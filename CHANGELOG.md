# Changelog

All notable changes to **Bambu Lab Fleet Studio** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-11

### Added
- **Zero-Config Automatic Printer Discovery (`#1`)**: Automatically discovers all Bambu Lab 3D printers (`A1`, `A1 Mini`, `P1S`, `P1P`, `P2S`, `X1C`, `X1E`, `X2D`, `H2C`, `H2D`, `H2S`) registered in Home Assistant via `ha-bambulab`.
- **Model-Accurate Printer Studio Cards (`#1`)**: Embedded high-resolution printer graphics paired with a 3-mode interactive viewport switcher (`📹 Live Cam` with fullscreen lightbox, `🖼️ 3MF Cover`, and `🎛️ Quick Controls`).
- **Smart Conditional AMS Deck (`#1`)**: Automatically inspects the Home Assistant Device Registry for attached AMS units (`AMS`, `AMS Lite`, `AMS 2 Pro`, `AMS HT`). Printers with an AMS render a 4-slot color-coded spool deck with live hex colors, remain bars, temperature, humidity index, and active drying status; single-extruder printers without an AMS display only a compact Direct External Spool card.
- **In-Dashboard Add, Edit, Reload & Delete Printer Manager (`#1`)**: Native integration with Home Assistant's `config_entries/flow` and `config_entries/options/flow` APIs allowing direct LAN printer onboarding (Port `8883` TLS), IP/Access Code updates, device renaming, and Bambu Cloud wizard hand-off without leaving the dashboard.
- **Card-Based 4-Step Setup Walkthrough (`#1`)**: Visual 4-card onboarding guide with model selector pills (`A1 & A1 Mini`, `P1S & P1P`, `X1C / P2S / H2D`).
- **Cross-Fleet Filament Finder Drawer (`#1`)**: Collapsible spool inventory drawer in the Command Bar aggregating all loaded AMS trays (`A1`–`A4`) and Direct External Spools across every printer with material filter pills (`All`, `PLA`, `PETG`, `ASA`, `TPU`), search input, and click-to-highlight printer navigation.
- **Conditional HMS Error & Print Pause Diagnostic Banner (`#1`)**: Zero-height when healthy; automatically renders a high-visibility amber/red alert banner when `hms_errors`, `print_error`, or filament runout occurs, with a 1-click **Bambu Wiki ↗** button.
- **Safety-Locked Smart Plug Power Toggle & Live Wattage (`#1`)**: Optional per-printer `switch.*` and `sensor.*_power` binding in the **Edit Printer** modal with live wattage (`W`) pill and automatic thermal safety lock (`🔒`) while printing or while `nozzleTemp > 60°C`.
- **1-Click Notification & Camera Snapshot Automation Builder (`#1`)**: Auto-discovers Home Assistant `notify.*` services and provides 1-click installation, YAML copy, and live test push for 3 blueprints (*Print Complete Push + Snapshot*, *HMS Error & Filament Runout Alert*, and *Auto-Off Chamber Light after 5m*).
- **Mobile & Home Assistant Companion App Optimization (`#1`)**: Added CSS `@container` (`inline-size`) queries and mobile breakpoints (`<= 680px` / `<= 420px`) with 2×2 mobile AMS spool decks, 4-column KPI bar, 2×2 touch command buttons, horizontal swipeable filter pills, 16px mobile inputs, and `dvh` bottom-sheet modals.
- **HACS Frontend Plugin Support & Dashboard Spotlight (`#1`)**: Full `hacs.json` manifest, automated `hacs/action` CI validation workflow (`.github/workflows/validate.yaml`), visual Lovelace Card Editor (`bambu-fleet-studio-editor`), expanded maker welcome note, and 5 high-resolution Dashboard Spotlight screenshots (`docs/screenshots/`).
