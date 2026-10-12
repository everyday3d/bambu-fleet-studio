# 🖨️ Bambu Lab Fleet Studio — Home Assistant Dashboard & Custom Cards

[![Release v1.2.3](https://img.shields.io/badge/Release-v1.2.3%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom%20Plugin-41BDF5?style=flat-square&logo=home-assistant)](https://github.com/hacs/integration)
[![GitHub Issues](https://img.shields.io/github/issues/everyday3d/bambu-fleet-studio?style=flat-square&logo=github&label=Issue%20Tracker)](https://github.com/everyday3d/bambu-fleet-studio/issues)
[![License: MIT](https://img.shields.io/badge/License-MIT-amber?style=flat-square)](LICENSE)

> [!NOTE]
> **👋 Hello makers!** This is a project I've been working on for some time, and I think I'm finally ready to release it to the community.
>
> Having every Bambu Lab printer in my shop on a single, clean Home Assistant screen has been a total game-changer—being able to glance at live camera feeds, check nozzle/bed temps, see exact layer progress & ETAs, and immediately spot which filament colors and materials are loaded in each AMS without bouncing between Bambu Handy or Bambu Studio is ridiculously handy. It even knows which printers actually have an AMS attached (so your non-AMS printers stay clutter-free) and lets you add or manage printers right from the dashboard.
>
> Since this is a fresh release, **expect some bugs!** If you run into anything quirky or have an idea that would make your print room easier to run, please drop a ticket in the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)** and I will get it fixed! I hope you enjoy using it in your workshop as much as I do.

> A professional, card-based Home Assistant Lovelace dashboard and zero-dependency Web Component suite (`bambu-fleet-cards.js`) purpose-built for managing multi-printer **Bambu Lab** 3D printing, laser & AMS fleets (**`A1`**, **`A1 Mini`**, **`A2L`**, **`P1P`**, **`P1S`**, **`P2S`**, **`X1C`**, **`X1E`**, **`X2D`**, **`H2C`**, **`H2D`**, **`H2D Pro`**, **`H2S`**, the **`R1` 55W CO2 Laser Cutter & Engraver**, plus **`AMS`**, **`AMS Lite`**, **`AMS 2 Pro`**, and **`AMS HT`**).

---

## 🌟 Why Bambu Lab Fleet Studio?

Default Home Assistant entity lists clutter your screen with dozens of ungrouped sensors and render empty AMS filament slots even on printers that do not have an AMS attached. **Bambu Lab Fleet Studio** replaces walls of text and scattered entities with a sleek, dark-glass industrial command center:

- **🔌 100% Standalone Local LAN Engine (`Zero External Dependencies`)**: Includes its own built-in Home Assistant backend (`custom_components/bambu_fleet_studio/`) that connects **directly** to your Bambu Lab printers over your local network—**no `ha-bambulab` or third-party integration required**!
  - **Direct Port `8883` TLS MQTT Client**: Connects directly (`username: bblp`, `password: <8-char Access Code>`) to `device/<serial>/report` and `device/<serial>/request` for real-time temperatures, print progress, layer counters, ETA, AMS/AMS Lite/AMS 2 Pro/AMS HT spools, HMS error codes, chamber lights, speed profiles, and print job controls (`pause`, `resume`, `stop`, `pushall`).
  - **Direct Port `6000` TLS & Port `322` RTSPS Camera Engine**: Streams live JPEG/MJPEG camera feeds directly from Port `6000` TLS (`A1`, `A1 Mini`, `P1P`, `P1S`) and decodes 1080p H.264 RTSPS video from Port `322` (`P2S`, `X1C`, `X1E`, `H2D`, `H2C`, `H2S`, `R1`) with zero external camera proxy dependencies.
  - **Automatic Legacy Migration**: If you previously configured printers in Home Assistant, Fleet Studio automatically imports their IP address, Serial Number, and Access Code into `.storage/bambu_fleet_studio.printers` on first startup.
- **🖼️ Complete 14-Model Printer & R1 Laser Photography**: Built-in, embedded high-resolution studio renders for every Bambu Lab series—**`A1`**, **`A1 Mini`**, **`A2L`**, **`P1S`**, **`P1P`**, **`P2S`**, **`X1C`**, **`X1E`**, **`X2D`**, **`H2C`**, **`H2D`**, **`H2D Pro`**, **`H2S`**, and the **`R1` (55W CO2 Laser Cutter & Engraver)**—automatically matched to each device's model (with a per-device **Hardware Model & Artwork** selector in the Edit modal).
- **🎨 Embedded Studio Artwork for AMS Lite, AMS HT, AMS 2 Pro & AMS**: Includes dedicated high-resolution studio renders for **`AMS Lite`** (4-spool open rotary feeder), **`AMS HT`** (85°C High-Temperature active engineering dryer), **`AMS 2 Pro`** (4-slot active drying unit), and standard **`AMS`**, displayed directly inside each printer's **AMS & Filament System** header, the **Edit Device** modal, and the **Supported Hardware Lineup** gallery.
- **🎨 Smart Conditional Multi-AMS Detection, Live `% RH` & Automatic `°F` → `°C` Normalization**: Automatically inspects live MQTT `print.ams.ams[]` payloads across single or daisy-chained AMS units (`AMS #1`, `AMS #2`, etc.). Normalizes any Imperial (`°F`) printer/AMS temperature sensors to 3D-printing Celsius (`°C`), renders **`🌬️ Open-Air Rotary`** on sensorless `AMS Lite` feeders, displays real relative humidity (`% RH`) with amber/red wet-filament highlighting (`>= 45% RH`), plus inline **Chamber Temp (`°C`)**, **Aux/Chamber Fan `%`**, **Door Open/Closed**, and **Exact Finish Clock Time (`1h 12m • 7:42 PM`)** inside existing tiles with zero layout bloat.
- **📡 Built-In LAN Network Auto-Discovery & 15-Char Serial Lookup**: Opening the **`➕ Add Printer`** modal automatically sweeps your local `/24` subnet on Port `8883` TLS in ~1.2s, validates `BBL CA` certificates, extracts each printer's **15-character Serial Number**, and infers the hardware model (`22E` → `P2S`, `039` → `A1`, `030` → `A1 Mini`, `01P` → `P1S`, `00M` → `X1C`, `094` → `H2D`). Click any discovered printer card to populate **Model, IPv4 Address, Serial Number, and Name** in one click! Also includes a **`📡 Find IP on LAN`** button in the **Edit Device** modal if DHCP changes a printer's IP.
- **🎨 Cross-Fleet Filament Finder ("Which Printer Has My Spool?")**: Collapsible spool inventory drawer in the Command Bar aggregating every loaded AMS slot (`A1`–`A4`, `B1`–`B4`, etc.) and External Spool across the entire fleet with material filter pills (`All`, `PLA`, `PETG`, `ASA`, `TPU`, etc.), instant search, and click-to-highlight printer navigation.
- **🚨 Conditional HMS Error & Print Pause Alert Strip**: Hidden (`0px`) during healthy operation; automatically expands into a high-visibility amber/red diagnostic banner when HMS faults, `print_error`, or filament runout occurs, complete with a 1-click **Bambu Wiki ↗** troubleshooting button.
- **⚡ Safety-Locked Smart Plug Power Toggle & Live Wattage (`W`)**: Bind any Home Assistant `switch.*` and `sensor.*_power` entity per printer in the **Edit Printer** modal. Displays live power draw (`W`) and a mains toggle button that **automatically locks (`🔒`)** while printing or while `nozzleTemp > 60°C` to prevent heat-creep extruder jams.
- **🔔 1-Click Notification & Camera Snapshot Automation Builder**: Auto-discovers your Home Assistant `notify.*` devices and installs 3 ready-made automations in 1 click (*Print Complete Push + Live Camera Snapshot*, *HMS Error & Filament Runout Alert*, and *Auto-Off Chamber Light after 5m*).
- **📹 1080p RTSPS & MJPEG Live Camera Viewport + P2S Liveview Assistant**: Side-by-side model artwork and flicker-free live camera feed with double-buffered 1920×1080 RTSPS stream decoding for `P2S`, `H2`, `X1`, and `R1`, native Port `6000` TLS streaming for `A1`, `A1 Mini`, `P1S`, and `P1P`, DOM-preserved `<img>` viewports with scroll-anchored card controls, and an interactive **Enable LAN Only Liveview** setup helper when a P2S camera stream is disabled on the printer touchscreen.
- **➕ Built-In Fleet Manager (Add / Edit / Reload / Delete)**: Add new Bambu Lab printers or R1 Lasers directly via the standalone LAN engine (`/api/bambu_fleet_studio/printers`) with 1-click LAN Auto-Discovery, customize printer & AMS hardware artwork, reconnect streams, or remove devices directly from the dashboard UI.
- **📖 4-Card Visual Onboarding Walkthrough & Clickable Hardware Lineup**: Interactive 4-step card grid with 6 series tabs (`A1 / Mini / A2L`, `P1S / P1P / P2S`, `X1C / X1E / X2D`, `H2C / H2D / H2S`, `🔥 R1 CO2 Laser`, `🎨 AMS Lite / AMS HT`) plus a clickable 17-tile **Supported Hardware Lineup** gallery.
- **⏱️ Per-Printer Extrusion Odometer (`m` / `km` / `kg` / `Spools`) & Live Print Hours Tracker**: Tracks cumulative lifetime print/laser hours alongside extruded filament length (`m` / `km`), extruded weight (`kg`), and equivalent 1 kg spools (`📦 ~X.X Spools (X.XXkg)` at `330m ≈ 1kg` of 1.75mm filament). Automatically accumulates elapsed `RUNNING` hours and extruded filament via `.3mf` job length/weight × progress deltas and Bambu RFID `remain%` drops, with 1-click **`⚡ Est. from Hours`** (`~4.5m/h`) baseline calibration in **`✏️ Edit Device`**.
- **🛏️ Model-Aware Build Plate Selector (Official Bambu Lab + BIQU CryoGrip & Panda Plates)**: Select and display each printer's installed build plate, automatically tailored to its bed dimensions (`180×180mm` A1 Mini, `256×256mm` A1/P1/X1, `350×320mm` H2/X2D, `400×400mm` R1 Laser). Includes all **Official Bambu Lab Plates** (*Textured PEI*, *Smooth PEI*, *Dual-Texture*, *Cool Plate SuperTack*, *High Temp*, *Engineering*, *3D Effect Sheets*) and **BIQU Plates** (*🧊 CryoGrip Pro Glacier*, *❄️ CryoGrip Pro Frostbite*, *🐼 Panda BuildPlate*, *🍊 Panda Juicy*).
- **🌐 12-Language Internationalization (`i18n`)**: Built-in support for **English (`en`)**, **Deutsch (`de`)**, **Français (`fr`)**, **Español (`es`)**, **Italiano (`it`)**, **Nederlands (`nl`)**, **Polski (`pl`)**, **Português (`pt`)**, **Русский (`ru` — *untested; community feedback needed!*)**, **简体中文 (`zh` — *untested; community feedback needed!*)**, **繁體中文 (`zh-tw` — *untested; community feedback needed!*)**, and **日本語 (`ja`)**. Automatically detects your Home Assistant profile language (`hass.language`, including `zh-Hans` / `zh-CN` and `zh-Hant` / `zh-TW` / `zh-HK`), localizes Bambu filament color names (`玉石白`, `拓竹绿`, `竹炭黑`, `樱花粉`, `天空蓝`, etc.), Cross-Fleet Filament Studio, top Lovelace tabs, 4-Step Setup Walkthrough, and backend config flow (`translations/{zh-Hans,zh-Hant}.json`), supports `language:` in card YAML / visual editor, and includes an instant **`🌐`** language selector right in the Command Bar.
- **📱 Mobile & Home Assistant Companion App Optimized**: Built with modern CSS `@container` size queries, dynamic viewport (`dvh`) bottom-sheet modals, 2×2 touch-friendly Command Bar & AMS Spool grids on narrow viewports, swipeable filter pills, and 16px mobile inputs (preventing unwanted iOS Safari auto-zoom).
- **🔒 100% Self-Contained, Standalone & Privacy-First**: Zero third-party integration dependencies (`ha-bambulab` is **not** required), zero external CDN dependencies, and zero hardcoded tokens or IP addresses.

---

## 📸 Dashboard Spotlight

### 1. Multi-Printer Fleet Command Center
![Bambu Lab Fleet Studio Overview](docs/screenshots/01_fleet_studio_overview.png)

**What You See in the Fleet Studio Overview:**
- **Top Command Header**: Real-time fleet KPI pills (**Total Printers**, **Online**, **AMS Units**, **Print Hours / Alerts**) paired with instant action triggers (`🌐 Language`, `🎨 Filament Finder`, `🔔 Automations`, `📖 Setup Guide`, `➕ Add Printer`).
- **Hero Visual Split**: Each printer card pairs its model-accurate studio photograph on the left with a live camera stream viewport on the right.
- **Print Job & Layer Telemetry Bar**: Displays active `.3mf` / `.gcode` job name, completion percentage, glowing progress bar, current/total layer counter (`Layer 194 / 285`), and live remaining ETA.
- **4-Tile Hardware Telemetry Grid**: Scannable cards for **Nozzle Temp** (actual vs. target), **Bed Temp** (actual vs. target), **Speed Profile & Chamber Temp**, and **Cooling Fans & Wi-Fi RSSI**.

---

### 2. Smart Conditional AMS Engine — Zero Wasted Space
![Smart Conditional AMS Detection Spotlight](docs/screenshots/02_conditional_ams_spotlight.png)

**How Conditional AMS Detection Works:**
- **AMS-Equipped Printers (Left — Bambu A1 + AMS Lite / Bambu P1S + AMS 2 Pro)**: Automatically detects attached AMS units and active `tray_1..tray_4` slots. Renders all 4 filament slots with live RFID hex color swatches, material type (`PLA`, `PETG`, `ASA`, `PLA-CF`, `TPU`), active slot glow border, and AMS humidity/temperature badges.
- **Direct-Spool Printers (Right — Bambu A1 Mini without AMS)**: Detects that no AMS hardware is attached and **automatically omits the 4-slot AMS deck**, rendering a clean **Direct External Spool Holder** card instead.

---

### 3. Built-In Standalone Printer Fleet Manager (Add, Edit, Reload & Delete)
![Add Edit Printer Manager Spotlight](docs/screenshots/03_add_edit_printer_manager.png)

**In-Dashboard Standalone Fleet Administration:**
- **Interactive Model Selector & Preview**: Preview **Bambu A1**, **Bambu A1 Mini**, **Bambu P1S**, **Bambu P2S**, **Bambu X1C**, **Bambu H2D**, or **Bambu R1 Laser** hardware capabilities before pairing.
- **Direct Standalone LAN Pairing (`Port 8883 TLS`)**: Pair any Bambu Lab printer directly from the dashboard using its **Local IPv4 Address**, **8-Character Access Code**, and **auto-detected 15-Character Serial Number**—no external integration setup needed.
- **Per-Printer Lifecycle Actions**: Reconnect live MQTT/Camera threads (`🔄`), edit IP/Access Code/AMS artwork/Smart Plug bindings (`✏️`), or remove a printer (`🗑️`) directly from the card header.

---

### 4. 4-Card Visual Setup Walkthrough
![4-Step Visual Walkthrough Cards](docs/screenshots/04_walkthrough_step_cards.png)

**Zero Walls of Text:**
- Clicking **Setup Guide** in the Command Bar reveals a 4-card visual onboarding grid covering **Step 01 (LAN Mode & Access Code)**, **Step 02 (15-Char Serial Number)**, **Step 03 (Fleet Studio Modal Pairing)**, and **Step 04 (Auto-Discovery & Smart AMS)**.

---

### 5. Advanced Fleet Intelligence — Filament Finder, HMS Diagnostics, Smart Plugs & Automations
![Advanced Fleet Intelligence Spotlight](docs/screenshots/05_filament_hms_smartplug_automations.png)

**Built-In Power Features for Multi-Printer Workshops:**
- **🎨 Cross-Fleet Filament Finder**: Click `🎨 Filament Finder` in the Command Bar to search across every loaded AMS slot and External Spool in your shop by material (`PLA`, `PETG`, `ASA`, `TPU`) or color name. Clicking any spool card smoothly scrolls to and highlights that printer card.
- **🚨 Conditional HMS Error & Print Pause Banner**: Takes up `0px` when your printer is healthy, and automatically expands into a high-visibility diagnostic banner whenever an HMS error code or `print_error` triggers—complete with a direct **Bambu Wiki ↗** button.
- **⚡ Safety-Locked Smart Plug & Live Wattage (`W`)**: Optional per-printer smart plug binding (`switch.*` + `sensor.*_power`) configurable in the **Edit Printer** modal. Displays live power consumption in the card header and **blocks accidental power-off (`🔒`)** while printing or while `nozzleTemp > 60°C` to prevent heat-creep filament jams.
- **🔔 1-Click Notification & Camera Snapshot Automation Builder**: Deploy native Home Assistant automations in 1 click (or copy the generated YAML) for **Print Complete Push + Camera Snapshot**, **HMS Error & Filament Runout Alert**, and **Auto-Off Chamber Light (5m Delay)**.

---

## 📦 Installation (100% Standalone — Zero Third-Party Dependencies)

### Prerequisites
1. **Home Assistant** `2024.6.0` or newer.
2. **No other Bambu Lab integration required!** Bambu Lab Fleet Studio includes its own standalone local LAN MQTT + Camera backend (`custom_components/bambu_fleet_studio/`) and frontend Lovelace card bundle (`bambu-fleet-cards.js`). *(If you already have `ha-bambulab` installed, Fleet Studio will automatically import your existing printer credentials and coexist seamlessly.)*

---

### Step 1: Install the Standalone Backend & Card Bundle

#### Option A: Install via HACS
1. Open **HACS** in your Home Assistant sidebar.
2. Click the **three-dot menu (`⋮`)** in the top-right corner and select **Custom repositories**.
3. Enter the repository URL:
   ```text
   https://github.com/everyday3d/bambu-fleet-studio
   ```
4. Select category **Dashboard** (or copy `custom_components/bambu_fleet_studio` into `/config/custom_components/bambu_fleet_studio`) and click **Download**.

#### Option B: Direct Copy Installation
1. Copy the `custom_components/bambu_fleet_studio/` folder into your Home Assistant `/config/custom_components/bambu_fleet_studio/` directory and add `bambu_fleet_studio:` to your `configuration.yaml` (or add **Bambu Lab Fleet Studio** under **Settings → Devices & Services → Add Integration**).
2. Copy [`bambu-fleet-cards.js`](https://github.com/everyday3d/bambu-fleet-studio/releases/latest/download/bambu-fleet-cards.js) into `/config/www/bambu-fleet-cards.js`.
3. In Home Assistant, go to **Settings → Dashboards → `⋮` (top right) → Resources → Add Resource**:
   - **URL**: `/local/bambu-fleet-cards.js`
   - **Resource type**: `JavaScript Module`
4. Restart Home Assistant Core once to activate the standalone `/api/bambu_fleet_studio/*` engine, then click **`➕ Add Printer`** on your dashboard to auto-discover and pair your printers on Port `8883` TLS!

---

## ⚙️ Usage & Lovelace YAML Configuration

**Bambu Lab Fleet Studio** provides two custom elements:
1. `custom:bambu-fleet-studio` — **Zero-Config Full Fleet Studio** (auto-discovers every Bambu Lab printer in Home Assistant, includes Command Bar, Fleet Grid, Add/Edit Manager Modal, and 4-Card Walkthrough).
2. `custom:bambu-printer-studio-card` — **Single-Printer Studio Card** (drop into any existing Lovelace view for a specific printer prefix).

### 1. Full Standalone Dashboard (`examples/bambu-fleet-dashboard.yaml`)

Create a new dashboard in **Settings → Dashboards → Add Dashboard**, open the **Raw configuration editor**, and paste:

```yaml
title: Bambu Lab Fleet
views:
  - title: Fleet Studio
    path: overview
    icon: mdi:printer-3d
    type: panel
    cards:
      - type: custom:bambu-fleet-studio
        title: Bambu Lab Fleet Studio
        subtitle: Real-Time Telemetry, Live Camera Feeds & Smart Conditional AMS

  - title: Setup Walkthrough
    path: walkthrough
    icon: mdi:compass-outline
    type: panel
    cards:
      - type: custom:bambu-fleet-studio
        title: Bambu Lab Fleet Studio
        default_tab: walkthrough
```

### 2. Individual Printer Cards (Manual Prefix Mode)

If you prefer placing individual printer cards inside an existing Lovelace view (with visual card editor support):

```yaml
type: grid
columns: 3
square: false
cards:
  - type: custom:bambu-printer-studio-card
    name: Bambu A1
    prefix: a1_03900a100000001
    printer_model: A1
    ams_mode: auto

  - type: custom:bambu-printer-studio-card
    name: Bambu P1S
    prefix: p1s_01p00b200000002
    printer_model: P1S
    ams_mode: auto

  - type: custom:bambu-printer-studio-card
    name: Bambu A1 Mini
    prefix: a1mini_03000c300000003
    printer_model: A1MINI
    ams_mode: auto
```

### Card Configuration Options (`custom:bambu-printer-studio-card`)

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `prefix` | `string` | Optional | Printer identifier prefix (`<model>_<serial>`, e.g. `a1_03900a100000001` or `p2s_22e00a100000001`). |
| `name` | `string` | Auto-detected | Display name shown in the card header (e.g. `Bambu A1`, `Bambu P2S`, `Bambu R1 Laser`). |
| `printer_model` | `string` | `auto` | Hardware model filter / artwork selector: `A1`, `A1MINI`, `A2L`, `P1S`, `P1P`, `P2S`, `X1C`, `X1E`, `X2D`, `H2C`, `H2D`, `H2DPRO`, `H2S`, or `R1`. |
| `language` | `string` | `auto` | UI language override (`auto`, `en`, `de`, `fr`, `es`, `it`, `nl`, `pl`, `pt`, `ru`, `zh`, `zh-tw`, `ja`). |
| `ams_mode` | `string` | `auto` | AMS display behavior: `auto` (shows AMS deck **only** if AMS hardware is detected), `show` (force show), or `hide` (force hide). |

---

## 🗂️ Repository Structure

```text
bambu-fleet-studio/
├── bambu-fleet-cards.js              # Self-contained HACS Lovelace bundle (Custom Cards + Embedded Model Art + 12-Language i18n)
├── custom_components/
│   └── bambu_fleet_studio/           # 100% Standalone Home Assistant Local LAN Backend (Zero External Dependencies)
│       ├── __init__.py               # Direct Port 8883 TLS MQTT client, Port 6000 TLS & Port 322 RTSPS camera engine, LAN scanner
│       ├── config_flow.py            # Home Assistant UI integration config flow
│       ├── strings.json              # Integration config flow strings
│       ├── translations/             # Localized backend config flow (en, zh-Hans, zh-Hant)
│       └── manifest.json             # Standalone Home Assistant component manifest
├── hacs.json                         # HACS manifest configuration
├── info.md                           # HACS store overview & quick-start guide
├── README.md                         # Full documentation & Dashboard Spotlight
├── CHANGELOG.md                      # Keep a Changelog version history
├── LICENSE                           # MIT License
├── docs/
│   └── screenshots/                  # High-resolution Dashboard Spotlight screenshots
│       ├── 01_fleet_studio_overview.png
│       ├── 02_conditional_ams_spotlight.png
│       ├── 03_add_edit_printer_manager.png
│       ├── 04_walkthrough_step_cards.png
│       └── 05_filament_hms_smartplug_automations.png
└── examples/
    └── bambu-fleet-dashboard.yaml    # Ready-to-import Lovelace dashboard configuration
```

---

## 🐛 Issue Tracking & Community Support

- **📋 Bug Reports & Feature Requests**: Tracked exclusively via **[Bambu Lab Fleet Studio GitHub Issues](https://github.com/everyday3d/bambu-fleet-studio/issues)**.

---

## 📄 License

Released under the [MIT License](LICENSE). Copyright © 2026 `everyday3d`.
