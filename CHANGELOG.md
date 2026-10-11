# Changelog

All notable changes to **Bambu Lab Fleet Studio** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Clickable `AMS 2 Pro` / `AMS HT` Active Filament Dryer Control Modal (`#13`)**: Clicking the existing AMS temperature/humidity header badge (`🌡️ 23°C • 💧 47% RH • 🔥 Dry`) on any `AMS 2 Pro` (`<= 65°C`) or `AMS HT` (`<= 85°C`) opens a dedicated **Active Filament Dryer Control** modal that invokes `bambu_lab.start_filament_drying` and `bambu_lab.stop_filament_drying`:
  - **Material Drying Presets**: 1-click preset cards for **`PLA / Matte (50°C • 4h)`**, **`PETG / TPU (60°C • 6h)`**, **`ABS / ASA (65°C • 6h)`**, and **`PA / PC / CF (80°C • 8h on AMS HT / 65°C • 8h on AMS 2 Pro)`**.
  - **Dedicated Drying Duration Selector (`1h`–`24h`) & Live Finish Time Preview**: 6 quick-select duration pills (`2h`, `4h`, `6h`, `8h`, `12h`, `24h`) plus custom hours input (`1`–`24`) and a live finish-clock badge (`⏱️ 4h • Finishes ~11:30 PM`).
  - **Automatic PLA Softening Warning**: Automatically warns when `PLA` is loaded in any tray and the target drying temperature exceeds `55°C`.
  - **Explicit Spool Rotation Selector (`rotate_tray`)**: Prompts whether to run **`🛑 Do NOT Rotate (Stationary)`** (`rotate_tray: false`, filament stays loaded in feeder) or **`🔄 Rotate Spools While Drying`** (`rotate_tray: true`, periodically rotates spools for uniform heating).
  - **Firmware MQTT Encryption Lock Diagnostics (`err_code 84033543`) & Post-Command State Verification**: Detects when a printer in Local MQTT mode has firmware MQTT signature verification (`mqtt_encryption: on`) enabled with `developer_lan_mode: off` (which causes Bambu firmware to reject unsigned local control commands with `err_code 84033543: mqtt message verify failed`), displays a clear unlock guide (**Settings ⚙️ → LAN Only Mode → Developer Mode ON** on the printer touchscreen or switching to **Bambu Cloud** mode in Home Assistant), and polls `binary_sensor.*_ams_*_drying` after calling `start_filament_drying` to confirm the AMS actually entered active drying before reporting success.

## [1.2.3] - 2026-10-11

### Fixed
- **Automatic Fahrenheit (`°F`) → Celsius (`°C`) Temperature Normalization (`#12`)**: Fixed an issue on Home Assistant systems configured with Imperial/US units where printer temperature sensors (`nozzle_temperature`, `nozzle_target_temperature`, `bed_temperature`, `bed_target_temperature`, `chamber_temperature`, and `ams_*_temperature`) reported in `°F` (e.g. `73.4°` nozzle / `75.2°` bed / `Target 32.0°` when idle at room temperature, and falsely triggered the `> 60°C` Smart Plug thermal safety lock). All printer and AMS temperature sensors now automatically inspect `attributes.unit_of_measurement` and normalize `°F` values to 3D-printing Celsius (`°C`) with explicit `°C` unit labels.
- **AMS Lite Open-Air Sensor Handling (`#12`)**: Because the Bambu `AMS Lite` is an open-air rotary feeder with no enclosure temperature or humidity sensor (`ha-bambulab` reports `0°C` / `32.0°F` and `0%` humidity), `AMS Lite` decks now display a clean **`🌬️ Open-Air Rotary`** hardware badge instead of dummy `🌡️ 0°C` / `💧 Idx 1` enclosure chips.

## [1.2.2] - 2026-10-11

