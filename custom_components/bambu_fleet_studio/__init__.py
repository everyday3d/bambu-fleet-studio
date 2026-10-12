"""Bambu Lab Fleet Studio — Standalone Local LAN MQTT & Camera Integration for Home Assistant.

Zero third-party HACS integration dependencies (does NOT require greghesp/ha-bambulab).
Connects directly to Bambu Lab printers over:
- TCP Port 8883 TLS (MQTT telemetry & printer control commands)
- TCP Port 6000 TLS (Binary JPEG camera stream for A1, A1 Mini, A2L, P1P, P1S)
- TCP Port 322 TLS (RTSPS 1080p camera stream for P2S, X1C, X1E, X2D, H2C, H2D, H2S, R1)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import socket
import ssl
import struct
import threading
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from aiohttp import web
import paho.mqtt.client as mqtt

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

DOMAIN = "bambu_fleet_studio"
VERSION = "1.2.3"
STORAGE_KEY = "bambu_fleet_studio.printers"
STORAGE_VERSION = 1
LOGGER = logging.getLogger(__name__)

SERIAL_PREFIX_MODELS = {
    "00M": "X1C",
    "00W": "X1",
    "03W": "X1E",
    "01S": "P1P",
    "01P": "P1S",
    "22E": "P2S",
    "030": "A1MINI",
    "039": "A1",
    "094": "H2D",
    "093": "H2S",
}

RTSP_MODELS = {"P2S", "X1C", "X1", "X1E", "X2D", "H2C", "H2D", "H2DPRO", "H2S", "R1"}

SPEED_LEVEL_MAP = {
    1: "silent",
    2: "standard",
    3: "sport",
    4: "ludicrous",
    "1": "silent",
    "2": "standard",
    "3": "sport",
    "4": "ludicrous",
}

SPEED_NAME_TO_LEVEL = {
    "silent": "1",
    "standard": "2",
    "sport": "3",
    "ludicrous": "4",
}


def infer_model_from_serial(serial: str) -> str:
    """Infer Bambu Lab hardware model code from 15-character Serial Number prefix."""
    sn = (serial or "").strip().upper()
    if len(sn) >= 3:
        prefix = sn[:3]
        if prefix in SERIAL_PREFIX_MODELS:
            return SERIAL_PREFIX_MODELS[prefix]
    return "P1S"


def normalize_model_code(raw: str, serial: str = "") -> str:
    """Normalize model string to canonical uppercase code."""
    u = re.sub(r"[\s_-]+", "", (raw or "").strip().upper())
    if "A1MINI" in u:
        return "A1MINI"
    if "A2L" in u:
        return "A2L"
    if u.startswith("A1"):
        return "A1"
    if "P2S" in u:
        return "P2S"
    if "P1P" in u:
        return "P1P"
    if "P1S" in u:
        return "P1S"
    if "X1E" in u:
        return "X1E"
    if "X2D" in u:
        return "X2D"
    if "X1" in u:
        return "X1C"
    if "H2C" in u:
        return "H2C"
    if "H2D" in u:
        return "H2D"
    if "H2S" in u:
        return "H2S"
    if "R1" in u or "LASER" in u:
        return "R1"
    if serial:
        return infer_model_from_serial(serial)
    return "P1S"


def discover_serial_from_tls(host: str, port: int = 8883, timeout: float = 2.0) -> Optional[dict[str, str]]:
    """Connect to printer Port 8883 TLS and extract 15-character Serial Number from peer certificate CN."""
    if not host:
        return None
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=timeout) as raw_sock:
            with ctx.wrap_socket(raw_sock, server_hostname=host) as tls_sock:
                der_cert = tls_sock.getpeercert(binary_form=True)
                if not der_cert:
                    return None
                cert = x509.load_der_x509_certificate(der_cert)
                cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                issuer_attrs = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
                issuer_str = issuer_attrs[0].value if issuer_attrs else ""
                if cn_attrs:
                    cn_val = str(cn_attrs[0].value).strip().upper()
                    if re.match(r"^[0-9A-Z]{14,16}$", cn_val) or "BBL" in issuer_str.upper():
                        model = infer_model_from_serial(cn_val)
                        return {
                            "serial": cn_val,
                            "model": model,
                            "host": host,
                            "issuer": issuer_str,
                        }
    except Exception as err:
        LOGGER.debug("TLS serial discovery failed for %s:%s: %s", host, port, err)
    return None


def _make_digest_header(user: str, password: str, method: str, uri: str, realm: str, nonce: str) -> str:
    ha1 = hashlib.md5(f"{user}:{realm}:{password}".encode("utf-8")).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode("utf-8")).hexdigest()
    resp = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode("utf-8")).hexdigest()
    return (
        f'Digest username="{user}", realm="{realm}", '
        f'nonce="{nonce}", uri="{uri}", response="{resp}"'
    )


class _LocalRtspsBridge:
    """Localhost RTSP-to-RTSPS TCP bridge for Bambu Lab printers (P2S / X1 / H2D / R1) on port 322."""

    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(8)
        self.local_port = self._srv.getsockname()[1]
        self._thread = threading.Thread(
            target=self._accept_loop,
            name=f"bfs_rtsps_bridge_{self.local_port}",
            daemon=True,
        )
        self._thread.start()

    def _accept_loop(self) -> None:
        while True:
            try:
                client_sock, _ = self._srv.accept()
                threading.Thread(
                    target=self._handle_client,
                    args=(client_sock,),
                    daemon=True,
                ).start()
            except Exception:
                break

    def _handle_client(self, client_sock: socket.socket) -> None:
        upstream_sock = None
        try:
            raw_sock = socket.create_connection((self.host, self.port), timeout=8)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            upstream_sock = ctx.wrap_socket(raw_sock, server_hostname=self.host)
            upstream_sock.settimeout(25)
            client_sock.settimeout(25)
        except Exception:
            try:
                client_sock.close()
            except Exception:
                pass
            return

        state: dict[str, Any] = {
            "realm": "",
            "nonce": "",
            "last_req": None,
            "streaming": False,
            "lock": threading.Lock(),
        }

        def send_upstream(req: dict[str, Any]) -> None:
            with state["lock"]:
                state["last_req"] = req
                lines = list(req["header_lines"])
                if state["realm"] and state["nonce"]:
                    auth = _make_digest_header(
                        self.user,
                        self.password,
                        req["method"],
                        req["upstream_uri"],
                        state["realm"],
                        state["nonce"],
                    )
                    lines.append(f"Authorization: {auth}")
                payload = ("\r\n".join(lines) + "\r\n\r\n").encode("latin1")
                upstream_sock.sendall(payload)

        def client_to_upstream() -> None:
            try:
                while True:
                    data = client_sock.recv(8192)
                    if not data:
                        break
                    if data.startswith(b"$"):
                        upstream_sock.sendall(data)
                        continue
                    text = data.decode("latin1", errors="ignore")
                    first_end = text.find("\r\n")
                    if first_end == -1:
                        upstream_sock.sendall(data)
                        continue
                    req_line = text[:first_end]
                    m = re.match(
                        r"^(OPTIONS|DESCRIBE|SETUP|PLAY|PAUSE|TEARDOWN|GET_PARAMETER|SET_PARAMETER)\s+(\S+)\s+RTSP/1\.0$",
                        req_line,
                    )
                    if not m:
                        upstream_sock.sendall(data)
                        continue
                    method = m.group(1)
                    orig_uri = m.group(2)
                    cseq_m = re.search(r"CSeq:\s*(\d+)", text, re.IGNORECASE)
                    cseq = cseq_m.group(1) if cseq_m else "1"

                    if (
                        method == "SETUP"
                        and re.search(r"Transport:.*UDP", text, re.IGNORECASE)
                        and not re.search(r"Transport:.*TCP", text, re.IGNORECASE)
                    ):
                        reply = f"RTSP/1.0 461 Unsupported Transport\r\nCSeq: {cseq}\r\n\r\n"
                        client_sock.sendall(reply.encode("latin1"))
                        continue

                    upstream_uri = re.sub(
                        r"^rtsp://(127\.0\.0\.1|localhost):\d+",
                        f"rtsps://{self.host}:{self.port}",
                        orig_uri,
                    )
                    raw_lines = text.split("\r\n")
                    header_lines = [f"{method} {upstream_uri} RTSP/1.0"]
                    for line in raw_lines[1:]:
                        if not line or line.lower().startswith("authorization:"):
                            continue
                        header_lines.append(line)

                    send_upstream(
                        {
                            "method": method,
                            "upstream_uri": upstream_uri,
                            "header_lines": header_lines,
                        }
                    )
            except Exception:
                pass
            finally:
                for s in (upstream_sock, client_sock):
                    try:
                        s.close()
                    except Exception:
                        pass

        def upstream_to_client() -> None:
            try:
                while True:
                    chunk = upstream_sock.recv(16384)
                    if not chunk:
                        break
                    if state["streaming"]:
                        client_sock.sendall(chunk)
                        continue

                    if chunk.startswith(b"RTSP/1.0 401"):
                        txt = chunk.decode("latin1", errors="ignore")
                        r_m = re.search(r'realm="([^"]+)"', txt)
                        n_m = re.search(r'nonce="([^"]+)"', txt)
                        if r_m and n_m:
                            state["realm"] = r_m.group(1)
                            state["nonce"] = n_m.group(1)
                            if state["last_req"] is not None:
                                send_upstream(state["last_req"])
                                continue

                    if chunk.startswith(b"RTSP/1.0"):
                        while b"\r\n\r\n" not in chunk:
                            more = upstream_sock.recv(8192)
                            if not more:
                                break
                            chunk += more
                        sep = chunk.find(b"\r\n\r\n")
                        if sep != -1:
                            hdr_str = chunk[:sep].decode("latin1", errors="ignore")
                            body_bytes = chunk[sep + 4 :]
                            local_base = f"rtsp://127.0.0.1:{self.local_port}"
                            hdr_str = hdr_str.replace(
                                f"rtsps://{self.host}:{self.port}", local_base
                            ).replace(f"rtsps://{self.host}", local_base)

                            cl_m = re.search(r"Content-Length:\s*(\d+)", hdr_str, re.IGNORECASE)
                            last_method = state["last_req"]["method"] if state["last_req"] else ""
                            if cl_m and last_method == "DESCRIBE":
                                expected_len = int(cl_m.group(1))
                                while len(body_bytes) < expected_len:
                                    more = upstream_sock.recv(8192)
                                    if not more:
                                        break
                                    body_bytes += more
                                sdp_part = body_bytes[:expected_len].decode("latin1", errors="ignore")
                                rem_part = body_bytes[expected_len:]
                                sdp_part = sdp_part.replace(
                                    f"rtsps://{self.host}:{self.port}", local_base
                                ).replace(f"rtsps://{self.host}", local_base)
                                sdp_encoded = sdp_part.encode("latin1")
                                hdr_str = re.sub(
                                    r"Content-Length:\s*\d+",
                                    f"Content-Length: {len(sdp_encoded)}",
                                    hdr_str,
                                    flags=re.IGNORECASE,
                                )
                                out = hdr_str.encode("latin1") + b"\r\n\r\n" + sdp_encoded + rem_part
                                client_sock.sendall(out)
                                continue

                            if last_method == "PLAY" and "200 OK" in hdr_str:
                                state["streaming"] = True

                            out = hdr_str.encode("latin1") + b"\r\n\r\n" + body_bytes
                            client_sock.sendall(out)
                            continue

                    client_sock.sendall(chunk)
            except Exception:
                pass
            finally:
                for s in (client_sock, upstream_sock):
                    try:
                        s.close()
                    except Exception:
                        pass

        t_up = threading.Thread(target=client_to_upstream, daemon=True)
        t_down = threading.Thread(target=upstream_to_client, daemon=True)
        t_up.start()
        t_down.start()
        t_up.join()
        t_down.join()


_RTSPS_BRIDGES: dict[tuple[str, int, str, str], _LocalRtspsBridge] = {}
_RTSPS_BRIDGES_LOCK = threading.Lock()


def get_or_create_rtsps_bridge(host: str, access_code: str, port: int = 322, path: str = "/streaming/live/1") -> str:
    """Return a local rtsp://127.0.0.1:<port>/... URL bridging an rtsps:// printer stream."""
    key = (host, port, "bblp", access_code)
    with _RTSPS_BRIDGES_LOCK:
        bridge = _RTSPS_BRIDGES.get(key)
        if bridge is None:
            bridge = _LocalRtspsBridge(host, port, "bblp", access_code)
            _RTSPS_BRIDGES[key] = bridge
    return f"rtsp://127.0.0.1:{bridge.local_port}{path}"


