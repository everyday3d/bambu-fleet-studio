# Changelog

All notable changes to **Bambu Lab Fleet Studio** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