### Added
- **Inline Chamber Temperature, Aux/Chamber Fans & Door Sensor Telemetry (`#11`)**: On enclosed printers (`P2S`, `P1S`, `X1C`, `X1E`, `X2D`, `H2`, `R1`), the existing Build Plate tile now shows `🛏️ Bed & Chamber` with live chamber temperature (`• 🏠 24°`) and door state (`🚪 Door Closed` / `🚪 Door Open`), the Cooling & Speed tile sub-line shows live `Aux %` and `Chamb %` fan speeds alongside the speed profile, and an inline `🚪 Door Open` pill appears in the card header only when the enclosure door is open.
- **Actual AMS Relative Humidity (`% RH`) & Wet-Filament Highlight (`#11`)**: Reads `sensor.*_ams_<N>_humidity` (`% RH`) alongside `humidity_index` inside the existing AMS header badge (e.g. `💧 47% RH • Idx 5`), automatically highlighting the pill in amber (`>= 45% RH`) or red (`>= 55% RH`) with `⚠️` when desiccant or active drying is needed.
- **Exact Finish Clock Time in Existing ETA Badge (`#11`)**: Displays the target completion clock time alongside the remaining countdown inside the existing `⏱️` job progress pill (e.g., `1h 12m • 7:42 PM`) when a print is active.

## [1.2.1] - 2026-10-11

### Fixed
- **P2S / X1 / H2 RTSPS Camera Live Feed Fix (`#10`)**: Resolved an issue where RTSPS cameras (`P2S`, `X1C`, `X1E`, `H2D`, `R1`) displayed a black 320×240 placeholder image with a red exclamation mark (`!`) even after enabling `LAN Only Liveview`. Root cause: Home Assistant Core's `/api/camera_proxy_stream/` endpoint invokes `camera._async_camera_image()` directly, bypassing `use_stream_for_stills = True` and returning `BambuLabRtspCamera.camera_image()`'s hardcoded 320×240 red-exclamation fallback instead of decoding the RTSPS stream. RTSPS cameras now use double-buffered offscreen preloading against `/api/camera_proxy/camera.<id>` (which calls `camera.async_camera_image()` → `stream.async_get_image()` and delivers full 1920×1080 HD live frames) in both the card viewport and fullscreen lightbox modal.
- **Zero-Scroll Card Action & Chamber Light Toggle (`#10`)**: Fixed a bug where clicking any button on a printer card (such as toggling the Chamber Light `💡` ON/OFF or switching viewport tabs) caused the dashboard page to scroll back to the top and momentarily blinked live camera streams. Added scroll-container & viewport-card-offset anchoring (`_captureScrollContext` / `_restoreScrollContext`), live camera `<img>` DOM node preservation across `_render()` updates, `type="button"` + `btn.blur()` focus management, and instant optimistic UI toggling on the Chamber Light buttons.
- **Notification Automation Blueprint Compatibility (`#10`)**: Fixed `buildAutomationBlueprint` so non-`mobile_app` notification services (`notify.notify` / `notify.persistent_notification`) omit mobile-only `data.image` fields that caused Home Assistant validation errors.

## [1.2.0] - 2026-10-11

### Added
- **Built-In LAN Printer Auto-Discovery Scanner (`#9`)**: Added an automatic `/24` local network scanner (`/api/bambu_lab/scan_network` & `/api/bambu_lab/discover_serial?scan=1`) and interactive **`📡 Auto-Discovered Bambu Printers on Network`** deck inside the **`➕ Add Printer`** modal:
  - Concurrently sweeps the local subnet on TCP Port `8883` TLS in ~1.2 seconds, validates the `BBL CA` X.509 peer certificate, extracts the 15-character Serial Number (`CN`), infers the hardware model from the serial prefix (`22E` → `P2S`, `039` → `A1`, `030` → `A1 Mini`, `01P` → `P1S`, `01S` → `P1P`, `00M` → `X1C`, `03W` → `X1E`, `094` → `H2D`), and merges with Home Assistant's device registry.
  - Renders clickable discovery cards with model studio render, IPv4 address, 15-character Serial Number, and status pills (`✨ NEW ON LAN`, `⚠️ NEW IP`, `✅ PAIRED • ONLINE`, `💤 PAIRED • OFFLINE`).
  - Clicking any discovered printer populates **Model, IPv4 Address, 15-Character Serial Number, and Display Name** in 1 click and focuses the **8-Char Access Code** field (and automatically pre-selects the first unconfigured printer found on the LAN).
