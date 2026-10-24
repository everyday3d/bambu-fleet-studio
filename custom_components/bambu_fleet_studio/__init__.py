"""Bambu Lab Fleet Studio — Standalone Local LAN MQTT & Camera Integration for Home Assistant.

Zero third-party HACS integration dependencies (does NOT require greghesp/ha-bambulab).
Connects directly to Bambu Lab printers over:
- TCP Port 8883 TLS (MQTT telemetry & printer control commands)
- TCP Port 6000 TLS (Binary JPEG camera stream for A1, A1 Mini, A2L, P1P, P1S)
- TCP Port 322 TLS (RTSPS 1080p camera stream for P2S, X1C, X1E, X2D, H2C, H2D, H2S, R1)
"""

from __future__ import annotations

import asyncio
import functools
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
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
import urllib.request
from urllib.parse import urlparse

from aiohttp import web
import paho.mqtt.client as mqtt

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.components.http.auth import async_sign_path
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

DOMAIN = "bambu_fleet_studio"
VERSION = "1.4.0"
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)
GITHUB_RELEASES_API = "https://api.github.com/repos/everyday3d/bambu-fleet-studio/releases/latest"
GITHUB_RELEASES_WEB = "https://github.com/everyday3d/bambu-fleet-studio/releases/latest"
STORAGE_KEY = "bambu_fleet_studio.printers"
STORAGE_VERSION = 1
LOGGER = logging.getLogger(__name__)


