# 🖨️ Bambu Lab Fleet Studio `v1.4.1`

<p align="center">
  <img src="https://raw.githubusercontent.com/everyday3d/bambu-fleet-studio/main/icon.png" width="128" height="128" alt="Bambu Lab Fleet Studio (BFleet)" style="border-radius: 28px;" />
</p>

[![Release v1.4.1](https://img.shields.io/badge/Release-v1.4.1%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)

> **👋 Hello makers!** This is a project I've been working on for some time, and I'm excited to share it with the community.
>
> Having every Bambu Lab printer in my shop on a single, clean Home Assistant screen has been a total game-changer—glancing at live camera streams, checking nozzle and bed temperatures, tracking layer progress and finish times, and immediately seeing which filament spools are loaded in each AMS without bouncing between apps is ridiculously handy. It even detects which printers actually have an AMS attached (keeping non-AMS cards clean) and lets you add or manage printers right from the dashboard.
>
> Expect some bugs—please use the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)** and I will get it fixed! I hope you enjoy using it in your workshop as much as I do.

A clean, card-based Home Assistant dashboard for **Bambu Lab** 3D printers, lasers, and AMS filament systems (`A1`, `A1 Mini`, `A2L`, `P1P`, `P1S`, `P2S`, `X1C`, `X1E`, `X2D`, `H2C`, `H2D`, `H2D Pro`, `H2S`, the **`R1` CO2 Laser**, plus **`AMS`**, **`AMS Lite`**, **`AMS 2 Pro`**, and **`AMS HT`**).

![Bambu Lab Fleet Studio Overview](https://raw.githubusercontent.com/everyday3d/bambu-fleet-studio/main/docs/screenshots/01_fleet_studio_overview.png)

## 🆕 What's New in `v1.4.1`

- **🛠️ Printer Maintenance Reminders & 1-Click Reset Log**:
  - Keeping up with routine maintenance across multiple printers is easy to forget until a print starts acting up. Each printer now keeps track of its own print hours and reminds you when it's time to **wipe down carbon rods or lubricate linear rails** (every `250h`), **clean and regrease the Z lead screws** (every `500h`), **brush out the extruder gears and check the nozzle** (every `500h`, or clean the optics on an `R1` Laser), and **swap out the carbon air filter** on enclosed printers (every `400h`).
  - You'll see a small **`🛠️ OK`** or **`🛠️ Due`** badge right inside the Odometer box on each printer card. When you finish cleaning or greasing a printer, just open **✏️ Edit Device** and click **✓ Reset** next to that item (or **✓ Reset All**) to start the countdown fresh!
- **🔧 Bambu Lab H2C 7-Nozzle Changer & H2D / X2D Dual-Nozzle Support (*Untested — Community Feedback Needed!*)**:
  - **H2C 7-Nozzle Changer Rack**: H2C printer cards now show the **fixed Left nozzle** alongside all **6 swappable Right hotends (`R1`–`R6`)**, including which nozzle is currently loaded, which slots are parked or empty, nozzle sizes (`0.2mm`–`0.8mm`), and print hours.
  - **Dual-Nozzle Temperatures (`L + R`)**: `H2C`, `H2D`, `H2D Pro`, and `X2D` cards now display both **Left (`L`)** and **Right (`R`)** nozzle temperatures side-by-side, and Smart Plug safety locks wait until **both** nozzles cool below `60°C` before allowing power-off.
  - **🧪 Help Us Test `H2C` & `X2D`**: I don't have a physical `H2C` or `X2D` in my shop yet, so this support is marked **Beta / Untested**. If you own an `H2C` or `X2D`, please try it out and let me know in **[GitHub Issues](https://github.com/everyday3d/bambu-fleet-studio/issues)** or **[Discussions](https://github.com/everyday3d/bambu-fleet-studio/discussions)** how it looks and if anything needs tweaking!
- **🎉 Now Available in the Official HACS Store**:
  - **Bambu Lab Fleet Studio** is now in the official **HACS Default Store**! Just search for **Bambu Lab Fleet Studio** inside HACS and install it in one click.

## ✨ Key Highlights

- **🔌 Works 100% Locally on Your Home Network**: Connects directly to your Bambu Lab printers over Wi-Fi or Ethernet—no Bambu Cloud or third-party Home Assistant integration required.
- **📹 Built-In Live Camera Feeds**: Watch live camera video right inside each printer card across all Bambu Lab printers (`A1`, `A1 Mini`, `P1P`, `P1S`, `P2S`, `X1C`, `X1E`, `H2C`, `H2D`, `H2S`, and `R1` Laser).
- **🖼️ Studio Artwork for Every Bambu Printer, Laser & AMS**: Built-in photos for **`A1`**, **`A1 Mini`**, **`A2L`**, **`P1S`**, **`P1P`**, **`P2S`**, **`X1C`**, **`X1E`**, **`X2D`**, **`H2C`**, **`H2D`**, **`H2D Pro`**, **`H2S`**, **`R1 Laser`**, **`AMS`**, **`AMS Lite`**, **`AMS 2 Pro`**, and **`AMS HT`**.
- **🎨 Smart AMS Display**: Automatically shows 4-slot AMS decks (with colors, material types, remaining percentage, and humidity) only on printers that actually have an AMS attached.
- **📡 1-Click Network Printer Discovery**: Scans your local network to find your Bambu printers automatically and fills in the model, IP address, and serial number for you.
- **🔍 Shop-Wide Filament Finder**: Search across every loaded spool in your shop by material (`PLA`, `PETG`, `ASA`, `TPU`) or color and jump straight to that printer card.
- **🔔 1-Click Phone Alerts, WLED Progress Bars & Smart Plug Safety**: Set up phone notifications (with camera photos and filament grams used), WLED progress light bars, smart speaker voice alerts, low-spool warnings, and safety-locked smart plugs in seconds.
- **⏱️ Print Hours & Filament Odometer + Build Plate Tracker**: Tracks total print hours and estimated filament used (`m`, `kg`, `~Spools`), plus lets you pick which build plate is installed on each printer.
- **🌐 12 Languages Built In**: English, German, French, Spanish, Italian, Dutch, Polish, Portuguese, Russian *(untested)*, Simplified Chinese *(untested)*, Traditional Chinese *(untested)*, and Japanese.

## 🚀 Quick Start YAML

Create a new dashboard view set to **Panel (1 card)** and paste:

```yaml
type: custom:bambu-fleet-studio
title: Bambu Lab Fleet Studio
subtitle: Real-Time Telemetry, Live Camera Feeds & Smart Conditional AMS
```

For bug reports and feature requests, visit the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)**.