- **1-Click DHCP IP Relocator in Edit Device Modal (`#9`)**: Added a **`📡 Find IP on LAN`** button next to the **Local IP Address (Host)** field in the **Edit Device** modal to automatically locate a printer's new IPv4 address on Port `8883` TLS by its 15-character Serial Number if DHCP reassigns its IP.

## [1.1.1] - 2026-10-11

### Added
- **Automatic 15-Character Serial Number Discovery (`#8`)**: Added live LAN TLS certificate & device registry serial number auto-population in both the **Add Printer** modal (with automatic IP-to-Serial lookup, `🔍 Auto-Detect` button, and optional serial entry) and the **Edit Device** modal (with a 1-click `📋 Copy` button). Also added automatic serial-prefix model inference (`22E` → `P2S`, `039` → `A1`, `030` → `A1 Mini`, `01P` → `P1S`, `01S` → `P1P`, `00M` → `X1C`, `03W` → `X1E`, `094` → `H2D`).
- **Multi-AMS Spool Deck Support (`#8`)**: Printers with multiple daisy-chained AMS units (e.g., dual `AMS 2 Pro` units `#1` and `#2` on `P2S`, `X1C`, or `H2` series, including area-prefixed entities) now render every attached AMS deck (`A1`–`A4`, `B1`–`B4`, etc.) on the printer card and in the **Cross-Fleet Filament Finder**.

### Fixed
- **P2S / H2 / X1 Live Camera RTSP Stream & "Enable LAN Only Liveview" Diagnostics (`#8`)**: Upgraded RTSP camera handling to support native Home Assistant `<ha-camera-stream>` WebRTC/HLS playback alongside MJPEG stream switching, added `pick_image` preview fallback when the camera entity is offline/disabled, added a 1-click **Reconnect Camera** trigger, and added an interactive **"Enable LAN Only Liveview on Printer"** touchscreen guide (`Settings ⚙️ → LAN Only → Toggle ON "LAN Only Liveview"`) when a P2S reports `rtsp_url: "disable"`.

## [1.1.0] - 2026-10-11

### Added
- **Embedded Studio Artwork for AMS Lite, AMS HT, AMS 2 Pro & AMS (`#7`)**: Added high-resolution transparent-background studio PNG renders for **`AMS Lite`** (`AMSLITE` — 4-spool open rotary feeder), **`AMS HT`** (`AMSHT` — 85°C High-Temperature active dryer & feeder), **`AMS 2 Pro`** (`AMS2PRO`), and **`AMS`** (`AMS`). Displayed alongside the **AMS & Filament System** header on printer cards, inside the **Edit Device** modal (with per-printer AMS unit & artwork selector), in a dedicated **`🎨 AMS Lite / AMS HT`** walkthrough tab, and in the 17-tile **Supported Hardware Lineup** gallery.
- **Complete 14-Model Artwork & R1 55W CO2 Laser Support (`#6`)**: Embedded high-resolution studio renders and full model selection/override support for **`P2S`**, **`A2L`**, **`H2C`**, **`H2D`**, **`H2D Pro`**, **`H2S`**, **`X1C`**, **`X2D`**, and Bambu Lab's new **`R1` (55W CO2 Laser Cutter & Engraver)** alongside **`A1`**, **`A1 Mini`**, **`P1S`**, **`P1P`**, and **`X1E`**.
- **Clickable Hardware Lineup Gallery & 6-Series Walkthrough Tabs (`#6`, `#7`)**: Added 6 hardware series tabs (`A1 / Mini / A2L`, `P1S / P1P / P2S`, `X1C / X1E / X2D`, `H2C / H2D / H2S`, `🔥 R1 CO2 Laser`, `🎨 AMS Lite / AMS HT`) and a clickable 17-tile **Supported Hardware Lineup** gallery in the 4-Step Setup Walkthrough.

