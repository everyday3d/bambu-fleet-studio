# 🖨️ Bambu Lab Fleet Studio `v1.3.3`

[![Release v1.3.3](https://img.shields.io/badge/Release-v1.3.3%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)

> **👋 Hello makers!** This is a project I've been working on for some time, and I think I'm finally ready to release it to the community.
>
> Having every Bambu Lab printer in my shop on a single, clean Home Assistant screen has been a total game-changer—glancing at live camera streams, checking nozzle/bed temps, tracking layer progress & ETAs, and immediately seeing which filament spools are loaded in each AMS without bouncing between apps is ridiculously handy. It even detects which printers actually have an AMS attached (keeping non-AMS cards clean) and lets you add or manage printers right from the dashboard.
>
> Expect some bugs—please use the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)** and I will get it fixed! I hope you enjoy it as much as I do.

A professional, card-based Home Assistant Lovelace dashboard and custom card suite for **Bambu Lab** 3D printers, lasers & AMS filament systems (`A1`, `A1 Mini`, `A2L`, `P1P`, `P1S`, `P2S`, `X1C`, `X1E`, `X2D`, `H2C`, `H2D`, `H2D Pro`, `H2S`, the **`R1` 55W CO2 Laser Cutter & Engraver**, plus **`AMS`**, **`AMS Lite`**, **`AMS 2 Pro`**, and **`AMS HT`**).

![Bambu Lab Fleet Studio Overview](https://raw.githubusercontent.com/everyday3d/bambu-fleet-studio/main/docs/screenshots/01_fleet_studio_overview.png)

## ✨ Key Highlights

- **🔌 100% Standalone Local LAN Engine (`Zero External Dependencies`)**: Includes its own built-in Home Assistant backend (`custom_components/bambu_fleet_studio/`) that connects **directly** to your Bambu Lab printers over Port `8883` TLS MQTT, Port `6000` TLS camera streaming (`A1`, `A1 Mini`, `P1P`, `P1S`), and Port `322` RTSPS 1080p video decoding (`P2S`, `X1`, `H2`, `R1`)—**no `ha-bambulab` or third-party integration required**!
- **⏱️ Per-Printer Extrusion Odometer (`m` / `km` / `kg` / `Spools`) & Model-Aware Build Plate Selector**: Tracks cumulative lifetime print hours and extruded filament (`m` / `km` / `kg` / `~Spools`) in real time over Local LAN MQTT with 1-click **`⚡ Est. from Hours`** calibration, plus a bed-size-aware **Build Plate Selector** covering all **Official Bambu Lab Plates** and **BIQU CryoGrip Pro Glacier / Frostbite & Panda Plates**.
- **🌐 12-Language Internationalization (`i18n`)**: Built-in translations for **English (`en`)**, **Deutsch (`de`)**, **Français (`fr`)**, **Español (`es`)**, **Italiano (`it`)**, **Nederlands (`nl`)**, **Polski (`pl`)**, **Português (`pt`)**, **Русский (`ru` — *untested; community feedback needed!*)**, **简体中文 (`zh` — *untested; community feedback needed!*)**, **繁體中文 (`zh-tw` — *untested; community feedback needed!*)**, and **日本語 (`ja`)** with automatic `hass.language` detection and an instant Command Bar **`🌐`** language selector.
- **🖼️ Complete 14-Model Printer & R1 Laser Photography**: Embedded high-resolution studio renders for **`A1`**, **`A1 Mini`**, **`A2L`**, **`P1S`**, **`P1P`**, **`P2S`**, **`X1C`**, **`X1E`**, **`X2D`**, **`H2C`**, **`H2D`**, **`H2D Pro`**, **`H2S`**, and the **`R1` (55W CO2 Laser)**.
- **🎨 Embedded Studio Artwork for AMS Lite, AMS HT, AMS 2 Pro & AMS**: High-resolution studio renders for **`AMS Lite`** (4-spool rotary feeder), **`AMS HT`** (85°C High-Temp active dryer), **`AMS 2 Pro`**, and **`AMS`** displayed inside the AMS header, Edit Device modal, and Hardware Lineup gallery.
- **🎨 Smart Conditional Multi-AMS Deck, Live `% RH` & Automatic `°F` → `°C` Normalization**: Automatically inspects live MQTT `print.ams.ams[]` payloads across single or daisy-chained AMS units (`AMS #1`, `AMS #2`, etc.), normalizes any Imperial (`°F`) printer/AMS temperature sensors to 3D-printing Celsius (`°C`), renders **`🌬️ Open-Air Rotary`** on sensorless `AMS Lite` feeders, and displays real relative humidity (`% RH`), amber/red wet-filament highlighting, inline **Chamber Temp (`°C`)**, **Aux/Chamber Fan `%`**, **Door Open/Closed**, and **Exact Finish Clock Time (`1h 12m • 7:42 PM`)**.
- **📡 Built-In LAN Network Auto-Discovery & 15-Char Serial Lookup**: Automatically sweeps your local `/24` subnet on Port `8883` TLS, validates `BBL CA` certificates, extracts the **15-character Serial Number**, and infers the hardware model (`P2S`, `A1`, `A1 Mini`, `P1S`, `X1C`, `H2D`) for 1-click pairing—plus a **`📡 Find IP on LAN`** button in **Edit Device**.
- **🎨 Cross-Fleet Filament Finder**: Search and filter every loaded AMS slot and External Spool across your entire fleet by material (`PLA`, `PETG`, `ASA`, `TPU`) or color with 1-click jump to the printer card.
- **🚨 Conditional HMS Error & Print Pause Banner**: Hidden (`0px`) when healthy; automatically expands with active HMS error descriptions and a 1-click **Bambu Wiki ↗** button when attention is needed.
- **⚡ Safety-Locked Smart Plug & Live Wattage (`W`)**: Optional per-printer smart plug binding (`switch.*` & `sensor.*_power`) with thermal safety lock (`🔒`) while printing or while `nozzleTemp > 60°C`.
- **🔔 1-Click Notification & Camera Snapshot Automation Builder**: Deploy native Home Assistant automations for print-complete camera snapshots, HMS error push alerts, and 5-minute chamber light auto-off in 1 click.
- **📹 1080p RTSPS & MJPEG Live Camera Viewport + Lightbox**: Flicker-free double-buffered 1920×1080 RTSPS live feed for `P2S`, `H2`, `X1`, and `R1` alongside native Port `6000` TLS streaming for `A1`, `A1 Mini`, `P1S`, and `P1P`, with DOM-preserved viewports, scroll-anchored card buttons, and an interactive **Enable LAN Only Liveview** guide.
- **➕ Built-In Standalone Add / Edit / Delete Printer Manager**: Add new printers or R1 Lasers directly via the standalone LAN engine, customize printer & AMS artwork, reconnect streams, or remove devices directly from the dashboard.
- **📖 4-Card Visual Setup Walkthrough & Hardware Lineup Gallery**: Scannable 4-step onboarding cards with 6 series tabs (`A1 / Mini / A2L`, `P1S / P1P / P2S`, `X1C / X1E / X2D`, `H2C / H2D / H2S`, `R1 CO2 Laser`, `AMS Lite / AMS HT`) and a clickable 17-item hardware gallery—no walls of text.
- **📱 Mobile & HA Companion App Ready**: Responsive CSS `@container` queries, 2×2 mobile AMS spool grids, thumb-friendly 2×2 action buttons, and `dvh` bottom-sheet modals.

## 🚀 Quick Start YAML

Add a new panel view to your dashboard and paste:

```yaml
type: custom:bambu-fleet-studio
title: Bambu Lab Fleet Studio
subtitle: Real-Time Telemetry, Live Camera Feeds & Smart Conditional AMS
```

For bug reports and feature requests, visit the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)**.