class BambuPrinterRuntime:
    """Standalone Local LAN MQTT (Port 8883) & Camera (Port 6000 / Port 322 RTSPS) runtime for a single Bambu printer."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self.serial: str = str(config.get("serial") or "").strip().upper()
        self.host: str = str(config.get("host") or "").strip()
        self.access_code: str = str(config.get("access_code") or "").strip()
        self.model: str = normalize_model_code(str(config.get("model") or ""), self.serial)
        self.name: str = str(config.get("name") or f"Bambu {self.model}").strip()
        self.usage_hours: str = str(config.get("usage_hours") or "0")
        self.ams_override: str = str(config.get("ams_override") or "AUTO").strip().upper()
        self.smart_plug: dict[str, Any] = config.get("smart_plug") or {}
        self.prefix: str = f"{self.model.lower()}_{self.serial.lower()}"

        self._stop_event = threading.Event()
        self._mqtt_client: Optional[mqtt.Client] = None
        self._mqtt_thread: Optional[threading.Thread] = None
        self._cam_thread: Optional[threading.Thread] = None
        self._jpeg_lock = threading.Lock()
        self._last_jpeg: Optional[bytes] = None
        self._last_jpeg_ts: float = 0.0
        self._seq_id: int = 1

        # Live telemetry state
        self.online: bool = False
        self.last_seen: float = 0.0
        self.sw_version: str = "—"
        self.print_status: str = "offline"
        self.current_stage: str = "offline"
        self.progress: int = 0
        self.nozzle_temp: str = "—"
        self.nozzle_target: str = "0"
        self.bed_temp: str = "—"
        self.bed_target: str = "0"
        self.chamber_temp: str = "—"
        self.current_layer: str = "0"
        self.total_layers: str = "0"
        self.remaining_mins: str = "0"
        self.task_name: str = "No active print job"
        self.print_weight: str = "—"
        self.print_length: str = "—"
        self.bed_type: str = "Textured Plate"
        self.nozzle_size: str = "0.4"
        self.nozzle_type: str = "hardened steel"
        self.wifi_signal: str = "—"
        self.speed_profile: str = "standard"
        self.cooling_fan: str = "0"
        self.heatbreak_fan: str = "0"
        self.aux_fan: str = "—"
        self.chamber_fan: str = "—"
        self.has_door_sensor: bool = self.model in ("P2S", "X1C", "X1E", "X2D", "H2C", "H2D", "H2S", "R1")
        self.door_open: bool = False
        self.light_on: bool = False
        self.hms_errors: list[dict[str, Any]] = []
        self.print_error: int = 0
        self.rtsp_url: str = ""
        self.ams_units: list[dict[str, Any]] = []
        self.ext_spool: dict[str, Any] = {
            "name": "External Spool",
            "type": "PLA",
            "color": "#f59e0b",
            "active": False,
            "empty": True,
        }

    def start(self) -> None:
        """Start background MQTT and Camera threads."""
        self._stop_event.clear()
        if self.host and self.access_code and self.serial:
            self._mqtt_thread = threading.Thread(
                target=self._mqtt_loop,
                name=f"bfs_mqtt_{self.serial}",
                daemon=True,
            )
            self._mqtt_thread.start()

            if self.model not in RTSP_MODELS:
                self._cam_thread = threading.Thread(
                    target=self._port6000_cam_loop,
                    name=f"bfs_cam6000_{self.serial}",
                    daemon=True,
                )
                self._cam_thread.start()

    def stop(self) -> None:
        """Stop background MQTT and Camera threads."""
        self._stop_event.set()
        if self._mqtt_client:
            try:
                self._mqtt_client.disconnect()
            except Exception:
                pass

    def _next_seq(self) -> str:
        self._seq_id += 1
        return str(self._seq_id)

    def publish_command(self, payload: dict[str, Any]) -> bool:
        """Publish a command JSON payload to device/<serial>/request."""
        if not self._mqtt_client or not self.online:
            return False
        try:
            topic = f"device/{self.serial}/request"
            self._mqtt_client.publish(topic, json.dumps(payload), qos=0)
            return True
        except Exception as err:
            LOGGER.warning("Failed to publish MQTT command to %s: %s", self.serial, err)
            return False

    def send_action(self, action: str, value: Any = None) -> bool:
        """Execute a high-level printer control action over Local LAN MQTT."""
        act = (action or "").strip().lower()
        if act in ("light", "light_toggle"):
            next_mode = "off" if self.light_on else "on"
            self.light_on = next_mode == "on"
            return self.publish_command({
                "system": {
                    "sequence_id": self._next_seq(),
                    "command": "ledctrl",
                    "led_node": "chamber_light",
                    "led_mode": next_mode,
                    "led_on_time": 500,
                    "led_off_time": 500,
                    "loop_times": 0,
                    "interval_time": 0,
                }
            })
        if act in ("light_on", "light_off"):
            next_mode = "on" if act == "light_on" else "off"
            self.light_on = next_mode == "on"
            return self.publish_command({
                "system": {
                    "sequence_id": self._next_seq(),
                    "command": "ledctrl",
                    "led_node": "chamber_light",
                    "led_mode": next_mode,
                    "led_on_time": 500,
                    "led_off_time": 500,
                    "loop_times": 0,
                    "interval_time": 0,
                }
            })
        if act in ("refresh", "pushall"):
            return self.publish_command({
                "pushing": {
                    "sequence_id": self._next_seq(),
                    "command": "pushall",
                    "version": 1,
                    "push_target": 1,
                }
            })
        if act == "pause":
            return self.publish_command({
                "print": {
                    "sequence_id": self._next_seq(),
                    "command": "pause",
                    "param": "",
                }
            })
        if act == "resume":
            return self.publish_command({
                "print": {
                    "sequence_id": self._next_seq(),
                    "command": "resume",
                    "param": "",
                }
            })
        if act == "stop":
            return self.publish_command({
                "print": {
                    "sequence_id": self._next_seq(),
                    "command": "stop",
                    "param": "",
                }
            })
        if act == "speed":
            lvl = SPEED_NAME_TO_LEVEL.get(str(value or "").lower(), str(value or "2"))
            return self.publish_command({
                "print": {
                    "sequence_id": self._next_seq(),
                    "command": "print_speed",
                    "param": lvl,
                }
            })
        if act in ("ams_filament_setting", "set_filament") and isinstance(value, dict):
            is_ext = bool(value.get("is_ext") or str(value.get("slot_code") or "").upper() == "EXT")
            unit_num = int(value.get("unit_num", 1) or 1)
            slot_num = int(value.get("slot", 1) or 1)
            ams_id = 255 if is_ext else max(0, unit_num - 1)
            tray_id = 254 if is_ext else max(0, slot_num - 1)
            raw_hex = str(value.get("color") or "#00AE42").strip().lstrip("#").upper()
            if len(raw_hex) == 6:
                rgba_hex = raw_hex + "FF"
            elif len(raw_hex) == 8:
                rgba_hex = raw_hex
            else:
                rgba_hex = "00AE42FF"
            fil_type = str(value.get("type") or "PLA").strip().upper()
            idx_map = {
                "PLA": ("GFL99", 190, 240),
                "PLA+": ("GFL99", 195, 240),
                "PLA-CF": ("GFL98", 200, 240),
                "PETG": ("GFG99", 220, 260),
                "ABS": ("GFB99", 240, 280),
                "ASA": ("GFB98", 240, 280),
                "TPU": ("GFU99", 200, 240),
                "PA": ("GFN99", 260, 300),
                "PA-CF": ("GFN98", 260, 300),
                "PC": ("GFC99", 260, 290),
            }
            default_idx, default_min, default_max = idx_map.get(fil_type, ("GFL99", 190, 240))
            tray_info_idx = str(value.get("tray_info_idx") or default_idx)
            temp_min = int(value.get("nozzle_temp_min") or default_min)
            temp_max = int(value.get("nozzle_temp_max") or default_max)
            custom_name = str(value.get("name") or fil_type).strip()

            # Optimistically update in-memory tray state
            css_hex = "#" + rgba_hex[:6]
            if is_ext:
                self.ext_spool = {
                    "name": custom_name,
                    "type": fil_type,
                    "color": css_hex,
                    "active": bool(self.ext_spool.get("active")),
                    "empty": False,
                }
            else:
                for u in self.ams_units:
                    if int(u.get("unitNum", 1)) == unit_num:
                        for tr in u.get("trays", []):
                            if int(tr.get("slot", 0)) == slot_num:
                                tr["name"] = custom_name
                                tr["type"] = fil_type
                                tr["color"] = css_hex
                                tr["empty"] = False
                                if value.get("remain") is not None:
                                    try:
                                        tr["remain"] = max(0, min(100, int(value["remain"])))
                                    except Exception:
                                        pass

            return self.publish_command({
                "print": {
                    "sequence_id": self._next_seq(),
                    "command": "ams_filament_setting",
                    "ams_id": ams_id,
                    "tray_id": tray_id,
                    "tray_info_idx": tray_info_idx,
                    "tray_color": rgba_hex,
                    "nozzle_temp_min": temp_min,
                    "nozzle_temp_max": temp_max,
                    "tray_type": fil_type,
                }
            })
        return False

    def _mqtt_loop(self) -> None:
        """Persistent MQTT TLS connection loop to <host>:8883."""
        while not self._stop_event.is_set():
            try:
                try:
                    client = mqtt.Client(
                        mqtt.CallbackAPIVersion.VERSION2,
                        client_id=f"bambu_fleet_studio_{self.serial}_{int(time.time()) % 10000}",
                        protocol=mqtt.MQTTv311,
                    )
                except AttributeError:
                    client = mqtt.Client(
                        client_id=f"bambu_fleet_studio_{self.serial}_{int(time.time()) % 10000}",
                        protocol=mqtt.MQTTv311,
                    )

                client.username_pw_set("bblp", self.access_code)
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                client.tls_set_context(ctx)

                disconnected = [False]

                def on_connect(cli, userdata, flags, rc, *args):
                    rc_val = getattr(rc, "value", rc)
                    if rc_val == 0:
                        disconnected[0] = False
                        self.online = True
                        self.last_seen = time.time()
                        if self.print_status == "offline":
                            self.print_status = "idle"
                            self.current_stage = "idle"
                        cli.subscribe(f"device/{self.serial}/report")
                        cli.publish(
                            f"device/{self.serial}/request",
                            json.dumps({
                                "pushing": {
                                    "sequence_id": self._next_seq(),
                                    "command": "pushall",
                                    "version": 1,
                                    "push_target": 1,
                                }
                            }),
                        )
                        cli.publish(
                            f"device/{self.serial}/request",
                            json.dumps({
                                "info": {
                                    "sequence_id": self._next_seq(),
                                    "command": "get_version",
                                }
                            }),
                        )
                    else:
                        disconnected[0] = True
                        LOGGER.warning("MQTT connect rc=%s for %s (%s)", rc_val, self.serial, self.host)

                def on_disconnect(cli, userdata, *args):
                    disconnected[0] = True
                    if (time.time() - self.last_seen) > 90.0:
                        self.online = False
                        self.print_status = "offline"

                def on_message(cli, userdata, msg):
                    self.online = True
                    self.last_seen = time.time()
                    if self.print_status == "offline":
                        self.print_status = "idle"
                    try:
                        data = json.loads(msg.payload.decode("utf-8", errors="ignore"))
                        self._handle_mqtt_payload(data)
                    except Exception as parse_err:
                        LOGGER.debug("MQTT payload parse error (%s): %s", self.serial, parse_err)

                client.on_connect = on_connect
                client.on_disconnect = on_disconnect
                client.on_message = on_message

                self._mqtt_client = client
                client.connect(self.host, 8883, keepalive=30)
                client.loop_start()

                last_pushall = time.time()
                while not self._stop_event.is_set() and not disconnected[0]:
                    time.sleep(1.5)
                    now_ts = time.time()
                    if self.online and (now_ts - last_pushall) > 60.0:
                        last_pushall = now_ts
                        self.send_action("pushall")
                    if (now_ts - self.last_seen) > 120.0:
                        break

                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception:
                    pass
                for _ in range(4):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)
            except Exception as err:
                if (time.time() - self.last_seen) > 90.0:
                    self.online = False
                    self.print_status = "offline"
                LOGGER.warning("MQTT loop error for %s (%s): %s", self.serial, self.host, err)
                for _ in range(10):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)

    @staticmethod
    def _fan_gear_to_pct(val: Any) -> str:
        """Convert Bambu 0..15 fan gear value to 0..100% string."""
        try:
            n = int(str(val).strip())
            if 0 <= n <= 15:
                return str(round((n / 15.0) * 100))
            return str(min(100, max(0, n)))
        except Exception:
            return "0"

    def _handle_mqtt_payload(self, data: dict[str, Any]) -> None:
        """Update live telemetry fields from a Bambu Lab MQTT JSON message."""
        if "info" in data and isinstance(data["info"], dict):
            mods = data["info"].get("module")
            if isinstance(mods, list):
                for m in mods:
                    if isinstance(m, dict) and m.get("name") in ("ota", "mc", "ap") and m.get("sw_ver"):
                        self.sw_version = str(m["sw_ver"])
                        break

        p = data.get("print")
        if not isinstance(p, dict):
            return

        if "gcode_state" in p:
            raw_st = str(p["gcode_state"] or "").strip().lower()
            if raw_st in ("running", "pause", "prepare", "finish", "failed", "idle"):
                self.print_status = raw_st
            elif raw_st:
                self.print_status = "idle" if raw_st == "init" else raw_st

        if "stg_cur" in p:
            self.current_stage = str(p["stg_cur"])

        if "mc_percent" in p:
            try:
                self.progress = min(100, max(0, int(float(p["mc_percent"]))))
            except Exception:
                pass

        if "nozzle_temper" in p:
            try:
                self.nozzle_temp = str(round(float(p["nozzle_temper"])))
            except Exception:
                pass
        if "nozzle_target_temper" in p:
            try:
                self.nozzle_target = str(round(float(p["nozzle_target_temper"])))
            except Exception:
                pass
        if "bed_temper" in p:
            try:
                self.bed_temp = str(round(float(p["bed_temper"])))
            except Exception:
                pass
        if "bed_target_temper" in p:
            try:
                self.bed_target = str(round(float(p["bed_target_temper"])))
            except Exception:
                pass

        # Chamber temperature (either chamber_temper or ctc.info.temp)
        if "chamber_temper" in p:
            try:
                ct = float(p["chamber_temper"])
                if 0 < ct < 130:
                    self.chamber_temp = str(round(ct))
            except Exception:
                pass
        if isinstance(p.get("device"), dict) and isinstance(p["device"].get("ctc"), dict):
            try:
                ctc_info = p["device"]["ctc"].get("info", {})
                ct_raw = int(ctc_info.get("temp", 0)) & 0xFFFF
                if 0 < ct_raw < 130:
                    self.chamber_temp = str(ct_raw)
            except Exception:
                pass

        if "layer_num" in p:
            self.current_layer = str(p["layer_num"])
        if "total_layer_num" in p:
            self.total_layers = str(p["total_layer_num"])
        if "mc_remaining_time" in p:
            self.remaining_mins = str(p["mc_remaining_time"])

        if "subtask_name" in p and p["subtask_name"]:
            self.task_name = str(p["subtask_name"])
        elif "gcode_file" in p and p["gcode_file"]:
            self.task_name = str(p["gcode_file"])

        if "wifi_signal" in p and p["wifi_signal"]:
            self.wifi_signal = str(p["wifi_signal"])
        if "nozzle_diameter" in p and p["nozzle_diameter"]:
            self.nozzle_size = str(p["nozzle_diameter"])
        if "nozzle_type" in p and p["nozzle_type"]:
            self.nozzle_type = str(p["nozzle_type"]).replace("_", " ")

        if "spd_lvl" in p:
            self.speed_profile = SPEED_LEVEL_MAP.get(p["spd_lvl"], "standard")

        if "cooling_fan_speed" in p:
            self.cooling_fan = self._fan_gear_to_pct(p["cooling_fan_speed"])
        if "heatbreak_fan_speed" in p:
            self.heatbreak_fan = self._fan_gear_to_pct(p["heatbreak_fan_speed"])
        if "big_fan1_speed" in p:
            self.aux_fan = self._fan_gear_to_pct(p["big_fan1_speed"])
        if "big_fan2_speed" in p:
            self.chamber_fan = self._fan_gear_to_pct(p["big_fan2_speed"])

        if isinstance(p.get("lights_report"), list):
            for lr in p["lights_report"]:
                if isinstance(lr, dict) and lr.get("node") == "chamber_light":
                    self.light_on = str(lr.get("mode", "")).lower() == "on"

        if "home_flag" in p:
            try:
                hf = int(p["home_flag"])
                if self.has_door_sensor:
                    self.door_open = bool(hf & 0x00800000)
            except Exception:
                pass

        if isinstance(p.get("ipcam"), dict):
            rtsp = p["ipcam"].get("rtsp_url")
            if rtsp is not None:
                self.rtsp_url = str(rtsp)

        if "hms" in p and isinstance(p["hms"], list):
            self.hms_errors = p["hms"]
        if "print_error" in p:
            try:
                self.print_error = int(p["print_error"])
            except Exception:
                pass

        # Parse External Spool (vt_tray)
        vt = p.get("vt_tray")
        if isinstance(vt, dict):
            t_type = str(vt.get("tray_type") or "").strip()
            t_color = str(vt.get("tray_color") or "F59E0BFF").strip()
            hex_col = ("#" + t_color[:6]) if len(t_color) >= 6 else "#f59e0b"
            is_empty = not bool(t_type)
            sub_brand = str(vt.get("tray_sub_brands") or t_type or "External Spool").strip()
            self.ext_spool = {
                "name": "Empty" if is_empty else sub_brand,
                "type": t_type or "PLA",
                "color": hex_col,
                "active": False,
                "empty": is_empty,
            }

        # Parse Multi-AMS units (ams.ams)
        ams_block = p.get("ams")
        if isinstance(ams_block, dict) and isinstance(ams_block.get("ams"), list):
            tray_now_raw = str(ams_block.get("tray_now") or "255")
            raw_units = ams_block["ams"]
            parsed_units = []
            for idx, u in enumerate(raw_units):
                if not isinstance(u, dict):
                    continue
                unit_id = int(str(u.get("id", idx)))
                unit_num = unit_id + 1
                bank_letter = ["A", "B", "C", "D"][unit_id] if 0 <= unit_id < 4 else "A"
                default_ams_code = "AMSLITE" if self.model in ("A1", "A1MINI", "A2L") else ("AMS2PRO" if self.model in ("P2S", "X2D", "H2C", "H2D", "H2S") else "AMS")
                ams_code = self.ams_override if (self.ams_override and self.ams_override not in ("AUTO", "NONE")) else default_ams_code

                hum_idx = str(u.get("humidity") or "—")
                hum_raw = u.get("humidity_raw")
                hum_pct: Optional[int] = None
                try:
                    if hum_raw is not None and int(str(hum_raw)) > 0:
                        hum_pct = int(str(hum_raw))
                except Exception:
                    hum_pct = None

                temp_str = "—"
                try:
                    t_val = float(u.get("temp", 0))
                    if t_val > 0:
                        temp_str = str(round(t_val, 1))
                except Exception:
                    pass

                is_open_air = ams_code == "AMSLITE" or (temp_str in ("—", "0", "0.0") and hum_pct is None)

                raw_trays = u.get("tray") if isinstance(u.get("tray"), list) else []
                tray_map = {int(str(t.get("id", 0))): t for t in raw_trays if isinstance(t, dict) and str(t.get("id", "")).isdigit()}

                trays_out = []
                for slot_idx in range(4):
                    slot_num = slot_idx + 1
                    t_obj = tray_map.get(slot_idx)
                    global_tray_id = str(unit_id * 4 + slot_idx)
                    is_active = tray_now_raw == global_tray_id
                    if not t_obj:
                        trays_out.append({
                            "slot": slot_num,
                            "slotCode": f"{bank_letter}{slot_num}",
                            "name": "Empty",
                            "type": "",
                            "color": "#334155",
                            "remain": None,
                            "active": is_active,
                            "empty": True,
                        })
                        continue
                    t_type = str(t_obj.get("tray_type") or "").strip()
                    t_sub = str(t_obj.get("tray_sub_brands") or t_type or "").strip()
                    t_col_raw = str(t_obj.get("tray_color") or "334155FF").strip().lstrip("#")
                    hex_color = ("#" + t_col_raw[:6]) if len(t_col_raw) >= 6 else "#334155"
                    is_empty = not bool(t_type)
                    rem_val = t_obj.get("remain")
                    remain: Optional[int] = None
                    try:
                        r_int = int(rem_val)
                        if 0 <= r_int <= 100:
                            remain = r_int
                    except Exception:
                        remain = None

                    trays_out.append({
                        "slot": slot_num,
                        "slotCode": f"{bank_letter}{slot_num}",
                        "name": "Empty" if is_empty else (t_sub or t_type),
                        "type": t_type or "PLA",
                        "color": hex_color,
                        "remain": remain,
                        "active": is_active,
                        "empty": is_empty,
                    })

                parsed_units.append({
                    "id": f"ams_{self.prefix}_{unit_num}",
                    "unitNum": unit_num,
                    "bankLetter": bank_letter,
                    "modelNorm": ams_code,
                    "isOpenAir": is_open_air,
                    "humidityIndex": hum_idx,
                    "humidityPct": hum_pct,
                    "isWet": bool(hum_pct is not None and hum_pct >= 45),
                    "isVeryWet": bool(hum_pct is not None and hum_pct >= 55),
                    "temperature": "—" if is_open_air else temp_str,
                    "tempUnit": "°C",
                    "drying": False,
                    "trays": trays_out,
                })
            self.ams_units = parsed_units

    def _port6000_cam_loop(self) -> None:
        """Background TCP Port 6000 TLS binary JPEG stream reader for A1, A1 Mini, P1P, P1S."""
        while not self._stop_event.is_set():
            if not self.online:
                time.sleep(2.0)
                continue
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with socket.create_connection((self.host, 6000), timeout=8.0) as raw_sock:
                    with ctx.wrap_socket(raw_sock, server_hostname=self.host) as tls_sock:
                        tls_sock.settimeout(12.0)
                        auth_pkt = struct.pack(
                            "<IIII32s32s",
                            0x40,
                            0x3000,
                            0,
                            0,
                            b"bblp",
                            self.access_code.encode("ascii"),
                        )
                        tls_sock.sendall(auth_pkt)

                        buf = bytearray()
                        while not self._stop_event.is_set():
                            chunk = tls_sock.recv(16384)
                            if not chunk:
                                break
                            buf.extend(chunk)
                            # Locate JPEG SOI (\xff\xd8\xff) and EOI (\xff\xd9)
                            soi = buf.find(b"\xff\xd8\xff")
                            if soi != -1:
                                eoi = buf.find(b"\xff\xd9", soi + 3)
                                if eoi != -1:
                                    jpeg_bytes = bytes(buf[soi : eoi + 2])
                                    del buf[: eoi + 2]
                                    if len(jpeg_bytes) > 1024:
                                        self.online = True
                                        with self._jpeg_lock:
                                            self._last_jpeg = jpeg_bytes
                                            self._last_jpeg_ts = time.monotonic()
                            elif len(buf) > 524288:
                                buf.clear()
            except Exception as err:
                LOGGER.debug("Port 6000 camera loop for %s (%s): %s", self.serial, self.host, err)
                for _ in range(8):
                    if self._stop_event.is_set():
                        break
                    time.sleep(0.5)

    def get_camera_jpeg(self) -> Optional[bytes]:
        """Return the latest JPEG frame from either Port 6000 TLS or Port 322 RTSPS."""
        now = time.monotonic()
        if self._last_jpeg and (now - self._last_jpeg_ts) < 1.2:
            return self._last_jpeg

        if self.model in RTSP_MODELS and self.online and self.rtsp_url != "disable":
            if self._jpeg_lock.acquire(blocking=False):
                try:
                    import av

                    bridge_url = get_or_create_rtsps_bridge(self.host, self.access_code, 322, "/streaming/live/1")
                    container = av.open(
                        bridge_url,
                        options={"rtsp_transport": "tcp"},
                        timeout=5.0,
                    )
                    try:
                        for frame in container.decode(video=0):
                            pil_img = frame.to_image()
                            out = BytesIO()
                            pil_img.save(out, format="JPEG", quality=85)
                            self._last_jpeg = out.getvalue()
                            self._last_jpeg_ts = time.monotonic()
                            return self._last_jpeg
                    finally:
                        container.close()
                except Exception as err:
                    LOGGER.debug("RTSPS decode error for %s: %s", self.serial, err)
                finally:
                    self._jpeg_lock.release()

        return self._last_jpeg

    def to_status_dict(self) -> dict[str, Any]:
        """Serialize runtime state for /api/bambu_fleet_studio/status."""
        recent_mqtt = self.last_seen > 0 and (time.time() - self.last_seen) < 120.0
        recent_cam = self._last_jpeg_ts > 0 and (time.monotonic() - self._last_jpeg_ts) < 30.0
        is_online = bool(self.online or recent_mqtt or recent_cam)
        cam_available = is_online and (
            (self.model in RTSP_MODELS and self.rtsp_url != "disable")
            or (self.model not in RTSP_MODELS and self._last_jpeg is not None)
        )
        p_status = self.print_status if is_online else "offline"
        if is_online and p_status == "offline":
            p_status = "idle"
        c_stage = self.current_stage if is_online else "offline"
        if is_online and c_stage == "offline":
            c_stage = "idle"
        return {
            "serial": self.serial,
            "prefix": self.prefix,
            "name": self.name,
            "model": self.model,
            "modelNorm": self.model,
            "rawModelNorm": self.model,
            "ipAddress": self.host,
            "swVersion": self.sw_version,
            "online": is_online,
            "printStatus": p_status,
            "currentStage": c_stage,
            "progress": self.progress,
            "nozzleTemp": self.nozzle_temp,
            "nozzleTarget": self.nozzle_target,
            "bedTemp": self.bed_temp,
            "bedTarget": self.bed_target,
            "chamberTemp": self.chamber_temp,
            "currentLayer": self.current_layer,
            "totalLayers": self.total_layers,
            "remainingMins": self.remaining_mins,
            "taskName": self.task_name,
            "printWeight": self.print_weight,
            "printLength": self.print_length,
            "totalUsage": self.usage_hours,
            "bedType": self.bed_type,
            "nozzleSize": self.nozzle_size,
            "nozzleType": self.nozzle_type,
            "wifiSignal": self.wifi_signal,
            "speedProfile": self.speed_profile,
            "coolingFan": self.cooling_fan,
            "heatbreakFan": self.heatbreak_fan,
            "auxFan": self.aux_fan,
            "chamberFan": self.chamber_fan,
            "hasDoorSensor": self.has_door_sensor,
            "doorOpen": self.door_open,
            "lightOn": self.light_on,
            "camAvailable": cam_available,
            "isRtspCam": self.model in RTSP_MODELS,
            "cameraPic": f"/api/bambu_fleet_studio/camera/{self.serial}",
            "cameraStreamUrl": f"/api/bambu_fleet_studio/camera_stream/{self.serial}",
            "hasAms": self.ams_override != "NONE" and len(self.ams_units) > 0,
            "amsUnits": self.ams_units,
            "extSpool": self.ext_spool,
            "smartPlugCfg": self.smart_plug,
            "standalone": True,
        }


class BambuFleetStudioManager:
    """Manages standalone BambuPrinterRuntime instances and persistent storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.runtimes: dict[str, BambuPrinterRuntime] = {}
        self.configs: dict[str, dict[str, Any]] = {}

    async def async_initialize(self) -> None:
        """Load saved printers (and auto-import any existing printer credentials on first run)."""
        stored = await self.store.async_load()
        if isinstance(stored, dict) and isinstance(stored.get("printers"), dict):
            self.configs = stored["printers"]

        # Auto-import any printer credentials from Home Assistant config_entries so existing printers work immediately
        imported = False
        for entry in self.hass.config_entries.async_entries():
            if entry.domain == "bambu_lab":
                sn = str(entry.data.get("serial") or entry.unique_id or "").strip().upper()
                host = str(entry.options.get("host") or entry.data.get("host") or "").strip()
                code = str(entry.options.get("access_code") or entry.data.get("access_code") or "").strip()
                mod = normalize_model_code(
                    str(entry.data.get("device_type") or entry.options.get("device_type") or ""),
                    sn,
                )
                opt_name = str(entry.options.get("name") or "").strip()
                title_name = str(entry.title or "").strip()
                if opt_name and opt_name.upper() != sn:
                    name = opt_name
                elif title_name and title_name.upper() != sn:
                    name = title_name
                else:
                    name = f"Bambu {mod}"
                usage_hours = str(entry.options.get("usage_hours") or entry.data.get("usage_hours") or "0")
                if sn and host and code:
                    if sn not in self.configs:
                        self.configs[sn] = {
                            "serial": sn,
                            "host": host,
                            "access_code": code,
                            "model": mod,
                            "name": name,
                            "usage_hours": usage_hours,
                            "ams_override": "AUTO",
                        }
                        imported = True
                    else:
                        if not self.configs[sn].get("access_code"):
                            self.configs[sn]["access_code"] = code
                            self.configs[sn]["host"] = host
                            imported = True
                        if self.configs[sn].get("name", "").upper() == sn and name.upper() != sn:
                            self.configs[sn]["name"] = name
                            imported = True
                        if not self.configs[sn].get("usage_hours") or self.configs[sn].get("usage_hours") == "0":
                            if usage_hours != "0":
                                self.configs[sn]["usage_hours"] = usage_hours
                                imported = True

        if imported:
            await self.async_save()

        for sn, cfg in list(self.configs.items()):
            await self.async_start_printer(sn, cfg)

    async def async_save(self) -> None:
        """Persist printer configs to .storage/bambu_fleet_studio.printers."""
        await self.store.async_save({"printers": self.configs})

    async def async_start_printer(self, serial: str, cfg: dict[str, Any]) -> BambuPrinterRuntime:
        """Start or restart a BambuPrinterRuntime."""
        sn = serial.strip().upper()
        if sn in self.runtimes:
            await self.hass.async_add_executor_job(self.runtimes[sn].stop)
        rt = BambuPrinterRuntime(self.hass, cfg)
        self.runtimes[sn] = rt
        await self.hass.async_add_executor_job(rt.start)
        return rt

    async def async_upsert_printer(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Add or update a standalone printer configuration."""
        host = str(payload.get("host") or "").strip()
        serial = str(payload.get("serial") or "").strip().upper()
        if serial == "AUTO":
            serial = ""
        if not serial and host:
            tls_info = await self.hass.async_add_executor_job(discover_serial_from_tls, host)
            if tls_info and tls_info.get("serial"):
                serial = tls_info["serial"].upper()
        if not serial:
            raise ValueError("Could not determine 15-character Serial Number. Verify printer IP or enter Serial manually.")

        existing = self.configs.get(serial, {})
        access_code = str(payload.get("access_code") or existing.get("access_code") or "").strip()
        model = normalize_model_code(str(payload.get("model") or existing.get("model") or ""), serial)
        name = str(payload.get("name") or existing.get("name") or f"Bambu {model}").strip()
        usage_hours = str(payload.get("usage_hours") if "usage_hours" in payload else existing.get("usage_hours", "0")).strip()
        ams_override = str(payload.get("ams_override") or existing.get("ams_override") or "AUTO").strip().upper()
        smart_plug = payload.get("smart_plug") if "smart_plug" in payload else existing.get("smart_plug", {})

        cfg = {
            "serial": serial,
            "host": host or existing.get("host", ""),
            "access_code": access_code,
            "model": model,
            "name": name,
            "usage_hours": usage_hours,
            "ams_override": ams_override,
            "smart_plug": smart_plug,
        }
        self.configs[serial] = cfg
        await self.async_save()
        rt = await self.async_start_printer(serial, cfg)
        for _ in range(22):
            if rt.online:
                break
            await asyncio.sleep(0.1)
        return rt.to_status_dict()

    async def async_delete_printer(self, serial_or_prefix: str) -> bool:
        """Delete a printer by serial or prefix."""
        target = (serial_or_prefix or "").strip().upper()
        matched_sn = None
        for sn, rt in list(self.runtimes.items()):
            if sn == target or rt.prefix.upper() == target:
                matched_sn = sn
                break
        if not matched_sn and target in self.configs:
            matched_sn = target
        if not matched_sn:
            return False

        rt = self.runtimes.pop(matched_sn, None)
        if rt:
            await self.hass.async_add_executor_job(rt.stop)
        self.configs.pop(matched_sn, None)
        await self.async_save()
        return True

    def find_runtime(self, serial_or_prefix: str) -> Optional[BambuPrinterRuntime]:
        """Find runtime by serial or prefix (e.g., p2s_22e8aj5b2401081)."""
        target = (serial_or_prefix or "").strip().upper()
        if target in self.runtimes:
            return self.runtimes[target]
        for rt in self.runtimes.values():
            if rt.prefix.upper() == target or rt.serial.upper() == target:
                return rt
        return None


async def async_scan_bambu_network(hass: HomeAssistant, subnet_override: str = "") -> dict[str, Any]:
    """Scan local /24 subnet(s) concurrently on TCP Port 8883 TLS to discover all Bambu Lab printers."""
    mgr: Optional[BambuFleetStudioManager] = hass.data.get(DOMAIN, {}).get("manager")
    known_by_serial: dict[str, dict[str, Any]] = {}
    subnets: set[str] = set()

    if mgr:
        for sn, rt in mgr.runtimes.items():
            if rt.host and re.match(r"^\d+\.\d+\.\d+\.\d+$", rt.host):
                subnets.add(".".join(rt.host.split(".")[:3]))
            known_by_serial[sn] = {
                "serial": sn,
                "model": rt.model,
                "host": rt.host,
                "name": rt.name,
                "entry_id": sn,
                "configured": True,
                "online": rt.online,
                "source": "bambu_fleet_studio",
            }

    if subnet_override and re.match(r"^\d+\.\d+\.\d+$", subnet_override.strip()):
        subnets = {subnet_override.strip()}
    elif not subnets:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", local_ip):
                    subnets.add(".".join(local_ip.split(".")[:3]))
        except Exception:
            subnets.add("192.168.1")

    candidate_ips = [f"{sub}.{i}" for sub in sorted(subnets) for i in range(1, 255)]
    sem = asyncio.Semaphore(85)
    open_8883_hosts: list[str] = []

    async def _probe_tcp_8883(ip: str) -> None:
        async with sem:
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(ip, 8883), timeout=0.60)
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                open_8883_hosts.append(ip)
            except Exception:
                pass

    await asyncio.gather(*(_probe_tcp_8883(ip) for ip in candidate_ips))

    async def _inspect_tls(ip: str) -> Optional[dict[str, Any]]:
        try:
            res = await hass.async_add_executor_job(discover_serial_from_tls, ip, 8883, 1.8)
            if res and res.get("serial"):
                return res
        except Exception:
            pass
        return None

    tls_results = await asyncio.gather(*(_inspect_tls(ip) for ip in open_8883_hosts))

    discovered_by_serial: dict[str, dict[str, Any]] = {}
    for tls_item in tls_results:
        if not tls_item or not tls_item.get("serial"):
            continue
        sn = tls_item["serial"].upper()
        live_host = tls_item.get("host", "")
        inferred_model = (tls_item.get("model") or "").upper()
        existing = known_by_serial.get(sn)
        if existing:
            prev_host = existing.get("host", "")
            ip_changed = bool(prev_host and live_host and prev_host != live_host)
            if ip_changed and mgr:
                try:
                    await mgr.async_upsert_printer({"serial": sn, "host": live_host})
                except Exception:
                    pass
            discovered_by_serial[sn] = {
                "serial": sn,
                "model": existing.get("model") or inferred_model or "P1S",
                "host": live_host or prev_host,
                "previous_host": prev_host if ip_changed else "",
                "ip_changed": ip_changed,
                "name": existing.get("name") or f"{inferred_model or 'Bambu'}_{sn[-4:]}",
                "entry_id": existing.get("entry_id", sn),
                "configured": True,
                "online": True,
                "source": "lan_tls_8883",
            }
        else:
            discovered_by_serial[sn] = {
                "serial": sn,
                "model": inferred_model or "P1S",
                "host": live_host,
                "previous_host": "",
                "ip_changed": False,
                "name": f"{inferred_model or 'Bambu'} ({sn[-4:]})",
                "entry_id": "",
                "configured": False,
                "online": True,
                "source": "lan_tls_8883",
            }

    for sn, kp in known_by_serial.items():
        if sn not in discovered_by_serial:
            discovered_by_serial[sn] = {
                **kp,
                "previous_host": "",
                "ip_changed": False,
            }

    printers_list = list(discovered_by_serial.values())
    printers_list.sort(
        key=lambda p: (
            0 if not p.get("configured") else (1 if p.get("ip_changed") else (2 if p.get("online") else 3)),
            p.get("host") or "999.999.999.999",
        )
    )

    return {
        "subnets": sorted(subnets),
        "scanned_hosts": len(candidate_ips),
        "open_8883_count": len(open_8883_hosts),
        "printers": printers_list,
    }


class FleetStatusAPIView(HomeAssistantView):
    """Return live standalone telemetry for all configured Bambu Lab printers."""

    url = "/api/bambu_fleet_studio/status"
    name = "api:bambu_fleet_studio:status"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
        printers = [rt.to_status_dict() for rt in mgr.runtimes.values()] if mgr else []
        return web.json_response({
            "standalone": True,
            "version": VERSION,
            "printers": printers,
        })


class FleetPrintersAPIView(HomeAssistantView):
    """Add, edit, or delete standalone Bambu Lab printers."""

    url = "/api/bambu_fleet_studio/printers"
    name = "api:bambu_fleet_studio:printers"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
        printers = []
        if mgr:
            for rt in mgr.runtimes.values():
                d = rt.to_status_dict()
                cfg = mgr.configs.get(rt.serial, {})
                d["host"] = rt.host or cfg.get("host", "")
                d["access_code"] = rt.access_code or cfg.get("access_code", "")
                d["usage_hours"] = cfg.get("usage_hours", rt.total_usage)
                printers.append(d)
        return web.json_response({"printers": printers})

    async def post(self, request: web.Request) -> web.Response:
        try:
            mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
            if not mgr:
                return web.json_response({"error": "Manager not initialized"}, status=500)
            body = await request.json()
            printer_dict = await mgr.async_upsert_printer(body)
            return web.json_response({"ok": True, "printer": printer_dict})
        except Exception as err:
            return web.json_response({"error": str(err)}, status=400)

    async def delete(self, request: web.Request) -> web.Response:
        try:
            mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
            if not mgr:
                return web.json_response({"error": "Manager not initialized"}, status=500)
            target = request.query.get("serial") or request.query.get("prefix") or ""
            if not target:
                try:
                    body = await request.json()
                    target = body.get("serial") or body.get("prefix") or ""
                except Exception:
                    pass
            removed = await mgr.async_delete_printer(target)
            return web.json_response({"ok": removed})
        except Exception as err:
            return web.json_response({"error": str(err)}, status=400)


class FleetCommandAPIView(HomeAssistantView):
    """Execute direct Local LAN MQTT printer commands (light, pause, resume, stop, speed, refresh, reload)."""

    url = "/api/bambu_fleet_studio/command"
    name = "api:bambu_fleet_studio:command"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        try:
            mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
            if not mgr:
                return web.json_response({"error": "Manager not initialized"}, status=500)
            body = await request.json()
            target = str(body.get("serial") or body.get("prefix") or "").strip()
            action = str(body.get("action") or body.get("command") or "").strip().lower()
            value = body.get("value")

            rt = mgr.find_runtime(target)
            if not rt:
                return web.json_response({"error": f"Printer {target} not found"}, status=404)

            if action == "reload":
                cfg = mgr.configs.get(rt.serial, {})
                await mgr.async_start_printer(rt.serial, cfg)
                return web.json_response({"ok": True, "reloaded": rt.serial})

            ok = await self.hass.async_add_executor_job(rt.send_action, action, value)
            return web.json_response({"ok": ok, "printer": rt.to_status_dict()})
        except Exception as err:
            return web.json_response({"error": str(err)}, status=400)


class FleetCameraSnapshotAPIView(HomeAssistantView):
    """Serve live JPEG camera frame from Port 6000 TLS or Port 322 RTSPS."""

    url = "/api/bambu_fleet_studio/camera/{serial}"
    name = "api:bambu_fleet_studio:camera"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, serial: str) -> web.Response:
        mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
        rt = mgr.find_runtime(serial) if mgr else None
        if not rt:
            return web.Response(status=404)
        jpeg = await self.hass.async_add_executor_job(rt.get_camera_jpeg)
        if not jpeg:
            return web.Response(status=503)
        return web.Response(
            body=jpeg,
            content_type="image/jpeg",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )


class FleetCameraStreamAPIView(HomeAssistantView):
    """Serve multipart/x-mixed-replace MJPEG live stream from Port 6000 TLS or Port 322 RTSPS."""

    url = "/api/bambu_fleet_studio/camera_stream/{serial}"
    name = "api:bambu_fleet_studio:camera_stream"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, serial: str) -> web.StreamResponse:
        mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
        rt = mgr.find_runtime(serial) if mgr else None
        if not rt:
            return web.Response(status=404)

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "multipart/x-mixed-replace; boundary=frame",
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            },
        )
        await response.prepare(request)
        try:
            while True:
                jpeg = await self.hass.async_add_executor_job(rt.get_camera_jpeg)
                if jpeg:
                    part = (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
                        + jpeg
                        + b"\r\n"
                    )
                    await response.write(part)
                await asyncio.sleep(0.9 if rt.model not in RTSP_MODELS else 1.5)
        except Exception:
            pass
        return response


class FleetDiscoverSerialAPIView(HomeAssistantView):
    """Standalone Port 8883 TLS serial number discovery & /24 LAN network scanner."""

    url = "/api/bambu_fleet_studio/discover_serial"
    extra_urls = ["/api/bambu_fleet_studio/scan_network", "/api/bambu_lab/discover_serial", "/api/bambu_lab/scan_network"]
    name = "api:bambu_fleet_studio:discover_serial"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        try:
            host = (request.query.get("host") or "").strip()
            scan = (request.query.get("scan") or "").strip()
            subnet = (request.query.get("subnet") or "").strip()

            if scan in ("1", "true", "yes") or request.path.endswith("/scan_network"):
                scan_data = await async_scan_bambu_network(self.hass, subnet)
                return web.json_response(scan_data)

            if host:
                tls_res = await self.hass.async_add_executor_job(discover_serial_from_tls, host)
                if tls_res and tls_res.get("serial"):
                    return web.json_response(tls_res)
                return web.json_response({"serial": "", "model": "", "host": host}, status=404)

            scan_data = await async_scan_bambu_network(self.hass, subnet)
            return web.json_response(scan_data)
        except Exception as err:
            return web.json_response({"error": str(err)}, status=500)


async def _async_ensure_initialized(hass: HomeAssistant) -> BambuFleetStudioManager:
    """Initialize the standalone BambuFleetStudioManager and register HTTP views once."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "manager" in domain_data:
        return domain_data["manager"]

    mgr = BambuFleetStudioManager(hass)
    domain_data["manager"] = mgr
    await mgr.async_initialize()

    if not domain_data.get("views_registered"):
        hass.http.register_view(FleetStatusAPIView(hass))
        hass.http.register_view(FleetPrintersAPIView(hass))
        hass.http.register_view(FleetCommandAPIView(hass))
        hass.http.register_view(FleetCameraSnapshotAPIView(hass))
        hass.http.register_view(FleetCameraStreamAPIView(hass))
        hass.http.register_view(FleetDiscoverSerialAPIView(hass))
        domain_data["views_registered"] = True

    return mgr


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Bambu Lab Fleet Studio standalone integration from YAML or startup."""
    await _async_ensure_initialized(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bambu Lab Fleet Studio standalone integration from a config entry."""
    await _async_ensure_initialized(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    mgr: Optional[BambuFleetStudioManager] = hass.data.get(DOMAIN, {}).get("manager")
    if mgr:
        for rt in list(mgr.runtimes.values()):
            await hass.async_add_executor_job(rt.stop)
    return True