### Fixed
- **Lovelace Dashboard Configuration Errors Resolved (`#6`)**: Registered `custom:bambu-printer-studio-card` alongside `custom:bambu-fleet-studio`, added legacy compatibility shims for `ha-bambulab-print_status-card`, `ha-bambulab-ams-card`, and `ha-bambulab-spool-card` so views never throw `Custom element doesn't exist` errors, added automatic model-fallback and "Ready to Pair" empty-state cards for single-printer tabs, and cleaned up redundant legacy card sections on the live `bambu-fleet` Lovelace dashboard.

## [1.0.0] - 2026-10-11

### Added
- **Zero-Config Automatic Printer Discovery (`#1`)**: Automatically discovers all Bambu Lab 3D printers & lasers registered in Home Assistant via `ha-bambulab`.
- **Model-Accurate Printer Studio Cards (`#1`)**: Embedded high-resolution printer graphics paired with a 3-mode interactive viewport switcher (`📹 Live Cam` with fullscreen lightbox, `🖼️ 3MF Cover`, and `🎛️ Quick Controls`).
- **Smart Conditional AMS Deck (`#1`)**: Automatically inspects the Home Assistant Device Registry for attached AMS units (`AMS`, `AMS Lite`, `AMS 2 Pro`, `AMS HT`). Printers with an AMS render a 4-slot color-coded spool deck with live hex colors, remain bars, temperature, humidity index, and active drying status; single-extruder printers without an AMS display only a compact Direct External Spool card.
- **In-Dashboard Add, Edit, Reload & Delete Printer Manager (`#1`)**: Native integration with Home Assistant's `config_entries/flow` and `config_entries/options/flow` APIs allowing direct LAN printer onboarding (Port `8883` TLS), IP/Access Code updates, device renaming, and Bambu Cloud wizard hand-off without leaving the dashboard.
- **Cross-Fleet Filament Finder Drawer (`#1`)**: Collapsible spool inventory drawer in the Command Bar aggregating all loaded AMS trays (`A1`–`A4`) and Direct External Spools across every printer with material filter pills (`All`, `PLA`, `PETG`, `ASA`, `TPU`), search input, and click-to-highlight printer navigation.
- **Conditional HMS Error & Print Pause Diagnostic Banner (`#1`)**: Zero-height when healthy; automatically renders a high-visibility amber/red alert banner when `hms_errors`, `print_error`, or filament runout occurs, with a 1-click **Bambu Wiki ↗** button.
- **Safety-Locked Smart Plug Power Toggle & Live Wattage (`#1`)**: Optional per-printer `switch.*` and `sensor.*_power` binding in the **Edit Printer** modal with live wattage (`W`) pill and automatic thermal safety lock (`🔒`) while printing or while `nozzleTemp > 60°C`.
- **1-Click Notification & Camera Snapshot Automation Builder (`#1`)**: Auto-discovers Home Assistant `notify.*` services and provides 1-click installation, YAML copy, and live test push for 3 blueprints (*Print Complete Push + Snapshot*, *HMS Error & Filament Runout Alert*, and *Auto-Off Chamber Light after 5m*).
- **Mobile & Home Assistant Companion App Optimization (`#1`)**: Added CSS `@container` (`inline-size`) queries and mobile breakpoints (`<= 680px` / `<= 420px`) with 2×2 mobile AMS spool decks, 4-column KPI bar, 2×2 touch command buttons, horizontal swipeable filter pills, 16px mobile inputs, and `dvh` bottom-sheet modals.
- **HACS Frontend Plugin Support & Dashboard Spotlight (`#1`)**: Full `hacs.json` manifest, automated `hacs/action` CI validation workflow (`.github/workflows/validate.yaml`), visual Lovelace Card Editor (`bambu-fleet-studio-editor`), expanded maker welcome note, and 5 high-resolution Dashboard Spotlight screenshots (`docs/screenshots/`).