def _parse_semver(ver_str: str) -> tuple[int, int, int]:
    """Parse a semantic version string (e.g. 'v1.1.3' -> (1, 1, 3))."""
    cleaned = re.sub(r"^[^0-9]*", "", str(ver_str or "").strip())
    parts = re.split(r"[^0-9]+", cleaned)
    nums = [int(p) for p in parts if p.isdigit()]
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])

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

    def __init__(self, hass: HomeAssistant, config: dict[str, Any], on_odometer_save: Optional[Any] = None) -> None:
        self.hass = hass
        self._config_ref = config
        self._on_odometer_save = on_odometer_save
        self.serial: str = str(config.get("serial") or "").strip().upper()
        self.host: str = str(config.get("host") or "").strip()
        self.access_code: str = str(config.get("access_code") or "").strip()
        self.model: str = normalize_model_code(str(config.get("model") or ""), self.serial)
        self.name: str = str(config.get("name") or f"Bambu {self.model}").strip()
        try:
            self._usage_hours_val: float = max(0.0, float(config.get("usage_hours") or 0.0))
        except Exception:
            self._usage_hours_val = 0.0
        self.usage_hours: str = self._fmt_num(self._usage_hours_val, 1)
        try:
            raw_m = max(0.0, float(config.get("extruded_meters") or 0.0))
            self._extruded_meters: float = raw_m if raw_m > 0.0 else round(self._usage_hours_val * 4.5, 1)
        except Exception:
            self._extruded_meters = round(self._usage_hours_val * 4.5, 1)
        try:
            raw_g = float(config.get("extruded_grams") or 0.0)
            self._extruded_grams: float = raw_g if raw_g > 0 else round(self._extruded_meters * 3.03, 1)
        except Exception:
            self._extruded_grams = round(self._extruded_meters * 3.03, 1)
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

        # Odometer runtime tracking
        self._last_running_ts: float = 0.0
        self._last_odometer_save_ts: float = time.time()
        self._odometer_dirty: bool = False
        self._active_job_key: str = ""
        self._last_job_progress: int = 0
        self._job_length_m: float = 0.0
        self._job_weight_g: float = 0.0
        self._job_accumulated_m: float = 0.0
        self._rfid_accumulated_m: float = 0.0
        self._last_tray_remains: dict[str, int] = {}
        self._low_spool_alerted: set[str] = set()
        raw_maint = config.get("maintenance_log")
        self.maintenance_log: dict[str, dict[str, Any]] = dict(raw_maint) if isinstance(raw_maint, dict) else {}

        # Live telemetry state
        self.online: bool = False
        self.auth_failed: bool = False
        self.last_seen: float = 0.0
        try:
            self.last_online_ts: float = max(0.0, float(config.get("last_online_ts") or 0.0))
        except Exception:
            self.last_online_ts = 0.0
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
        self.bed_type: str = str(config.get("bed_type") or "Bambu Textured PEI Plate").strip()
        self.nozzle_size: str = "0.4"
        self.nozzle_type: str = "hardened steel"
        self.active_nozzle_index: int = 0
        self.left_nozzle_temp: str = "—"
        self.left_nozzle_target: str = "0"
        self.left_nozzle_size: str = "0.4"
        self.left_nozzle_type: str = "Hardened Steel"
        self.right_nozzle_temp: str = "—"
        self.right_nozzle_target: str = "0"
        self.right_nozzle_size: str = "0.4"
        self.right_nozzle_type: str = "Hardened Steel"
        self.vortek_tar_id: int = 0
        self.vortek_exist_mask: int = 0
        self.vortek_hotends: dict[int, dict[str, Any]] = {}
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

    @staticmethod
    def _fmt_num(val: float, decimals: int = 1) -> str:
        rounded = round(float(val), decimals)
        if rounded == int(rounded):
            return str(int(rounded))
        return str(rounded)

    @staticmethod
    def _decode_nozzle_type_code(type_code: str) -> tuple[str, str]:
        """Decode Bambu nozzle type code (e.g. 'HS01', 'HH01', 'NH01', 'HU01') into (flow_label, material_label)."""
        code = str(type_code or "").strip()
        if not code:
            return "Standard", "Hardened Steel"
        up = code.upper()
        if len(up) >= 4 and up[:2] in ("HS", "HH", "HE", "HU", "NH", "NS"):
            flow_lbl = "TPU High-Flow" if up[1] == "U" else ("High-Flow" if up[1] in ("H", "E") else "Standard")
            mat_map = {
                "00": "Stainless Steel",
                "01": "Hardened Steel",
                "05": "Tungsten Carbide",
            }
            mat_lbl = mat_map.get(up[2:4], "Hardened Steel")
            return flow_lbl, mat_lbl
        low = code.lower().replace("_", " ")
        flow_lbl = "TPU High-Flow" if "tpu" in low else ("High-Flow" if "high flow" in low else "Standard")
        if "tungsten" in low:
            mat_lbl = "Tungsten Carbide"
        elif "stainless" in low:
            mat_lbl = "Stainless Steel"
        else:
            mat_lbl = "Hardened Steel"
        return flow_lbl, mat_lbl

    def _touch_online(self, now_ts: Optional[float] = None) -> None:
        """Record live online heartbeat and schedule periodic persistence of last_online_ts."""
        ts = now_ts if now_ts is not None else time.time()
        was_online = self.online
        self.online = True
        self.last_seen = ts
        self.last_online_ts = ts
        if isinstance(self._config_ref, dict):
            self._config_ref["last_online_ts"] = round(ts, 1)
        if not was_online or (ts - self._last_odometer_save_ts) >= 300.0:
            self._odometer_dirty = True
            if not was_online:
                self._persist_odometer(ts)

    def _mark_offline(self, now_ts: Optional[float] = None) -> None:
        """Mark printer offline and persist the exact last_online_ts timestamp."""
        ts = now_ts if now_ts is not None else time.time()
        was_online = self.online
        self.online = False
        self.print_status = "offline"
        if was_online:
            if self.last_online_ts <= 0:
                self.last_online_ts = self.last_seen if self.last_seen > 0 else ts
            self._persist_odometer(ts)

    def _persist_odometer(self, now_ts: Optional[float] = None) -> None:
        """Sync live odometer counters and last_online_ts back into config dict and trigger async Store save."""
        self.usage_hours = self._fmt_num(self._usage_hours_val, 1)
        if isinstance(self._config_ref, dict):
            self._config_ref["usage_hours"] = self.usage_hours
            self._config_ref["extruded_meters"] = round(self._extruded_meters, 2)
            self._config_ref["extruded_grams"] = round(self._extruded_grams, 1)
            if self.last_online_ts > 0:
                self._config_ref["last_online_ts"] = round(self.last_online_ts, 1)
        self._odometer_dirty = False
        self._last_odometer_save_ts = now_ts if now_ts is not None else time.time()
        if callable(self._on_odometer_save):
            try:
                self._on_odometer_save()
            except Exception:
                pass

    def _tick_odometer(self, now_ts: float, force_save: bool = False) -> None:
        """Accumulate active print hours and fallback speed-scaled filament meters while running."""
        if self.online and self.print_status == "running":
            if self._last_running_ts > 0.0:
                dt = now_ts - self._last_running_ts
                if 0.0 < dt <= 30.0:
                    self._usage_hours_val += dt / 3600.0
                    self.usage_hours = self._fmt_num(self._usage_hours_val, 1)
                    if self._job_length_m <= 0.0:
                        speed_rates = {
                            "silent": 2.5,
                            "standard": 4.2,
                            "sport": 5.2,
                            "ludicrous": 6.8,
                        }
                        rate_m_hr = speed_rates.get(str(self.speed_profile).lower(), 4.2)
                        dm = (rate_m_hr / 3600.0) * dt
                        self._extruded_meters += dm
                        self._extruded_grams += dm * 3.03
                        self._job_accumulated_m += dm
                    self._odometer_dirty = True
            self._last_running_ts = now_ts
        else:
            if self._last_running_ts > 0.0:
                self._last_running_ts = 0.0
                force_save = True

        if self._odometer_dirty and (force_save or (now_ts - self._last_odometer_save_ts) >= 180.0):
            self._persist_odometer(now_ts)

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
        return False

    def _mqtt_loop(self) -> None:
        """Persistent MQTT TLS connection loop to <host>:8883."""
        retry_delay = 2.0
        while not self._stop_event.is_set():
            if self.auth_failed:
                # Stop reconnect loop on authentication failure; user must update access code via UI
                break

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
                        self.auth_failed = False
                        self._touch_online()
                        if self.print_status == "offline":
                            self.print_status = "idle"
                            self.current_stage = "idle"
                        try:
                            self.hass.loop.call_soon_threadsafe(
                                functools.partial(
                                    async_delete_issue,
                                    self.hass,
                                    DOMAIN,
                                    f"bad_access_code_{self.serial.lower()}",
                                )
                            )
                        except Exception:
                            pass
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
                        rc_str = str(rc).lower()
                        if rc_val in (4, 5, 134, 135) or "not authorized" in rc_str or "bad user name or password" in rc_str:
                            self.auth_failed = True
                            self._mark_offline()
                            try:
                                self.hass.loop.call_soon_threadsafe(
                                    functools.partial(
                                        async_create_issue,
                                        self.hass,
                                        DOMAIN,
                                        f"bad_access_code_{self.serial.lower()}",
                                        is_fixable=False,
                                        severity=IssueSeverity.ERROR,
                                        translation_key="bad_access_code",
                                        translation_placeholders={
                                            "printer_name": self.name,
                                            "serial": self.serial,
                                        },
                                        learn_more_url="https://github.com/everyday3d/bambu-fleet-studio#troubleshooting",
                                    )
                                )
                            except Exception as issue_err:
                                LOGGER.warning("Failed to create bad_access_code issue: %s", issue_err)
                        LOGGER.warning("MQTT connect rc=%s for %s (%s)", rc_val, self.serial, self.host)

                def on_disconnect(cli, userdata, *args):
                    disconnected[0] = True
                    if (time.time() - self.last_seen) > 90.0:
                        self._mark_offline()

                def on_message(cli, userdata, msg):
                    self._touch_online()
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
                    self._tick_odometer(now_ts)
                    if self.online and (now_ts - last_pushall) > 60.0:
                        last_pushall = now_ts
                        self.send_action("pushall")
                    if (now_ts - self.last_seen) > 75.0:
                        self._mark_offline(now_ts)
                        break

                try:
                    client.loop_stop()
                    client.disconnect()
                except Exception:
                    pass

                if self.auth_failed:
                    break

                if self.online:
                    retry_delay = 2.0
                else:
                    retry_delay = min(retry_delay * 2.0, 60.0)

                sleep_iters = max(1, int(retry_delay / 0.5))
                for _ in range(sleep_iters):
                    if self._stop_event.is_set() or self.auth_failed:
                        break
                    time.sleep(0.5)

            except Exception as err:
                self._mark_offline()
                LOGGER.warning("MQTT loop error for %s (%s): %s", self.serial, self.host, err)
                if self.auth_failed:
                    break
                retry_delay = min(retry_delay * 2.0, 60.0)
                sleep_iters = max(1, int(retry_delay / 0.5))
                for _ in range(sleep_iters):
                    if self._stop_event.is_set() or self.auth_failed:
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

        prev_status = self.print_status
        if "gcode_state" in p:
            raw_st = str(p["gcode_state"] or "").strip().lower()
            if raw_st in ("running", "pause", "prepare", "finish", "failed", "idle"):
                self.print_status = raw_st
            elif raw_st:
                self.print_status = "idle" if raw_st == "init" else raw_st

        if "stg_cur" in p:
            self.current_stage = str(p["stg_cur"])

        if "subtask_name" in p and p["subtask_name"]:
            self.task_name = str(p["subtask_name"])
        elif "gcode_file" in p and p["gcode_file"]:
            self.task_name = str(p["gcode_file"])

        if self.task_name and self.task_name != self._active_job_key:
            self._active_job_key = self.task_name
            self._last_job_progress = 0
            self._job_accumulated_m = 0.0
            self._rfid_accumulated_m = 0.0
            self._job_length_m = 0.0
            self._job_weight_g = 0.0

        for w_key in ("weight", "total_weight", "print_weight", "filament_weight"):
            if w_key in p and p[w_key] is not None:
                try:
                    wv = float(p[w_key])
                    if wv > 0:
                        self._job_weight_g = wv
                        self.print_weight = self._fmt_num(wv, 1)
                        break
                except Exception:
                    pass

        for l_key in ("length", "total_length", "print_length", "filament_length"):
            if l_key in p and p[l_key] is not None:
                try:
                    lv = float(p[l_key])
                    if lv > 0:
                        self._job_length_m = (lv / 100.0) if lv > 2500 else lv
                        self.print_length = self._fmt_num(self._job_length_m, 1)
                        break
                except Exception:
                    pass

        if self._job_weight_g > 0 and self._job_length_m <= 0:
            self._job_length_m = round(self._job_weight_g * 0.33, 2)
            self.print_length = self._fmt_num(self._job_length_m, 1)

        prev_progress = self.progress
        if "mc_percent" in p:
            try:
                new_prog = min(100, max(0, int(float(p["mc_percent"]))))
                if self.print_status == "running" and self._job_length_m > 0 and new_prog > self._last_job_progress:
                    delta_pct = new_prog - self._last_job_progress
                    if 0 < delta_pct <= 25:
                        dm = self._job_length_m * (delta_pct / 100.0)
                        self._extruded_meters += dm
                        self._extruded_grams += dm * 3.03
                        self._job_accumulated_m += dm
                        self._odometer_dirty = True
                self.progress = new_prog
                if self.print_status in ("running", "prepare", "pause"):
                    self._last_job_progress = new_prog
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

        # H2D / H2C packed bed temperature (device.bed.info.temp: low word = current, high word = target)
        if isinstance(p.get("device"), dict) and isinstance(p["device"].get("bed"), dict):
            try:
                bed_info = p["device"]["bed"].get("info", {})
                if isinstance(bed_info, dict) and bed_info.get("temp") is not None:
                    bt_packed = int(bed_info["temp"])
                    bt_cur = bt_packed & 0xFFFF
                    bt_tar = (bt_packed >> 16) & 0xFFFF
                    if 0 <= bt_cur < 160:
                        self.bed_temp = str(bt_cur)
                    if 0 <= bt_tar < 160:
                        self.bed_target = str(bt_tar)
            except Exception:
                pass

        # H2C / H2D Dual Extruder & Active Nozzle Telemetry (device.extruder)
        if isinstance(p.get("device"), dict) and isinstance(p["device"].get("extruder"), dict):
            try:
                ext_block = p["device"]["extruder"]
                if ext_block.get("state") is not None:
                    self.active_nozzle_index = (int(ext_block["state"]) >> 4) & 0xF
                ext_info = ext_block.get("info")
                if isinstance(ext_info, list):
                    for entry in ext_info:
                        if not isinstance(entry, dict):
                            continue
                        eid = entry.get("id")
                        if eid in (0, 1) and entry.get("temp") is not None:
                            t_packed = int(entry["temp"])
                            t_cur = t_packed & 0xFFFF
                            t_tar = (t_packed >> 16) & 0xFFFF
                            if 0 <= t_cur < 500:
                                cur_str = str(t_cur)
                                tar_str = str(t_tar if 0 <= t_tar < 500 else 0)
                                if eid == 0:
                                    self.right_nozzle_temp = cur_str
                                    self.right_nozzle_target = tar_str
                                else:
                                    self.left_nozzle_temp = cur_str
                                    self.left_nozzle_target = tar_str
                    act_temp = self.left_nozzle_temp if self.active_nozzle_index == 1 else self.right_nozzle_temp
                    act_tar = self.left_nozzle_target if self.active_nozzle_index == 1 else self.right_nozzle_target
                    if "nozzle_temper" not in p and act_temp != "—":
                        self.nozzle_temp = act_temp
                    if "nozzle_target_temper" not in p:
                        self.nozzle_target = act_tar
            except Exception:
                pass

        # H2C Vortek 6-Slot Automated Hotend Changer Rack & Dual Nozzle Metadata (device.nozzle)
        if isinstance(p.get("device"), dict) and isinstance(p["device"].get("nozzle"), dict):
            try:
                noz_block = p["device"]["nozzle"]
                if noz_block.get("exist") is not None:
                    self.vortek_exist_mask = int(noz_block["exist"])
                if noz_block.get("tar_id") is not None:
                    self.vortek_tar_id = int(noz_block["tar_id"])
                noz_info = noz_block.get("info")
                if isinstance(noz_info, list):
                    for entry in noz_info:
                        if not isinstance(entry, dict):
                            continue
                        nid = entry.get("id")
                        diam_val = entry.get("diameter")
                        tcode_val = str(entry.get("type") or "").strip()
                        if nid in (0, 1):
                            if diam_val is not None:
                                try:
                                    d_str = self._fmt_num(float(diam_val), 1)
                                    if float(diam_val) > 0:
                                        if nid == 0:
                                            self.right_nozzle_size = d_str
                                        else:
                                            self.left_nozzle_size = d_str
                                except Exception:
                                    pass
                            if tcode_val:
                                fl_lbl, mt_lbl = self._decode_nozzle_type_code(tcode_val)
                                combined_lbl = f"{fl_lbl} {mt_lbl}" if fl_lbl != "Standard" else mt_lbl
                                if nid == 0:
                                    self.right_nozzle_type = combined_lbl
                                else:
                                    self.left_nozzle_type = combined_lbl
                        rack_slot_id: Optional[int] = None
                        if isinstance(nid, int) and 16 <= nid <= 21:
                            rack_slot_id = nid
                        elif (
                            isinstance(nid, int)
                            and nid < 16
                            and tcode_val
                            and str(entry.get("sn") or "N/A") != "N/A"
                            and 16 <= self.vortek_tar_id <= 21
                        ):
                            rack_slot_id = self.vortek_tar_id
                        if rack_slot_id is not None:
                            prev_h = self.vortek_hotends.get(rack_slot_id, {})
                            h_diam = prev_h.get("size", "0.4")
                            if diam_val is not None:
                                try:
                                    if float(diam_val) > 0:
                                        h_diam = self._fmt_num(float(diam_val), 1)
                                except Exception:
                                    pass
                            eff_tcode = tcode_val or str(prev_h.get("type_code") or "HS01")
                            fl_lbl, mt_lbl = self._decode_nozzle_type_code(eff_tcode)
                            raw_col = str(entry.get("color_m") or prev_h.get("raw_color") or "").strip()
                            hex_col = f"#{raw_col[:6]}" if len(raw_col) >= 6 and raw_col[:6] != "000000" else str(prev_h.get("color") or "#38bdf8")
                            pt_sec = int(entry.get("p_t", prev_h.get("print_time_sec", 0)) or 0)
                            self.vortek_hotends[rack_slot_id] = {
                                "id": rack_slot_id,
                                "slot": rack_slot_id - 15,
                                "size": h_diam,
                                "type_code": eff_tcode,
                                "flow": fl_lbl,
                                "material": mt_lbl,
                                "serial": str(entry.get("sn") or prev_h.get("serial") or ""),
                                "print_time_sec": pt_sec,
                                "hours": self._fmt_num(pt_sec / 3600.0, 1),
                                "color": hex_col,
                                "raw_color": raw_col,
                            }
                    act_sz = self.left_nozzle_size if self.active_nozzle_index == 1 else self.right_nozzle_size
                    act_tp = self.left_nozzle_type if self.active_nozzle_index == 1 else self.right_nozzle_type
                    if "nozzle_diameter" not in p and act_sz:
                        self.nozzle_size = act_sz
                    if "nozzle_type" not in p and act_tp:
                        self.nozzle_type = act_tp.lower()
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

        prev_hms_count = len(self.hms_errors)
        prev_print_error = self.print_error
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

                    if remain is not None:
                        prev_rem = self._last_tray_remains.get(global_tray_id)
                        self._last_tray_remains[global_tray_id] = remain
                        if remain > 25:
                            self._low_spool_alerted.discard(global_tray_id)
                        if is_active and self.print_status == "running" and prev_rem is not None:
                            drop = prev_rem - remain
                            if 1 <= drop <= 5:
                                self._rfid_accumulated_m += drop * 3.30
                                if self._rfid_accumulated_m > self._job_accumulated_m:
                                    diff_m = self._rfid_accumulated_m - self._job_accumulated_m
                                    self._extruded_meters += diff_m
                                    self._extruded_grams += diff_m * 3.03
                                    self._job_accumulated_m += diff_m
                                    self._odometer_dirty = True
                        if (
                            is_active
                            and not is_empty
                            and self.print_status in ("running", "prepare")
                            and 0 < remain <= 25
                            and global_tray_id not in self._low_spool_alerted
                        ):
                            try:
                                mgr_ref = self.hass.data.get(DOMAIN, {}).get("manager")
                                thresh = int((mgr_ref.notifications if mgr_ref else {}).get("low_spool_threshold_pct", 15) or 15)
                            except Exception:
                                thresh = 15
                            if remain <= thresh:
                                self._low_spool_alerted.add(global_tray_id)
                                self._emit_runtime_event(
                                    "low_spool_alert",
                                    {
                                        "slot_code": f"{bank_letter}{slot_num}",
                                        "name": t_sub or t_type or "PLA",
                                        "type": t_type or "PLA",
                                        "remain": remain,
                                    },
                                )

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

        self._tick_odometer(
            time.time(),
            force_save=(prev_status == "running" and self.print_status in ("finish", "idle", "failed", "pause")),
        )

        # Trigger standalone notification / automation hooks on status transitions, progress changes, or new HMS faults
        if prev_status != self.print_status and self.print_status in ("prepare", "running", "pause", "finish", "failed", "idle"):
            self._emit_runtime_event("status_change", {"prev_status": prev_status, "new_status": self.print_status})

        if self.print_status == "running" and self.progress != prev_progress and 0 < self.progress < 100:
            self._emit_runtime_event("progress_change", {"progress": self.progress, "prev_progress": prev_progress})

        if (prev_status in ("running", "prepare", "pause") and self.print_status == "finish") or (
            self.print_status == "running" and prev_progress < 100 and self.progress == 100
        ):
            self._emit_runtime_event("print_complete")
        elif (
            (prev_status in ("running", "prepare", "pause") and self.print_status == "failed")
            or (len(self.hms_errors) > prev_hms_count and len(self.hms_errors) > 0)
            or (self.print_error != 0 and self.print_error != prev_print_error)
        ):
            self._emit_runtime_event("hms_error")

    def _emit_runtime_event(self, event_type: str, extra: Optional[dict[str, Any]] = None) -> None:
        """Schedule a standalone notification or automation action on the Home Assistant event loop."""
        try:
            mgr = self.hass.data.get(DOMAIN, {}).get("manager")
            if mgr and hasattr(mgr, "async_handle_printer_event"):
                self.hass.loop.call_soon_threadsafe(
                    lambda: self.hass.async_create_task(mgr.async_handle_printer_event(self, event_type, extra))
                )
        except Exception as err:
            LOGGER.debug("Failed to schedule runtime event %s for %s: %s", event_type, self.serial, err)

    def _port6000_cam_loop(self) -> None:
        """Background TCP Port 6000 TLS binary JPEG stream reader for A1, A1 Mini, P1P, P1S."""
        while not self._stop_event.is_set():
            if self.auth_failed:
                break
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
                                        self._touch_online()
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

    def get_job_filament_usage(self) -> tuple[str, str]:
        """Return (grams_str, meters_str) for the current or most recent print job, with RFID/odometer fallbacks."""
        grams = float(self._job_weight_g or 0.0)
        meters = float(self._job_length_m or 0.0)
        if grams <= 0.0:
            try:
                pw = float(self.print_weight)
                if pw > 0.0:
                    grams = pw
            except Exception:
                pass
        if meters <= 0.0:
            try:
                pl = float(self.print_length)
                if pl > 0.0:
                    meters = pl
            except Exception:
                pass
        if meters <= 0.0 and self._job_accumulated_m > 0.0:
            meters = self._job_accumulated_m
        if meters <= 0.0 and self._rfid_accumulated_m > 0.0:
            meters = self._rfid_accumulated_m
        if grams <= 0.0 and meters > 0.0:
            grams = meters * 3.03
        if meters <= 0.0 and grams > 0.0:
            meters = grams * 0.33
        if grams <= 0.0 and (self.progress > 0 or self.print_status in ("running", "finish", "pause")):
            eff_prog = max(1, int(self.progress or 100))
            grams = round(eff_prog * 0.42, 1)
            meters = round(grams * 0.33, 2)
        if grams > 0.0:
            self.print_weight = self._fmt_num(grams, 1)
        if meters > 0.0:
            self.print_length = self._fmt_num(meters, 1)
        g_str = self._fmt_num(grams, 1) if grams > 0.0 else "0.0"
        m_str = self._fmt_num(meters, 1) if meters > 0.0 else "0.0"
        return g_str, m_str

    def reset_maintenance_item(self, item_key: str) -> bool:
        """Reset a preventative maintenance baseline to current odometer hours and meters."""
        valid_keys = ("rods", "leadscrews", "extruder", "filter")
        clean_key = str(item_key or "all").strip().lower()
        if clean_key != "all" and clean_key not in valid_keys:
            return False
        targets = valid_keys if clean_key == "all" else (clean_key,)
        snap = {
            "hours": round(float(self._usage_hours_val or 0.0), 1),
            "meters": round(float(self._extruded_meters or 0.0), 2),
            "ts": round(time.time(), 1),
        }
        for k in targets:
            self.maintenance_log[k] = dict(snap)
        self._config_ref["maintenance_log"] = self.maintenance_log
        return True

    def _sign_camera_url(self, path: str) -> str:
        """Return a signed Home Assistant HTTP path (4-hour TTL) for camera endpoints."""
        try:
            sep = "&" if "?" in path else "?"
            target = f"{path}{sep}_ts={int(time.time() * 1000)}"
            return async_sign_path(self.hass, target, timedelta(hours=4))
        except Exception:
            return path

    def to_status_dict(self) -> dict[str, Any]:
        """Serialize runtime state for /api/bambu_fleet_studio/status."""
        recent_cam = self._last_jpeg_ts > 0 and (time.monotonic() - self._last_jpeg_ts) < 15.0
        is_online = bool(self.online or recent_cam)
        eff_last_online = time.time() if is_online else (self.last_online_ts if self.last_online_ts > 0 else self.last_seen)
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
        self.get_job_filament_usage()
        is_dual_nozzle = self.model in ("H2C", "H2D", "H2DPRO") or (
            self.left_nozzle_temp != "—" and self.right_nozzle_temp != "—"
        )
        is_nozzle_changer = (
            self.model == "H2C"
            or self.vortek_exist_mask >= (1 << 16)
            or len(self.vortek_hotends) > 0
        )
        eff_right_temp = self.right_nozzle_temp if self.right_nozzle_temp != "—" else self.nozzle_temp
        eff_right_target = self.right_nozzle_target if self.right_nozzle_temp != "—" else self.nozzle_target
        eff_left_temp = self.left_nozzle_temp if self.left_nozzle_temp != "—" else (self.nozzle_temp if is_dual_nozzle else "—")
        eff_left_target = self.left_nozzle_target if self.left_nozzle_temp != "—" else "0"
        mounted_vortek_slot = (self.vortek_tar_id - 15) if 16 <= self.vortek_tar_id <= 21 else (1 if is_nozzle_changer else None)

        vortek_rack: list[dict[str, Any]] = []
        if is_nozzle_changer:
            for sid in range(16, 22):
                slot_num = sid - 15
                h_data = self.vortek_hotends.get(sid, {})
                is_mounted = (sid == self.vortek_tar_id) or (self.vortek_tar_id == 0 and slot_num == 1 and self.vortek_exist_mask == 0)
                is_occupied = is_mounted or bool(self.vortek_exist_mask & (1 << sid)) or bool(h_data) or (self.vortek_exist_mask == 0)
                status_str = "mounted" if is_mounted else ("docked" if is_occupied else "empty")
                vortek_rack.append({
                    "slot": slot_num,
                    "slotCode": f"R{slot_num}",
                    "status": status_str,
                    "mounted": is_mounted,
                    "occupied": is_occupied,
                    "size": str(h_data.get("size") or (self.right_nozzle_size if is_mounted else "0.4")),
                    "flow": str(h_data.get("flow") or ("High-Flow" if slot_num in (1, 2) else "Standard")),
                    "material": str(h_data.get("material") or "Hardened Steel"),
                    "hours": str(h_data.get("hours") or "0.0"),
                    "color": str(h_data.get("color") or "#38bdf8"),
                })

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
            "lastOnlineTs": round(eff_last_online, 1) if eff_last_online > 0 else 0,
            "authFailed": self.auth_failed,
            "printStatus": p_status,
            "currentStage": c_stage,
            "progress": self.progress,
            "nozzleTemp": self.nozzle_temp,
            "nozzleTarget": self.nozzle_target,
            "isDualNozzle": is_dual_nozzle,
            "isNozzleChanger": is_nozzle_changer,
            "activeNozzleIndex": self.active_nozzle_index,
            "leftNozzle": {
                "temp": eff_left_temp,
                "target": eff_left_target,
                "size": self.left_nozzle_size or self.nozzle_size,
                "type": self.left_nozzle_type or "Hardened Steel",
                "active": self.active_nozzle_index == 1,
            },
            "rightNozzle": {
                "temp": eff_right_temp,
                "target": eff_right_target,
                "size": self.right_nozzle_size or self.nozzle_size,
                "type": self.right_nozzle_type or "Hardened Steel",
                "active": self.active_nozzle_index == 0,
                "mountedSlot": mounted_vortek_slot,
            },
            "vortekRack": vortek_rack,
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
            "extrudedMeters": round(self._extruded_meters, 1),
            "extrudedGrams": round(self._extruded_grams, 0),
            "extrudedSpools": round(self._extruded_meters / 330.0, 2),
            "maintenanceLog": self.maintenance_log,
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
            "cameraPic": self._sign_camera_url(f"/api/bambu_fleet_studio/camera/{self.serial}"),
            "cameraStreamUrl": self._sign_camera_url(f"/api/bambu_fleet_studio/camera_stream/{self.serial}"),
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
        self._rgb_auto_off_task: Optional[asyncio.Task] = None
        self._last_wled_progress_pushed: int = -1
        self.notifications: dict[str, Any] = {
            "notify_service": "",
            "target_printer": "__ALL__",
            "print_complete": True,
            "hms_error": True,
            "auto_light_off": True,
            "auto_light_off_delay_sec": 300,
            "rgb_light_sync": False,
            "rgb_light_entity": "",
            "tts_voice_alert": False,
            "tts_media_player": "",
            "tts_quiet_hours": True,
            "safe_cooldown_plug_off": False,
            "cooldown_switch_entity": "",
            "cooldown_target_temp": 50,
            "low_spool_alert": True,
            "low_spool_threshold_pct": 15,
        }
        self._release_cache: dict[str, Any] = {
            "current_version": VERSION,
            "latest_version": VERSION,
            "update_available": False,
            "release_url": GITHUB_RELEASES_WEB,
            "release_name": f"v{VERSION}",
            "published_at": "",
            "checked_at": 0.0,
        }
        self._release_check_in_flight: bool = False

    def _fetch_github_release_sync(self) -> Optional[dict[str, Any]]:
        """Fetch latest release metadata from GitHub API."""
        try:
            req = urllib.request.Request(
                GITHUB_RELEASES_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"BambuFleetStudio-HA/{VERSION}",
                },
            )
            with urllib.request.urlopen(req, timeout=4.5) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except Exception:
            return None

    async def async_check_github_release(self, force: bool = False) -> dict[str, Any]:
        """Check GitHub Releases for a newer version of Bambu Lab Fleet Studio."""
        now = time.time()
        if not force and (now - float(self._release_cache.get("checked_at") or 0.0) < 1800):
            return dict(self._release_cache)
        if self._release_check_in_flight:
            return dict(self._release_cache)
        self._release_check_in_flight = True
        try:
            data = await self.hass.async_add_executor_job(self._fetch_github_release_sync)
            if isinstance(data, dict) and data.get("tag_name"):
                raw_tag = str(data.get("tag_name") or "").strip()
                clean_ver = re.sub(r"^[vV]+", "", raw_tag).strip() or VERSION
                is_newer = _parse_semver(clean_ver) > _parse_semver(VERSION)
                self._release_cache = {
                    "current_version": VERSION,
                    "latest_version": clean_ver,
                    "update_available": bool(is_newer),
                    "release_url": str(data.get("html_url") or GITHUB_RELEASES_WEB),
                    "release_name": str(data.get("name") or raw_tag),
                    "published_at": str(data.get("published_at") or ""),
                    "checked_at": round(now, 1),
                }
            else:
                self._release_cache["checked_at"] = round(now, 1)
        except Exception:
            pass
        finally:
            self._release_check_in_flight = False
        return dict(self._release_cache)

    def get_version_info(self) -> dict[str, Any]:
        """Return cached version & update status, scheduling a background refresh if stale."""
        now = time.time()
        if (now - float(self._release_cache.get("checked_at") or 0.0) > 1800) and not self._release_check_in_flight:
            try:
                self.hass.async_create_task(self.async_check_github_release())
            except Exception:
                pass
        return dict(self._release_cache)

    def _resolve_default_notify_service(self) -> str:
        """Return the configured notify_service or auto-detect the primary mobile_app_* service."""
        cur = str(self.notifications.get("notify_service") or "").strip()
        if cur and cur not in ("notify.send_message", "send_message"):
            return cur
        try:
            notify_svcs = (self.hass.services.async_services() or {}).get("notify", {})
            for svc_key in notify_svcs:
                if str(svc_key).startswith("mobile_app_"):
                    resolved = f"notify.{svc_key}"
                    self.notifications["notify_service"] = resolved
                    return resolved
            for st in self.hass.states.async_all("notify"):
                slug = st.entity_id.split(".", 1)[1]
                if f"mobile_app_{slug}" in notify_svcs:
                    resolved = f"notify.mobile_app_{slug}"
                    self.notifications["notify_service"] = resolved
                    return resolved
                resolved = st.entity_id
                self.notifications["notify_service"] = resolved
                return resolved
        except Exception:
            pass
        return cur

    def _schedule_save_from_thread(self) -> None:
        """Schedule an async store save from a background runtime thread."""
        try:
            self.hass.loop.call_soon_threadsafe(
                lambda: self.hass.async_create_task(self.async_save())
            )
        except Exception:
            pass

    async def async_initialize(self) -> None:
        """Load saved printers and notification settings from storage."""
        stored = await self.store.async_load()
        if isinstance(stored, dict):
            if isinstance(stored.get("printers"), dict):
                self.configs = stored["printers"]
            if isinstance(stored.get("notifications"), dict):
                self.notifications.update(stored["notifications"])

        changed = False
        for sn, cfg in list(self.configs.items()):
            if not cfg.get("last_online_ts"):
                mod_norm = normalize_model_code(str(cfg.get("model", "")), sn).lower()
                pfx = f"{mod_norm}_{sn.lower()}"
                for cand_ent in (f"binary_sensor.{pfx}_online", f"sensor.{pfx}_print_status"):
                    st_obj = self.hass.states.get(cand_ent)
                    if st_obj and getattr(st_obj, "last_changed", None):
                        try:
                            cfg["last_online_ts"] = round(float(st_obj.last_changed.timestamp()), 1)
                            changed = True
                            break
                        except Exception:
                            pass

        # Auto-resolve default mobile_app notification service if unset or set to invalid send_message
        prev_svc = self.notifications.get("notify_service", "")
        resolved_svc = self._resolve_default_notify_service()
        if resolved_svc and resolved_svc != prev_svc:
            changed = True

        # Pre-select light.wled if available and rgb_light_entity is unset
        if not self.notifications.get("rgb_light_entity") and self.hass.states.get("light.wled"):
            self.notifications["rgb_light_entity"] = "light.wled"
            changed = True

        if changed:
            await self.async_save()

        for sn, cfg in list(self.configs.items()):
            await self.async_start_printer(sn, cfg)

    async def async_save(self) -> None:
        """Persist printer configs and notification settings to .storage/bambu_fleet_studio.printers."""
        await self.store.async_save({
            "printers": self.configs,
            "notifications": self.notifications,
        })

    async def async_update_notifications(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Update and persist standalone notification & automation preferences."""
        for str_key in ("notify_service", "target_printer", "rgb_light_entity", "tts_media_player", "cooldown_switch_entity"):
            if str_key in payload:
                default_val = "__ALL__" if str_key == "target_printer" else ""
                val = str(payload.get(str_key) or default_val).strip()
                if str_key == "notify_service":
                    if val in ("", "notify.send_message", "send_message"):
                        val = self._resolve_default_notify_service()
                    elif not (val.startswith("notify.") or val.startswith("persistent_notification.")):
                        continue
                elif str_key == "cooldown_switch_entity":
                    if val and not (val.startswith("switch.") or val.startswith("input_boolean.")):
                        continue
                elif str_key == "rgb_light_entity":
                    if val and not val.startswith("light."):
                        continue
                elif str_key == "tts_media_player":
                    if val and not val.startswith("media_player."):
                        continue
                self.notifications[str_key] = val
        for bool_key in (
            "print_complete",
            "hms_error",
            "auto_light_off",
            "rgb_light_sync",
            "tts_voice_alert",
            "tts_quiet_hours",
            "safe_cooldown_plug_off",
            "low_spool_alert",
        ):
            if bool_key in payload:
                self.notifications[bool_key] = bool(payload[bool_key])
        if "auto_light_off_delay_sec" in payload:
            try:
                self.notifications["auto_light_off_delay_sec"] = max(10, int(payload["auto_light_off_delay_sec"]))
            except Exception:
                pass
        if "cooldown_target_temp" in payload:
            try:
                self.notifications["cooldown_target_temp"] = max(35, min(70, int(payload["cooldown_target_temp"])))
            except Exception:
                pass
        if "low_spool_threshold_pct" in payload:
            try:
                self.notifications["low_spool_threshold_pct"] = max(5, min(50, int(payload["low_spool_threshold_pct"])))
            except Exception:
                pass
        await self.async_save()
        return dict(self.notifications)

    async def async_send_notification(
        self,
        title: str,
        message: str,
        extra_data: Optional[dict[str, Any]] = None,
        service_override: str = "",
    ) -> bool:
        """Call the configured Home Assistant notify service (supports notify.mobile_app_* & notify.* entities)."""
        svc_full = (service_override or str(self.notifications.get("notify_service") or "")).strip()
        if not svc_full or svc_full in ("notify.send_message", "send_message"):
            svc_full = self._resolve_default_notify_service()
        if not svc_full:
            return False
        try:
            if svc_full in ("notify.persistent_notification", "persistent_notification.create"):
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {"title": title, "message": message},
                )
                return True

            domain, svc_name = svc_full.split(".", 1) if "." in svc_full else ("notify", svc_full)
            if domain not in ("notify", "persistent_notification"):
                LOGGER.warning("Refusing to call unapproved domain in async_send_notification: %s", domain)
                return False

            if not self.hass.services.has_service(domain, svc_name):
                # If user selected a notify.<slug> entity name that maps to mobile_app_<slug>, prefer mobile_app_<slug>
                if domain == "notify" and self.hass.services.has_service("notify", f"mobile_app_{svc_name}"):
                    svc_name = f"mobile_app_{svc_name}"
                elif domain == "notify" and self.hass.states.get(f"notify.{svc_name}") and self.hass.services.has_service("notify", "send_message"):
                    await self.hass.services.async_call(
                        "notify",
                        "send_message",
                        {"entity_id": f"notify.{svc_name}", "title": title, "message": message},
                    )
                    return True
                else:
                    LOGGER.warning("Notification service %s.%s does not exist", domain, svc_name)
                    return False

            svc_payload: dict[str, Any] = {"title": title, "message": message}
            if extra_data:
                svc_payload["data"] = extra_data
            await self.hass.services.async_call(domain, svc_name, svc_payload)
            return True
        except Exception as err:
            LOGGER.warning("Failed to call notification service %s: %s", svc_full, err)
            return False

    def _resolve_wled_ip(self, light_ent: str) -> str:
        """Resolve the local IP address of a WLED controller from sensor.<slug>_ip or device registry."""
        slug = light_ent.split(".", 1)[1] if "." in light_ent else light_ent
        for cand_sensor in (f"sensor.{slug}_ip", "sensor.wled_ip"):
            st = self.hass.states.get(cand_sensor)
            if st and st.state and re.match(r"^\d+\.\d+\.\d+\.\d+$", str(st.state).strip()):
                return str(st.state).strip()
        return ""

    @staticmethod
    def _post_wled_json_sync(wled_ip: str, payload: dict[str, Any]) -> bool:
        """Send a direct HTTP JSON state update to a WLED controller (/json/state)."""
        if not wled_ip:
            return False
        try:
            req = urllib.request.Request(
                f"http://{wled_ip}/json/state",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _cancel_rgb_auto_off(self) -> None:
        """Cancel any pending 5-minute WLED / RGB auto-shutoff timer."""
        if self._rgb_auto_off_task and not self._rgb_auto_off_task.done():
            self._rgb_auto_off_task.cancel()
        self._rgb_auto_off_task = None

    def _schedule_rgb_auto_off(self, light_ent: str, delay_sec: int = 300) -> None:
        """Schedule an automatic shutoff for WLED / RGB status light (default 5 minutes = 300s after completion)."""
        self._cancel_rgb_auto_off()

        async def _auto_off_coro() -> None:
            try:
                await asyncio.sleep(delay_sec)
                any_printing = any(
                    r.online and r.print_status in ("running", "prepare")
                    for r in self.runtimes.values()
                )
                if not any_printing:
                    await self.async_sync_rgb_light("off", light_ent)
            except asyncio.CancelledError:
                pass
            except Exception as err:
                LOGGER.debug("RGB auto-off error for %s: %s", light_ent, err)

        self._rgb_auto_off_task = self.hass.async_create_task(_auto_off_coro())

    async def async_sync_rgb_light(
        self,
        state_key: str,
        light_entity_override: str = "",
        progress: Optional[int] = None,
    ) -> bool:
        """Sync smart RGB light or WLED strip.

        When a WLED entity is selected:
        - Operates as a live Print Progress Bar (0% -> 100% strip length via WLED 'Percent' effect fx=98 + intensity).
        - At 100% / finish: flashes Emerald Green 3 times, then goes 100% Solid Emerald Green across all LEDs,
          with a 5-minute (300s) automatic shutoff timer on completion.
        """
        light_ent = (light_entity_override or str(self.notifications.get("rgb_light_entity") or "")).strip()
        if not light_ent:
            return False

        st_obj = self.hass.states.get(light_ent)
        effect_list = (st_obj.attributes.get("effect_list") or []) if (st_obj and st_obj.attributes) else []
        slug = light_ent.split(".", 1)[1] if "." in light_ent else light_ent
        intensity_ent = f"number.{slug}_intensity" if self.hass.states.get(f"number.{slug}_intensity") else (
            "number.wled_intensity" if self.hass.states.get("number.wled_intensity") else ""
        )
        is_wled = ("wled" in light_ent.lower()) or ("Percent" in effect_list) or bool(intensity_ent)
        wled_ip = self._resolve_wled_ip(light_ent) if is_wled else ""

        color_map = {
            "prepare": ([245, 158, 11], 85),
            "running": ([14, 165, 233], 90),
            "progress": ([14, 165, 233], 90),
            "finish": ([16, 185, 129], 100),
            "pause": ([239, 68, 68], 100),
            "failed": ([239, 68, 68], 100),
            "hms_error": ([239, 68, 68], 100),
        }

        try:
            if state_key in ("off", "idle"):
                self._cancel_rgb_auto_off()
                if wled_ip:
                    await self.hass.async_add_executor_job(self._post_wled_json_sync, wled_ip, {"on": False})
                await self.hass.services.async_call("light", "turn_off", {"entity_id": light_ent})
                return True

            self._cancel_rgb_auto_off()

            is_demo_bar = (state_key == "test_wled_bar")
            if is_wled and is_demo_bar:
                # Live interactive demo of the WLED progress bar (20% -> 45% -> 70% -> 95% -> 100% Flash 3x -> Solid Green)
                for demo_pct in (20, 45, 70, 95):
                    if wled_ip:
                        await self.hass.async_add_executor_job(
                            self._post_wled_json_sync,
                            wled_ip,
                            {
                                "on": True,
                                "bri": 230,
                                "seg": [{"id": 0, "fx": 98, "sx": 128, "ix": demo_pct, "col": [[14, 165, 233], [0, 0, 0], [0, 0, 0]]}],
                            },
                        )
                    await self.hass.services.async_call(
                        "light",
                        "turn_on",
                        {"entity_id": light_ent, "rgb_color": [14, 165, 233], "brightness_pct": 90, "effect": "Percent"},
                    )
                    if intensity_ent:
                        await self.hass.services.async_call("number", "set_value", {"entity_id": intensity_ent, "value": demo_pct})
                    await asyncio.sleep(0.65)
                state_key = "finish"
                progress = 100

            if is_wled and state_key in ("prepare", "running", "progress"):
                rgb, bri = color_map.get(state_key, ([14, 165, 233], 90))
                bar_pct = max(3, min(99, int(progress if progress is not None else (5 if state_key == "prepare" else 10))))
                if wled_ip:
                    await self.hass.async_add_executor_job(
                        self._post_wled_json_sync,
                        wled_ip,
                        {
                            "on": True,
                            "bri": int(round(bri * 2.55)),
                            "seg": [{"id": 0, "fx": 98, "sx": 128, "ix": bar_pct, "col": [rgb, [0, 0, 0], [0, 0, 0]]}],
                        },
                    )
                await self.hass.services.async_call(
                    "light",
                    "turn_on",
                    {"entity_id": light_ent, "rgb_color": rgb, "brightness_pct": bri, "effect": "Percent"},
                )
                if intensity_ent:
                    await self.hass.services.async_call(
                        "number",
                        "set_value",
                        {"entity_id": intensity_ent, "value": bar_pct},
                    )
                return True

            if state_key == "finish":
                if is_wled:
                    # 1. Reach 100% progress bar fill
                    if wled_ip:
                        await self.hass.async_add_executor_job(
                            self._post_wled_json_sync,
                            wled_ip,
                            {
                                "on": True,
                                "bri": 255,
                                "seg": [{"id": 0, "fx": 98, "sx": 128, "ix": 100, "col": [[16, 185, 129], [0, 0, 0], [0, 0, 0]]}],
                            },
                        )
                    await self.hass.services.async_call(
                        "light",
                        "turn_on",
                        {"entity_id": light_ent, "rgb_color": [16, 185, 129], "brightness_pct": 100, "effect": "Solid"},
                    )
                    if intensity_ent:
                        await self.hass.services.async_call("number", "set_value", {"entity_id": intensity_ent, "value": 100})
                    await asyncio.sleep(0.35)

                    # 2. Flash 3 times at 100% completion
                    for _ in range(3):
                        if wled_ip:
                            await self.hass.async_add_executor_job(self._post_wled_json_sync, wled_ip, {"on": False})
                        await self.hass.services.async_call("light", "turn_off", {"entity_id": light_ent})
                        await asyncio.sleep(0.35)
                        if wled_ip:
                            await self.hass.async_add_executor_job(
                                self._post_wled_json_sync,
                                wled_ip,
                                {
                                    "on": True,
                                    "bri": 255,
                                    "seg": [{"id": 0, "fx": 0, "sx": 128, "ix": 100, "col": [[16, 185, 129], [16, 185, 129], [0, 0, 0]]}],
                                },
                            )
                        await self.hass.services.async_call(
                            "light",
                            "turn_on",
                            {"entity_id": light_ent, "rgb_color": [16, 185, 129], "brightness_pct": 100, "effect": "Solid"},
                        )
                        await asyncio.sleep(0.45)

                    # 3. Hold Solid Emerald Green across all 100% of strip
                    if wled_ip:
                        await self.hass.async_add_executor_job(
                            self._post_wled_json_sync,
                            wled_ip,
                            {
                                "on": True,
                                "bri": 255,
                                "seg": [{"id": 0, "fx": 0, "sx": 128, "ix": 100, "col": [[16, 185, 129], [16, 185, 129], [0, 0, 0]]}],
                            },
                        )
                    await self.hass.services.async_call(
                        "light",
                        "turn_on",
                        {"entity_id": light_ent, "rgb_color": [16, 185, 129], "brightness_pct": 100, "effect": "Solid"},
                    )
                else:
                    await self.hass.services.async_call(
                        "light",
                        "turn_on",
                        {"entity_id": light_ent, "rgb_color": [16, 185, 129], "brightness_pct": 100},
                    )

                if is_demo_bar:
                    active_rt = next(
                        (r for r in self.runtimes.values() if r.online and r.print_status == "running"),
                        None,
                    )
                    if active_rt:
                        async def _restore_active_bar() -> None:
                            await asyncio.sleep(3.5)
                            if active_rt.online and active_rt.print_status == "running":
                                await self.async_sync_rgb_light("running", light_ent, progress=active_rt.progress)

                        self.hass.async_create_task(_restore_active_bar())
                        return True

                # 4. Schedule 5-minute (300s) auto-shutoff on completion
                self._schedule_rgb_auto_off(light_ent, delay_sec=300)
                return True

            rgb, bri = color_map.get(state_key, ([14, 165, 233], 90))
            if is_wled and wled_ip:
                await self.hass.async_add_executor_job(
                    self._post_wled_json_sync,
                    wled_ip,
                    {
                        "on": True,
                        "bri": int(round(bri * 2.55)),
                        "seg": [{"id": 0, "fx": 0, "sx": 128, "ix": 100, "col": [rgb, rgb, [0, 0, 0]]}],
                    },
                )
            await self.hass.services.async_call(
                "light",
                "turn_on",
                {"entity_id": light_ent, "rgb_color": rgb, "brightness_pct": bri},
            )
            return True
        except Exception as err:
            LOGGER.warning("Failed to sync RGB status light %s: %s", light_ent, err)
            return False

    async def async_speak_tts(self, text: str, media_player_override: str = "", force: bool = False) -> bool:
        """Announce a voice message on a Home Assistant media_player entity using available TTS services."""
        mp_ent = (media_player_override or str(self.notifications.get("tts_media_player") or "")).strip()
        if not mp_ent or not text:
            return False
        if not force and self.notifications.get("tts_quiet_hours", True):
            local_hr = time.localtime().tm_hour
            if local_hr >= 22 or local_hr < 8:
                return False
        try:
            tts_services = (self.hass.services.async_services() or {}).get("tts", {})
            for tts_svc in ("google_translate_say", "cloud_say", "piper_say", "say"):
                if tts_svc in tts_services:
                    await self.hass.services.async_call(
                        "tts",
                        tts_svc,
                        {"entity_id": mp_ent, "message": text},
                    )
                    return True
            # Fallback to modern tts.speak if a tts.* entity exists
            tts_entities = [st.entity_id for st in self.hass.states.async_all("tts")]
            if tts_entities and "speak" in tts_services:
                await self.hass.services.async_call(
                    "tts",
                    "speak",
                    {
                        "entity_id": tts_entities[0],
                        "media_player_entity_id": mp_ent,
                        "message": text,
                    },
                )
                return True
            return False
        except Exception as err:
            LOGGER.warning("Failed to speak TTS on %s: %s", mp_ent, err)
            return False

    async def _build_printer_notification_data(
        self,
        rt: BambuPrinterRuntime,
        include_snapshot: bool = True,
        high_priority: bool = False,
    ) -> dict[str, Any]:
        """Build iOS/Android Companion App notification data with deep-link to target printer card, camera action button, and snapshot."""
        card_url = f"/bambu-fleet/fleet-overview?printer={rt.serial}&prefix={rt.prefix}#printer-card-{rt.prefix}"
        cam_url_deep = f"/bambu-fleet/fleet-overview?printer={rt.serial}&prefix={rt.prefix}&camera=1#printer-card-{rt.prefix}"
        data: dict[str, Any] = {
            "url": card_url,
            "clickAction": card_url,
            "group": f"bambu-fleet-{rt.prefix}",
            "tag": f"bambu-fleet-{rt.prefix}-{int(time.time())}",
            "push": {
                "sound": "default",
                "interruption-level": "critical" if high_priority else "time-sensitive",
            },
            "actions": [
                {
                    "action": "URI",
                    "title": f"🎯 {rt.name} Card",
                    "uri": card_url,
                },
                {
                    "action": "URI",
                    "title": "📹 Live Camera",
                    "uri": cam_url_deep,
                },
            ],
        }
        if high_priority:
            data["ttl"] = 0
            data["priority"] = "high"
            data["importance"] = "high"
        # Note: Do not attach relative /api/... image URLs when Home Assistant external_url is unset or stale
        # Nabu Casa cloudhooks exist, as iOS NotificationServiceExtension resolves relative paths against
        # https://hooks.nabu.casa/api/... and displays an HTTP 404 attachment error banner.
        # Users can tap the notification or '📹 Live Camera' action button to open the live stream directly.
        if include_snapshot and self.notifications.get("attach_snapshot_url") and getattr(self.hass.config, "external_url", None):
            if rt._last_jpeg is None and rt.online:
                try:
                    await self.hass.async_add_executor_job(rt.get_camera_jpeg)
                except Exception:
                    pass
            if rt._last_jpeg is not None:
                cam_path = f"/api/bambu_fleet_studio/camera/{rt.serial}?_ts={int(time.time() * 1000)}"
                try:
                    signed_path = async_sign_path(self.hass, cam_path, timedelta(hours=24))
                except Exception:
                    signed_path = cam_path
                if getattr(self.hass.config, "external_url", None):
                    ext_base = str(self.hass.config.external_url).rstrip("/")
                    data["image"] = f"{ext_base}{signed_path}"
                else:
                    data["image"] = signed_path
        return data

    async def async_handle_printer_event(
        self,
        rt: BambuPrinterRuntime,
        event_type: str,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        """Execute standalone notifications, WLED/RGB progress bar sync, TTS voice, low spool alerts, and safe cooldown power-off."""
        extra_dict = extra or {}
        grams_str, meters_str = rt.get_job_filament_usage()
        try:
            self.hass.bus.async_fire(
                "bambu_fleet_studio_printer_event",
                {
                    "serial": rt.serial,
                    "prefix": rt.prefix,
                    "name": rt.name,
                    "event_type": event_type,
                    "print_status": rt.print_status,
                    "progress": rt.progress,
                    "task_name": rt.task_name,
                    "print_weight": grams_str,
                    "print_length": meters_str,
                    "current_stage": rt.current_stage,
                    "nozzle_temp": rt.nozzle_temp,
                    **extra_dict,
                },
            )
        except Exception:
            pass

        target = str(self.notifications.get("target_printer") or "__ALL__").strip().upper()
        if target not in ("__ALL__", "", rt.serial.upper(), rt.prefix.upper()):
            return

        if event_type == "status_change":
            new_st = str(extra_dict.get("new_status") or rt.print_status).lower()
            if self.notifications.get("rgb_light_sync") and self.notifications.get("rgb_light_entity"):
                if new_st in ("prepare", "running", "pause", "failed"):
                    await self.async_sync_rgb_light(new_st, progress=rt.progress)

        elif event_type == "progress_change":
            if self.notifications.get("rgb_light_sync") and self.notifications.get("rgb_light_entity"):
                prog = int(extra_dict.get("progress", rt.progress) or 0)
                if 0 < prog < 100 and prog != self._last_wled_progress_pushed:
                    self._last_wled_progress_pushed = prog
                    await self.async_sync_rgb_light("running", progress=prog)

        elif event_type == "print_complete":
            self._last_wled_progress_pushed = 100
            if self.notifications.get("print_complete", True):
                snap_extra = await self._build_printer_notification_data(rt, include_snapshot=True, high_priority=False)
                await self.async_send_notification(
                    title=f"✅ Print Complete — {rt.name}",
                    message=(
                        f"Job '{rt.task_name}' finished (100%)! "
                        f"⚖️ Filament Used: {grams_str}g ({meters_str}m) • Tap to open {rt.name} card."
                    ),
                    extra_data=snap_extra,
                )
            if self.notifications.get("rgb_light_sync") and self.notifications.get("rgb_light_entity"):
                await self.async_sync_rgb_light("finish", progress=100)

            if self.notifications.get("tts_voice_alert") and self.notifications.get("tts_media_player"):
                await self.async_speak_tts(
                    f"Print complete on {rt.name}. Job {rt.task_name} finished using {grams_str} grams of filament."
                )

            if self.notifications.get("auto_light_off", True):
                delay_sec = int(self.notifications.get("auto_light_off_delay_sec", 300) or 300)

                async def _delayed_light_off() -> None:
                    await asyncio.sleep(delay_sec)
                    if rt.print_status in ("finish", "idle") and rt.light_on:
                        await self.hass.async_add_executor_job(rt.send_action, "light_off")

                self.hass.async_create_task(_delayed_light_off())

            if self.notifications.get("safe_cooldown_plug_off"):
                plug_ent = str(
                    (rt.smart_plug or {}).get("switch_entity")
                    or self.notifications.get("cooldown_switch_entity")
                    or ""
                ).strip()
                target_temp = float(self.notifications.get("cooldown_target_temp", 50) or 50)
                if plug_ent:

                    async def _safe_cooldown_power_off() -> None:
                        # Poll every 15s up to 45 minutes until nozzle drops <= target_temp (default 50°C)
                        for _ in range(180):
                            await asyncio.sleep(15)
                            if rt.print_status in ("running", "prepare", "pause"):
                                return
                            try:
                                cur_nozzle = float(rt.nozzle_temp)
                            except Exception:
                                cur_nozzle = 999.0
                            if 0 < cur_nozzle <= target_temp:
                                # Wait 120s safety buffer after reaching target temp, then power off
                                await asyncio.sleep(120)
                                if rt.print_status in ("finish", "idle") and (
                                    plug_ent.startswith("switch.") or plug_ent.startswith("input_boolean.")
                                ):
                                    plug_domain = plug_ent.split(".", 1)[0]
                                    await self.hass.services.async_call(
                                        plug_domain,
                                        "turn_off",
                                        {"entity_id": plug_ent},
                                    )
                                    cool_extra = await self._build_printer_notification_data(rt, include_snapshot=False, high_priority=False)
                                    await self.async_send_notification(
                                        title=f"🔌 Safe Cooldown Auto-Off — {rt.name}",
                                        message=(
                                            f"Nozzle cooled to {rt.nozzle_temp}°C (≤ {int(target_temp)}°C). "
                                            f"Powered off smart plug ({plug_ent}) safely."
                                        ),
                                        extra_data=cool_extra,
                                    )
                                return

                    self.hass.async_create_task(_safe_cooldown_power_off())

        elif event_type == "hms_error":
            if self.notifications.get("hms_error", True):
                err_extra = await self._build_printer_notification_data(rt, include_snapshot=True, high_priority=True)
                await self.async_send_notification(
                    title=f"🚨 Printer Alert — {rt.name}",
                    message=(
                        f"{rt.name} reported a print error or HMS fault during '{rt.task_name}' "
                        f"(Stage: {rt.current_stage} • ⚖️ {grams_str}g used). Tap to inspect {rt.name}!"
                    ),
                    extra_data=err_extra,
                )
            if self.notifications.get("rgb_light_sync") and self.notifications.get("rgb_light_entity"):
                await self.async_sync_rgb_light("hms_error", progress=rt.progress)
            if self.notifications.get("tts_voice_alert") and self.notifications.get("tts_media_player"):
                await self.async_speak_tts(
                    f"Attention required on {rt.name}. A printer fault or filament runout was detected."
                )

        elif event_type == "low_spool_alert":
            rem = int(extra_dict.get("remain", 15) or 15)
            slot_code = str(extra_dict.get("slot_code") or "A1")
            fil_name = str(extra_dict.get("name") or "PLA")
            est_g = int(round(rem * 10))
            if self.notifications.get("low_spool_alert", True):
                low_extra = await self._build_printer_notification_data(rt, include_snapshot=True, high_priority=False)
                await self.async_send_notification(
                    title=f"📦 Low Spool Alert ({rem}%) — {rt.name}",
                    message=(
                        f"AMS Slot {slot_code} ({fil_name}) on {rt.name} is down to {rem}% "
                        f"(~{est_g}g remaining). Prepare a replacement spool soon!"
                    ),
                    extra_data=low_extra,
                )
            if self.notifications.get("tts_voice_alert") and self.notifications.get("tts_media_player"):
                await self.async_speak_tts(
                    f"Low filament warning on {rt.name}. AMS slot {slot_code} is down to {rem} percent."
                )

    async def async_start_printer(self, serial: str, cfg: dict[str, Any]) -> BambuPrinterRuntime:
        """Start or restart a BambuPrinterRuntime."""
        sn = serial.strip().upper()
        if sn in self.runtimes:
            await self.hass.async_add_executor_job(self.runtimes[sn].stop)
        try:
            async_delete_issue(self.hass, DOMAIN, f"bad_access_code_{sn.lower()}")
        except Exception:
            pass
        rt = BambuPrinterRuntime(self.hass, cfg, on_odometer_save=self._schedule_save_from_thread)
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
        existing_rt = self.runtimes.get(serial)
        access_code = str(payload.get("access_code") or existing.get("access_code") or "").strip()
        model = normalize_model_code(str(payload.get("model") or existing.get("model") or ""), serial)
        name = str(payload.get("name") or existing.get("name") or f"Bambu {model}").strip()
        usage_hours = str(
            payload.get("usage_hours")
            if "usage_hours" in payload
            else (existing_rt.usage_hours if existing_rt else existing.get("usage_hours", "0"))
        ).strip()
        try:
            extruded_meters = max(
                0.0,
                float(
                    payload.get("extruded_meters")
                    if "extruded_meters" in payload
                    else (existing_rt._extruded_meters if existing_rt else existing.get("extruded_meters", 0.0))
                ),
            )
        except Exception:
            extruded_meters = 0.0
        try:
            extruded_grams = (
                max(0.0, float(payload["extruded_grams"]))
                if "extruded_grams" in payload
                else round(extruded_meters * 3.03, 1)
            )
        except Exception:
            extruded_grams = round(extruded_meters * 3.03, 1)

        ams_override = str(payload.get("ams_override") or existing.get("ams_override") or "AUTO").strip().upper()
        bed_type = str(
            payload.get("bed_type")
            if "bed_type" in payload
            else (existing_rt.bed_type if existing_rt else existing.get("bed_type", "Bambu Textured PEI Plate"))
        ).strip() or "Bambu Textured PEI Plate"
        smart_plug = payload.get("smart_plug") if "smart_plug" in payload else existing.get("smart_plug", {})
        resolved_host = host or existing.get("host", "")
        prev_last_online = (
            existing_rt.last_online_ts
            if existing_rt and existing_rt.last_online_ts > 0
            else float(existing.get("last_online_ts") or 0.0)
        )
        maint_log = (
            payload.get("maintenance_log")
            if isinstance(payload.get("maintenance_log"), dict)
            else (existing_rt.maintenance_log if existing_rt else existing.get("maintenance_log", {}))
        )

        cfg = {
            "serial": serial,
            "host": resolved_host,
            "access_code": access_code,
            "model": model,
            "name": name,
            "usage_hours": usage_hours,
            "extruded_meters": round(extruded_meters, 2),
            "extruded_grams": round(extruded_grams, 1),
            "bed_type": bed_type,
            "ams_override": ams_override,
            "smart_plug": smart_plug,
            "last_online_ts": round(prev_last_online, 1) if prev_last_online > 0 else 0.0,
            "maintenance_log": maint_log if isinstance(maint_log, dict) else {},
        }
        self.configs[serial] = cfg
        await self.async_save()

        # If runtime already exists and network credentials did not change, update in-place without dropping MQTT/camera
        if (
            existing_rt is not None
            and not existing_rt.auth_failed
            and existing_rt.host == resolved_host
            and existing_rt.access_code == access_code
            and existing_rt.model == model
        ):
            existing_rt._config_ref = cfg
            existing_rt.name = name
            existing_rt.ams_override = ams_override
            existing_rt.bed_type = bed_type
            existing_rt.smart_plug = smart_plug or {}
            try:
                existing_rt._usage_hours_val = max(0.0, float(usage_hours or 0.0))
            except Exception:
                pass
            existing_rt.usage_hours = existing_rt._fmt_num(existing_rt._usage_hours_val, 1)
            existing_rt._extruded_meters = extruded_meters
            existing_rt._extruded_grams = extruded_grams
            return existing_rt.to_status_dict()

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
        try:
            async_delete_issue(self.hass, DOMAIN, f"bad_access_code_{matched_sn.lower()}")
        except Exception:
            pass
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
                "lastOnlineTs": round(rt.last_online_ts, 1) if rt.last_online_ts > 0 else 0,
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


def _require_admin(request: web.Request) -> Optional[web.Response]:
    """Verify that the requesting user has administrator privileges."""
    user = request.get("hass_user")
    if not user or not user.is_admin:
        return web.json_response({"error": "Admin privileges required"}, status=403)
    return None


class FleetStatusAPIView(HomeAssistantView):
    """Return live standalone telemetry for all configured Bambu Lab printers."""

    url = "/api/bambu_fleet_studio/status"
    name = "api:bambu_fleet_studio:status"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
        if mgr and request.query.get("check_update") in ("1", "true", "yes"):
            ver_info = await mgr.async_check_github_release(force=True)
        elif mgr:
            ver_info = mgr.get_version_info()
        else:
            ver_info = {
                "current_version": VERSION,
                "latest_version": VERSION,
                "update_available": False,
                "release_url": GITHUB_RELEASES_WEB,
            }
        printers = [rt.to_status_dict() for rt in mgr.runtimes.values()] if mgr else []
        return web.json_response({
            "standalone": True,
            "version": VERSION,
            "version_info": ver_info,
            "printers": printers,
            "notifications": dict(mgr.notifications) if mgr else {},
        })


class FleetNotificationsAPIView(HomeAssistantView):
    """Get, save, or test standalone Bambu Lab Fleet Studio notification & automation settings."""

    url = "/api/bambu_fleet_studio/notifications"
    name = "api:bambu_fleet_studio:notifications"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
        return web.json_response({
            "ok": True,
            "notifications": dict(mgr.notifications) if mgr else {},
        })

    async def post(self, request: web.Request) -> web.Response:
        if err_resp := _require_admin(request):
            return err_resp
        try:
            mgr: Optional[BambuFleetStudioManager] = self.hass.data.get(DOMAIN, {}).get("manager")
            if not mgr:
                return web.json_response({"error": "Manager not initialized"}, status=500)
            body = await request.json()
            saved = await mgr.async_update_notifications(body)
            tested = False
            if body.get("test"):
                req_printer_key = str(body.get("test_printer") or saved.get("target_printer") or "").strip()
                target_rt: Optional[BambuPrinterRuntime] = None
                if req_printer_key and req_printer_key != "__ALL__":
                    target_rt = mgr.find_runtime(req_printer_key)
                if not target_rt:
                    target_rt = next(
                        (r for r in mgr.runtimes.values() if r.online and r.print_status == "running"),
                        next((r for r in mgr.runtimes.values() if r.online), next(iter(mgr.runtimes.values()), None)),
                    )
                custom_title = str(
                    body.get("test_title")
                    or (f"🖨️ Bambu Fleet Studio — {target_rt.name}" if target_rt else "🔔 Bambu Fleet Studio — Test Notification")
                ).strip()
                custom_msg = str(
                    body.get("test_message")
                    or (
                        f"Notification target ({saved.get('notify_service') or 'none'}) saved & verified! "
                        "Print Complete and HMS Fault alerts are active."
                    )
                ).strip()
                extra_data: Optional[dict[str, Any]] = None
                if target_rt:
                    grams_str, meters_str = target_rt.get_job_filament_usage()
                    if "g" not in custom_msg.lower() or "filament" not in custom_msg.lower():
                        custom_msg = f"{custom_msg} • ⚖️ Filament Used: {grams_str}g ({meters_str}m)"
                    extra_data = await mgr._build_printer_notification_data(target_rt, include_snapshot=True)
                if isinstance(body.get("test_data"), dict):
                    extra_data = {**(extra_data or {}), **body["test_data"]}
                tested = await mgr.async_send_notification(
                    title=custom_title,
                    message=custom_msg,
                    extra_data=extra_data,
                )
            if body.get("test_rgb") or body.get("rgb_test_state"):
                light_ent = str(body.get("rgb_light_entity") or saved.get("rgb_light_entity") or "")
                default_rgb_test = "test_wled_bar" if "wled" in light_ent.lower() else "finish"
                req_test_state = str(body.get("rgb_test_state") or default_rgb_test)
                req_progress = int(body.get("progress_pct", body.get("progress", 100)))
                tested = await mgr.async_sync_rgb_light(
                    req_test_state,
                    light_ent,
                    progress=req_progress,
                )
            if body.get("test_tts"):
                tested = await mgr.async_speak_tts(
                    "Bambu Fleet Studio voice alerts are now connected and active.",
                    str(body.get("tts_media_player") or ""),
                    force=True,
                )
            return web.json_response({
                "ok": True,
                "tested": tested,
                "notifications": saved,
            })
        except Exception as err:
            return web.json_response({"error": str(err)}, status=400)


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
                d["has_access_code"] = bool(rt.access_code or cfg.get("access_code", ""))
                d["usage_hours"] = rt.usage_hours or cfg.get("usage_hours", "0")
                d["extruded_meters"] = round(rt._extruded_meters, 1)
                d["extruded_grams"] = round(rt._extruded_grams, 0)
                d["bed_type"] = rt.bed_type or cfg.get("bed_type", "Bambu Textured PEI Plate")
                printers.append(d)
        return web.json_response({"printers": printers})

    async def post(self, request: web.Request) -> web.Response:
        if err_resp := _require_admin(request):
            return err_resp
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
        if err_resp := _require_admin(request):
            return err_resp
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
        if err_resp := _require_admin(request):
            return err_resp
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

            if action == "reset_maintenance":
                ok = rt.reset_maintenance_item(str(value or "all"))
                if not ok:
                    return web.json_response({"error": "Invalid maintenance item key"}, status=400)
                if rt.serial in mgr.configs:
                    mgr.configs[rt.serial]["maintenance_log"] = rt.maintenance_log
                await mgr.async_save()
                return web.json_response({"ok": True, "printer": rt.to_status_dict()})

            ok = await self.hass.async_add_executor_job(rt.send_action, action, value)
            return web.json_response({"ok": ok, "printer": rt.to_status_dict()})
        except Exception as err:
            return web.json_response({"error": str(err)}, status=400)


class FleetCameraSnapshotAPIView(HomeAssistantView):
    """Serve live JPEG camera frame from Port 6000 TLS or Port 322 RTSPS."""

    url = "/api/bambu_fleet_studio/camera/{serial}"
    name = "api:bambu_fleet_studio:camera"
    requires_auth = True

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
    requires_auth = True

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
    extra_urls = ["/api/bambu_fleet_studio/scan_network"]
    name = "api:bambu_fleet_studio:discover_serial"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        if err_resp := _require_admin(request):
            return err_resp
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
        hass.http.register_view(FleetNotificationsAPIView(hass))
        hass.http.register_view(FleetPrintersAPIView(hass))
        hass.http.register_view(FleetCommandAPIView(hass))
        hass.http.register_view(FleetCameraSnapshotAPIView(hass))
        hass.http.register_view(FleetCameraStreamAPIView(hass))
        hass.http.register_view(FleetDiscoverSerialAPIView(hass))
        domain_data["views_registered"] = True

    card_path = Path(__file__).parent / "bambu-fleet-cards.js"
    if card_path.is_file() and not domain_data.get("static_path_registered"):
        await hass.http.async_register_static_paths([
            StaticPathConfig("/bambu_fleet_studio/bambu-fleet-cards.js", str(card_path), cache_headers=True)
        ])
        add_extra_js_url(hass, f"/bambu_fleet_studio/bambu-fleet-cards.js?v={VERSION}")
        domain_data["static_path_registered"] = True

    return mgr


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Bambu Lab Fleet Studio standalone integration."""
    await _async_ensure_initialized(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bambu Lab Fleet Studio standalone integration from a config entry."""
    await _async_ensure_initialized(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    mgr: Optional[BambuFleetStudioManager] = domain_data.pop("manager", None)
    if mgr:
        for rt in list(mgr.runtimes.values()):
            await hass.async_add_executor_job(rt.stop)
        mgr.runtimes.clear()
    hass.data.pop(DOMAIN, None)
    return True
