# 🖨️ Bambu Lab Fleet Studio `[v1.4.0]` — Home Assistant Dashboard & Custom Cards

[![Release v1.4.0](https://img.shields.io/badge/Release-v1.4.0%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)
[![HACS Default](https://img.shields.io/badge/HACS-Default%20Store-41BDF5?style=flat-square&logo=home-assistant)](https://github.com/hacs/default)
[![GitHub Issues](https://img.shields.io/github/issues/everyday3d/bambu-fleet-studio?style=flat-square&logo=github&label=Issue%20Tracker)](https://github.com/everyday3d/bambu-fleet-studio/issues)
[![License: MIT](https://img.shields.io/badge/License-MIT-amber?style=flat-square)](LICENSE)

> [!NOTE]
> **👋 Hello makers!** This is a project I've been working on for some time, and I'm excited to share it with the community.
>
> Having every Bambu Lab printer in my shop on a single, clean Home Assistant screen has been a total game-changer. Being able to glance at live camera feeds, check nozzle and bed temperatures, see exact layer progress and finish times, and immediately spot which filament colors and materials are loaded in each AMS without bouncing between Bambu Handy or Bambu Studio is ridiculously handy. It even knows which printers actually have an AMS attached (so your non-AMS printers stay clutter-free) and lets you add or manage printers right from the dashboard.
>
> Since this is an actively growing project, **expect some bugs!** If you run into anything quirky or have an idea that would make your print room easier to run, please drop a note in the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)** and I will get it fixed. I hope you enjoy using it in your workshop as much as I do!

---

## 🆕 What's New in `v1.4.0`

- **🔧 Bambu Lab H2C 7-Nozzle Changer & H2D / X2D Dual-Nozzle Support (*Untested — Community Feedback Needed!*)**:
  - **H2C Vortek 7-Nozzle Changer Rack**: H2C printer cards now include a dedicated **Vortek 7-Nozzle Changer** section showing the **fixed Left nozzle** alongside all **6 swappable Right induction hotends (`R1`–`R6`)**, including which nozzle is currently mounted, which slots are docked or empty, nozzle sizes (`0.2mm`–`0.8mm`), flow types (`Standard` or `High-Flow`), and print hours.
  - **Dual-Nozzle Temperatures (`L + R`)**: `H2C`, `H2D`, `H2D Pro`, and `X2D` cards now show both **Left (`L`)** and **Right (`R`)** nozzle temperatures and targets side-by-side, and Smart Plug safety locks now wait until **both** nozzles cool below `60°C` before allowing power-off.
  - **🧪 Help Us Test `H2C` & `X2D`**: I don't have a physical `H2C` or `X2D` in my shop yet, so this support is marked **Beta / Untested**. If you own an `H2C` or `X2D`, please try it out and let me know in **[GitHub Issues](https://github.com/everyday3d/bambu-fleet-studio/issues)** or **[Discussions](https://github.com/everyday3d/bambu-fleet-studio/discussions)** how it looks and if anything needs tweaking!
- **🎉 Now Available in the Official HACS Store**:
  - **Bambu Lab Fleet Studio** has been reviewed and merged into the official **HACS Default Store**! You can now search for **Bambu Lab Fleet Studio** directly inside HACS and install it in one click, with improved camera streaming security and automatic repair alerts if a printer's LAN Access Code ever changes.

---

## 🌟 What It Does for Your Print Room

Default Home Assistant entity lists can quickly turn into a wall of scattered sensors—and often show empty AMS slots even on printers that don't have an AMS. **Bambu Lab Fleet Studio** replaces all of that with one clean, easy-to-read workshop dashboard:

- **🔌 Works 100% Locally on Your Home Network (No Other Add-Ons Needed)**: Connects directly to your Bambu Lab printers over your local Wi-Fi or Ethernet network. You don't need Bambu Cloud or any other Home Assistant integration installed—just your printer's local IP address and 8-character LAN Access Code.
- **📹 Built-In Live Camera Feeds for Every Series**: Watch live camera streams right inside each printer card (or click to open a fullscreen player) across all Bambu Lab printers—including `A1`, `A1 Mini`, `P1P`, `P1S`, `P2S`, `X1C`, `X1E`, `H2C`, `H2D`, `H2S`, and the `R1` Laser.
- **🖼️ Artwork for All 14 Bambu Printers, R1 Laser & Every AMS Model**: Automatically shows matching studio photos for **`A1`**, **`A1 Mini`**, **`A2L`**, **`P1S`**, **`P1P`**, **`P2S`**, **`X1C`**, **`X1E`**, **`X2D`**, **`H2C`**, **`H2D`**, **`H2D Pro`**, **`H2S`**, and the **`R1` CO2 Laser**, plus **`AMS`**, **`AMS Lite`**, **`AMS 2 Pro`**, and **`AMS HT`**.
- **🎨 Smart AMS Display (Zero Clutter on Non-AMS Printers)**: Automatically detects whether a printer has one or more AMS units attached. Printers with an AMS show all 4 spool slots with live filament colors, material types, remaining spool percentage, and AMS humidity; printers without an AMS simply show a clean External Spool card instead of empty slots.
- **📡 1-Click Network Printer Discovery**: Click **`➕ Add Printer`** and the dashboard scans your local network to find your Bambu printers automatically—filling in the model, IP address, and 15-character serial number for you. All you have to type is the 8-character Access Code from the printer's screen.
- **🔍 "Which Printer Has My Spool?" Filament Finder**: Open the **Filament Studio** tab to search across every loaded spool in your shop by material (`PLA`, `PETG`, `ASA`, `TPU`) or color. Click any spool to jump straight to that printer's card.
- **🔔 Easy 1-Click Notifications, WLED Progress Bars & Smart Plug Safety**:
  - **Phone Push Alerts with Live Photo**: Get a notification on your phone when a print finishes (or pauses with an error), complete with a camera snapshot, how many grams/meters of filament the job used, and a button that jumps right to that printer card.
  - **WLED Print Progress Light Bar**: Link any WLED light strip to grow from `0%` to `100%` as your print progresses, flash green 3 times when the print finishes, and turn itself off 5 minutes later.
  - **Smart Speaker Announcements**: Have your smart speakers announce when a print finishes (with optional Quiet Hours at night).
  - **Safety-Locked Smart Plugs**: Link a smart plug to see live power draw (`W`) on the card. The power button automatically locks while printing or while any nozzle is hotter than `60°C` so you never accidentally cut power to a hot extruder—and can even power the printer off automatically once it cools down.
- **⏱️ Print Hours & Filament Odometer + Build Plate Tracker**: Keeps track of each printer's total print hours alongside estimated meters, kilograms, and 1 kg spools of filament used—plus lets you record which build plate (*Bambu Textured/Smooth PEI*, *SuperTack*, *BIQU CryoGrip Glacier/Frostbite*, etc.) is currently on each bed.
- **🌐 12 Languages Built In**: Supports **English**, **German**, **French**, **Spanish**, **Italian**, **Dutch**, **Polish**, **Portuguese**, **Russian** *(untested — feedback welcome!)*, **Simplified Chinese** *(untested — feedback welcome!)*, **Traditional Chinese** *(untested — feedback welcome!)*, and **Japanese**, with a quick **`🌐`** switcher in the top bar.

---

## 📸 Dashboard Spotlight

### 1. Multi-Printer Fleet Command Center
![Bambu Lab Fleet Studio Overview](docs/screenshots/01_fleet_studio_overview.png)

**At a Glance:**
- **Top Summary Bar**: Shows how many printers are online, actively printing, or need attention, with quick buttons for **Language**, **Filament Finder**, **Automations**, **Setup Guide**, and **Add Printer**.
- **Side-by-Side Printer & Live Camera**: Each card pairs the printer's photo with its live camera stream, 3MF model preview, and quick controls (Light, Pause, Resume, Stop, Print Speed).
- **Job Progress & Finish Time**: Shows the active file name, progress bar, current layer (`Layer 194 / 285`), time remaining, and exact clock time when the print will finish.
- **Temperatures, Fans & Odometer**: Clean tiles for Nozzle Temp, Bed & Chamber Temp, Cooling Fans, and lifetime hours/filament used.

---

### 2. Smart AMS Detection — Only Shows What You Actually Have
![Smart Conditional AMS Detection Spotlight](docs/screenshots/02_conditional_ams_spotlight.png)

- **Printers with an AMS (Left)**: Shows each attached AMS unit (`AMS`, `AMS Lite`, `AMS 2 Pro`, `AMS HT`) with all 4 spools, colors, material badges, and humidity alerts when desiccant is getting damp.
- **Printers without an AMS (Right)**: Skips the 4-slot AMS box completely and shows a simple External Spool card.

---

### 3. Add, Edit & Manage Printers Right from the Dashboard
![Add Edit Printer Manager Spotlight](docs/screenshots/03_add_edit_printer_manager.png)

- **Auto-Discover Printers on Your Wi-Fi/LAN**: Scan your network to find printers automatically, update an IP address if your router changes it, pick custom printer or AMS artwork, or link a Smart Plug without touching any YAML files.

---

### 4. Built-In 4-Step Visual Setup Guide
![4-Step Visual Walkthrough Cards](docs/screenshots/04_walkthrough_step_cards.png)

- Need help finding your printer's Access Code or Serial Number on the touchscreen? Click **Setup Guide** in the top bar for simple step-by-step cards for `A1 / A1 Mini`, `P1S / P1P / P2S`, `X1C / X1E / X2D`, `H2C / H2D / H2S`, and `R1 Laser`.

---

### 5. Filament Finder, Error Alerts, Smart Plugs & Automations
![Advanced Fleet Intelligence Spotlight](docs/screenshots/05_filament_hms_smartplug_automations.png)

- **Filament Finder**: Filter all spools across your shop by material or color family.
- **Automatic Error Banner**: Stays hidden when everything is running smoothly, and pops up with a plain-English explanation and a **Bambu Wiki ↗** link if a printer pauses or reports a fault.
- **1-Click Automations**: Set up phone alerts, WLED progress bars, voice announcements, low-spool warnings, and safe cooldown power-off in seconds.

---

## 📦 How to Install

### Requirements
1. **Home Assistant** `2024.6.0` or newer.
2. **Nothing else!** Everything needed to talk to your printers and display the dashboard is included in one package.

### Option A: Install via HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Search for **Bambu Lab Fleet Studio** and click **Download**. *(If your HACS catalog hasn't refreshed yet, you can also click the **`⋮`** menu in the top-right of HACS → **Custom repositories** → paste `https://github.com/everyday3d/bambu-fleet-studio` → select **Integration**.)*
3. **Restart Home Assistant**.
4. Go to **Settings → Devices & Services → Add Integration**, search for **Bambu Lab Fleet Studio**, and add it.

### Option B: Manual Copy
1. Copy the `custom_components/bambu_fleet_studio/` folder into your Home Assistant `/config/custom_components/bambu_fleet_studio/` directory and restart Home Assistant.
2. Go to **Settings → Devices & Services → Add Integration** and add **Bambu Lab Fleet Studio**.

---

## ⚙️ Adding the Dashboard Card

### 1. Full Workshop Dashboard (Recommended)

Create a new dashboard (or view) in Home Assistant, set the view type to **Panel (1 card)**, and add a **Manual** card with:

```yaml
type: custom:bambu-fleet-studio
title: Bambu Lab Fleet Studio
subtitle: Real-Time Telemetry, Live Camera Feeds & Smart Conditional AMS
```

Once the card appears, click **`➕ Add Printer`** in the top-right corner to discover and pair your printers!

### 2. Single-Printer Card (Optional)

If you want to place a single printer card on an existing dashboard page alongside other Home Assistant cards:

```yaml
type: custom:bambu-printer-studio-card
name: Bambu P1S
prefix: p1s_01p00b200000002
printer_model: P1S
ams_mode: auto
```

| Option | Default | Description |
| :--- | :--- | :--- |
| `prefix` | Optional | Printer identifier (`<model>_<serial>`, e.g. `a1_03900a100000001`). |
| `name` | Auto | Display name shown at the top of the card. |
| `printer_model` | `auto` | Model artwork override (`A1`, `A1MINI`, `A2L`, `P1S`, `P1P`, `P2S`, `X1C`, `X1E`, `X2D`, `H2C`, `H2D`, `H2DPRO`, `H2S`, `R1`). |
| `language` | `auto` | Language override (`auto`, `en`, `de`, `fr`, `es`, `it`, `nl`, `pl`, `pt`, `ru`, `zh`, `zh-tw`, `ja`). |
| `ams_mode` | `auto` | `auto` (only show AMS if attached), `show` (always show), or `hide` (always hide). |

---

## 🗂️ What's in the Repo

```text
bambu-fleet-studio/
├── custom_components/
│   └── bambu_fleet_studio/           # Home Assistant integration & dashboard card bundle
│       ├── __init__.py               # Local LAN printer connection, camera streaming & automations
│       ├── bambu-fleet-cards.js      # Dashboard UI, printer artwork & 12-language translations
│       ├── config_flow.py            # Home Assistant setup flow
│       ├── strings.json              # Setup text
│       ├── translations/             # Setup translations (en, zh-Hans, zh-Hant)
│       └── manifest.json             # Integration manifest
├── hacs.json                         # HACS store configuration
├── info.md                           # HACS store summary page
├── README.md                         # Main documentation
├── CHANGELOG.md                      # Version history
├── LICENSE                           # MIT License
└── examples/
    └── bambu-fleet-dashboard.yaml    # Example dashboard YAML
```

---

## 🗺️ Project Roadmap & Completed Milestones ([Community Poll #30](https://github.com/everyday3d/bambu-fleet-studio/discussions/30))

Have an idea or want to help pick what gets built next? Vote with a 👍 in **[📊 Roadmap Poll #30](https://github.com/everyday3d/bambu-fleet-studio/discussions/30)** or say hello in **[👋 Discussion #29](https://github.com/everyday3d/bambu-fleet-studio/discussions/29)**!

### 🚧 Upcoming Local-LAN Roadmap (`v1.4.x` — [Vote in Poll #30](https://github.com/everyday3d/bambu-fleet-studio/discussions/30))
- [ ] **1️⃣ 📊 Print Job History, Two-Way Spoolman Sync & Cost Tracker** *(~~Low-spool alerts~~ ✅ & ~~Filament grams in push alerts~~ ✅ shipped!)*: Keep a local log of finished and failed prints with print time, filament used, automatic **Spoolman** spool deduction, and estimated filament cost per print.
- [ ] **2️⃣ 🤖 AI Print Failure & Spaghetti Watchdog (`Ollama` / `Gemini` / `OpenAI` / `Claude` / `OpenRouter` / HA AI)**: Periodically check live camera snapshots using your choice of local **Ollama** or cloud AI vision to spot spaghetti, first-layer peeling, or nozzle blobs—with optional auto-pause and phone alerts.
- [ ] **3️⃣ 🎯 Skip Failed Objects Mid-Print & Live Temp/Fan Sliders** *(NEW)*: If one part pops loose on a multi-part plate, tap to skip just that object so the rest of the build plate finishes cleanly—plus adjust nozzle temp, bed temp, and fan speeds right from the card.
- [ ] **4️⃣ 📂 Printer SD Card File Browser & 1-Click Reprint**: Browse `.3mf` and `.gcode` files stored on your printer's MicroSD card over your local network, preview plate thumbnails, and start a reprint from the dashboard.
- [ ] **5️⃣ 🛠️ Maintenance Reminder Tracker & Service Log**: Simple countdown reminders based on your printer's actual print hours and filament used (cleaning carbon rods, greasing lead screws, swapping nozzles/PTFE tubes, and replacing carbon filters) with a 1-click reset log.
- [ ] **6️⃣ 🎞️ Automatic Layer Timelapses & Combined Filament + Electricity Cost Log** *(NEW)*: Save a camera snapshot on each layer change to build downloadable MP4 timelapses, and combine filament used (`g`) with Smart Plug electricity (`kWh`) to see true total print cost.
- [ ] **7️⃣ 🌡️ Workshop Air Quality & BentoBox / Exhaust Fan Automation** *(NEW)*: Link room or enclosure air quality sensors (`VOC`, `PM2.5`) and BentoBox / exhaust fans so filtration turns on automatically when printing `ABS`, `ASA`, `PA-CF`, or `PC`.
- [ ] **8️⃣ 📱 Wall-Tablet Kiosk Mode & Multi-Camera Grid View** *(NEW)*: A compact wall-tablet layout with a 2×2 or 3×2 live camera grid for print farms, plus community translation polish for Russian, Simplified Chinese, and Traditional Chinese.

> **☁️ Note on Bambu Firmware Limits**:
> Because **Bambu Lab Fleet Studio** talks directly to your printers over your local network without using Bambu Cloud, a couple of features that Bambu firmware locks to the printer's physical touchscreen—specifically **starting an active AMS drying cycle remotely** and **editing custom non-RFID spool slots**—must still be started on the printer screen. *(Reading live AMS humidity, temperature, and Bambu RFID spools works 100% locally!)*

### ✅ Completed & Shipped Roadmap Milestones
- [x] ~~**🔌 Direct Local Network Printer & Camera Connection (No Third-Party Add-Ons Needed)** (`#15`)~~ ✅
- [x] ~~**⏱️ Per-Printer Print Hours & Filament Odometer (`m` / `km` / `kg` / `~Spools`)** (`#24`)~~ ✅
- [x] ~~**🛏️ Build Plate Selector (Official Bambu Lab + BIQU CryoGrip & Panda Plates)** (`#25`)~~ ✅
- [x] ~~**🎨 Shop-Wide Filament Finder & Automatic Color Naming** (`#21`, `#26`)~~ ✅
- [x] ~~**📦 Low-Spool Filament Warning ($\le 15\%$ Remaining)** (`#33`)~~ ✅
- [x] ~~**🌈 WLED Live Print Progress Bar (`0%` → `100%`) with Completion Flash & Auto-Off** (`#33`, `#35`)~~ ✅
- [x] ~~**🔊 Smart Speaker Voice Announcements (with Quiet Hours) & Safe Cooldown Smart Plug Auto-Off** (`#33`)~~ ✅
- [x] ~~**🕒 Offline Printer "Last Seen" Timestamp** (`#34`)~~ ✅
- [x] ~~**🎯 Phone Push Notifications with Filament Grams Used, Camera Snapshot & 1-Tap Jump to Printer Card** (`#35`, `#36`)~~ ✅
- [x] ~~**⬆️ Version Badge & Update Notification in Top Bar** (`#37`)~~ ✅
- [x] ~~**🔧 Bambu Lab H2C Vortek 7-Nozzle Changer (`1L + 6R`) & H2D / X2D Dual-Nozzle Support (*Untested on H2C & X2D — Community Feedback Needed!*)** (`#41`)~~ ✅
- [x] ~~**🎉 Official HACS Default Store Release & Security Improvements** (`#38`, `#39`, `#40`)~~ ✅

---

## 🐛 Questions, Feedback & Bug Reports

- **📋 Report a Bug or Request a Feature**: **[GitHub Issues](https://github.com/everyday3d/bambu-fleet-studio/issues)**
- **💬 Chat & Vote on Features**: **[GitHub Discussions](https://github.com/everyday3d/bambu-fleet-studio/discussions)** and **[Roadmap Poll #30](https://github.com/everyday3d/bambu-fleet-studio/discussions/30)**

---

## 📄 License

Released under the [MIT License](LICENSE). Copyright © 2026 `everyday3d`.
