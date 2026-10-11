# 🖨️ Bambu Lab Fleet Studio — Home Assistant Dashboard & Custom Cards

[![Release v1.0.0](https://img.shields.io/badge/Release-v1.0.0%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom%20Plugin-41BDF5?style=flat-square&logo=home-assistant)](https://github.com/hacs/integration)
![BoxerDawg 3D Ecosystem](https://img.shields.io/badge/Ecosystem-BoxerDawg%203D-38bdf8?style=flat-square)
[![GitHub Issues](https://img.shields.io/github/issues/everyday3d/bambu-fleet-studio?style=flat-square&logo=github&label=Issue%20Tracker)](https://github.com/everyday3d/bambu-fleet-studio/issues)
[![License: MIT](https://img.shields.io/badge/License-MIT-amber?style=flat-square)](LICENSE)

> [!NOTE]
> **👋 Hello makers!** This is a project I've been working on for some time, and I think I'm finally ready to release it to the community.
>
> Having every Bambu Lab printer in my shop on a single, clean Home Assistant screen has been a total game-changer—being able to glance at live camera feeds, check nozzle/bed temps, see exact layer progress & ETAs, and immediately spot which filament colors and materials are loaded in each AMS without bouncing between Bambu Handy or Bambu Studio is ridiculously handy. It even knows which printers actually have an AMS attached (so your non-AMS printers stay clutter-free) and lets you add or manage printers right from the dashboard.
>
> Since this is a fresh release, **expect some bugs!** If you run into anything quirky or have an idea that would make your print room easier to run, please drop a ticket in the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)** and I will get it fixed! I hope you enjoy using it in your workshop as much as I do.

> **Part of the BoxerDawg 3D Ecosystem** — A professional, card-based Home Assistant Lovelace dashboard and zero-dependency Web Component suite (`bambu-fleet-cards.js`) purpose-built for managing multi-printer **Bambu Lab** 3D printing fleets (`A1`, `A1 Mini`, `P1P`, `P1S`, `X1C`, `X1E`).

---

## 🌟 Why Bambu Lab Fleet Studio?

Default Home Assistant entity lists clutter your screen with dozens of ungrouped sensors and render empty AMS filament slots even on printers that do not have an AMS attached. **Bambu Lab Fleet Studio** replaces walls of text and scattered entities with a sleek, dark-glass industrial command center:

- **🖼️ Model-Accurate Printer Photography**: Built-in, embedded high-resolution studio renders for **Bambu Lab A1**, **Bambu Lab P1S / X1C**, and **Bambu Lab A1 Mini** automatically matched to each printer's hardware model.
- **🎨 Smart Conditional AMS Detection**: Automatically inspects Home Assistant's Device Registry and `tray_1`–`tray_4` entities. **Only printers physically equipped with an AMS, AMS Lite, or AMS 2 Pro render the 4-slot AMS Spool Deck**—non-AMS printers cleanly display a compact **Direct External Spool** badge with zero wasted space.
- **📹 Live Camera Viewport + Instant Stream Lightbox**: Side-by-side model artwork and live camera feed with 1-click full-screen stream modal.
- **➕ Built-In Fleet Manager (Add / Edit / Reload / Delete)**: Add new Bambu Lab printers (LAN Mode or Bambu Cloud), inspect device IDs & serial numbers, reload `bambu_lab` config entries, or remove printers directly from the dashboard UI.
- **📖 4-Card Visual Onboarding Walkthrough**: Interactive 4-step card grid guiding operators through LAN Mode IP/Access Code discovery, 15-character Serial Number lookup, and 1-click Home Assistant pairing—without a wall of text.
- **🔒 100% Self-Contained & Privacy-First**: Zero external CDN dependencies, zero hardcoded tokens or IP addresses, and native integration with Home Assistant's [`hass-bambulab`](https://github.com/greghesp/ha-bambulab) device registry.

---

## 📸 Dashboard Spotlight

### 1. Multi-Printer Fleet Command Center
![Bambu Lab Fleet Studio Overview](docs/screenshots/01_fleet_studio_overview.png)

**What You See in the Fleet Studio Overview:**
- **Top Command Header**: Real-time fleet KPI pills (**Total Printers**, **Online**, **Active Prints**, **AMS Units**) paired with instant action triggers (`+ Add Printer`, `Walkthrough`, `Manage`).
- **Hero Visual Split**: Each printer card pairs its model-accurate studio photograph on the left with a live `camera.*` stream viewport on the right.
- **Print Job & Layer Telemetry Bar**: Displays active `.3mf` / `.gcode` job name, completion percentage, glowing progress bar, current/total layer counter (`Layer 194 / 285`), and live remaining ETA.
- **4-Tile Hardware Telemetry Grid**: Scannable cards for **Nozzle Temp** (actual vs. target), **Bed Temp** (actual vs. target), **Speed Profile & Chamber Temp**, and **Cooling Fans & Wi-Fi RSSI**.

---

### 2. Smart Conditional AMS Engine — Zero Wasted Space
![Smart Conditional AMS Detection Spotlight](docs/screenshots/02_conditional_ams_spotlight.png)

**How Conditional AMS Detection Works:**
- **AMS-Equipped Printers (Left — Bambu A1 + AMS Lite / Bambu P1S + AMS 2 Pro)**: Automatically detects child AMS devices in Home Assistant (`via_device_id`) and active `tray_1..tray_4` entities. Renders all 4 filament slots with live RFID hex color swatches, material type (`PLA`, `PETG`, `ASA`, `PLA-CF`, `TPU`), active slot glow border, and AMS humidity/temperature badges.
- **Direct-Spool Printers (Right — Bambu A1 Mini without AMS)**: Detects that no AMS hardware is attached and **automatically omits the 4-slot AMS deck**, rendering a clean **Direct External Spool Holder** card instead.

---

### 3. Built-In Printer Fleet Manager (Add, Edit, Reload & Delete)
![Add Edit Printer Manager Spotlight](docs/screenshots/03_add_edit_printer_manager.png)

**In-Dashboard Fleet Administration:**
- **Interactive Model Selector & Preview**: Preview **Bambu A1**, **Bambu A1 Mini**, **Bambu P1S**, or **Bambu X1C** hardware capabilities before pairing.
- **Direct Config Flow Launcher**: Launch Home Assistant's native `bambu_lab` configuration flow in 1 click for either **Local LAN Mode** (Direct MQTT port `8883` + RTSP stream) or **Bambu Cloud**.
- **Per-Printer Lifecycle Actions**: Reload stuck integration config entries (`homeassistant/config_entries/reload`), open the native HA Device Registry page, or delete a printer config entry (`DELETE /api/config/config_entries/entry/<id>`) with confirmation.

---

### 4. 4-Card Visual Setup Walkthrough
![4-Step Visual Walkthrough Cards](docs/screenshots/04_walkthrough_step_cards.png)

**Zero Walls of Text:**
- Clicking **Walkthrough** in the Command Bar (or navigating to the `Setup Guide` view tab) reveals a 4-card visual onboarding grid covering **Step 01 (LAN Mode & Access Code)**, **Step 02 (15-Char Serial Number)**, **Step 03 (Fleet Studio Modal Pairing)**, and **Step 04 (Auto-Discovery & Smart AMS)**.

---

## 📦 Installation

### Prerequisites
1. **Home Assistant** `2024.6.0` or newer.
2. **[ha-bambulab](https://github.com/greghesp/ha-bambulab)** custom integration installed via HACS and configured with at least one Bambu Lab printer (or use Fleet Studio's `+ Add Printer` button to set up your first printer).

---

### Option A: Install via HACS (Recommended)

1. Open **HACS** in your Home Assistant sidebar.
2. Click the **three-dot menu (`⋮`)** in the top-right corner and select **Custom repositories**.
3. Enter the repository URL:
   ```text
   https://github.com/everyday3d/bambu-fleet-studio
   ```
4. Select category **Dashboard** (or **Plugin** in older HACS versions) and click **Add**.
5. Find **Bambu Lab Fleet Studio** in HACS and click **Download**.
6. HACS will automatically register `/hacsfiles/bambu-fleet-studio/bambu-fleet-cards.js` in your Lovelace resources.

---

### Option B: Manual Installation

1. Download [`bambu-fleet-cards.js`](https://github.com/everyday3d/bambu-fleet-studio/releases/latest/download/bambu-fleet-cards.js) from the [Latest Release](https://github.com/everyday3d/bambu-fleet-studio/releases/latest).
2. Copy `bambu-fleet-cards.js` into your Home Assistant `config/www/` directory (`/homeassistant/www/bambu-fleet-cards.js`).
3. In Home Assistant, go to **Settings → Dashboards → `⋮` (top right) → Resources → Add Resource**:
   - **URL**: `/local/bambu-fleet-cards.js`
   - **Resource type**: `JavaScript Module`

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
| `prefix` | `string` | **Required** | Entity object ID prefix created by `ha-bambulab` (e.g. `a1_03900a100000001` or `p1s_01p00b200000002`). |
| `name` | `string` | Auto-detected | Display name shown in the card header (e.g. `Bambu A1`, `Bambu P1S`). |
| `printer_model` | `string` | `auto` | Hardware model artwork selector: `auto`, `A1`, `P1S` (also covers `P1P`/`X1C`), or `A1MINI`. |
| `ams_mode` | `string` | `auto` | AMS display behavior: `auto` (shows AMS deck **only** if AMS hardware is detected), `show` (force show), or `hide` (force hide). |

---

## 🗂️ Repository Structure

```text
bambu-fleet-studio/
├── bambu-fleet-cards.js              # Self-contained HACS Lovelace bundle (Custom Cards + Embedded Model Art)
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
│       └── 04_walkthrough_step_cards.png
└── examples/
    └── bambu-fleet-dashboard.yaml    # Ready-to-import Lovelace dashboard configuration
```

---

## 🐛 Issue Tracking & BoxerDawg 3D Ecosystem

This project is developed and maintained as part of the **BoxerDawg 3D Ecosystem**:

- **📋 Bug Reports & Feature Requests**: Tracked exclusively via **[Bambu Lab Fleet Studio GitHub Issues](https://github.com/everyday3d/bambu-fleet-studio/issues)**.

---

## 📄 License

Released under the [MIT License](LICENSE). Copyright © 2026 BoxerDawg 3D (`everyday3d`).
