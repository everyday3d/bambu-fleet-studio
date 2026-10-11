# 🖨️ Bambu Lab Fleet Studio

> **👋 Hello makers!** This is a project I've been working on for some time, and I think I'm ready to release it. Expect some bugs—please use the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)** and I will get it fixed! I hope you enjoy it as much as I do.

**Part of the BoxerDawg 3D Ecosystem** — A professional, card-based Home Assistant Lovelace dashboard and custom card suite for **Bambu Lab** 3D printers (`A1`, `A1 Mini`, `P1P`, `P1S`, `X1C`, `X1E`).

![Bambu Lab Fleet Studio Overview](https://raw.githubusercontent.com/everyday3d/bambu-fleet-studio/main/docs/screenshots/01_fleet_studio_overview.png)

## ✨ Key Highlights

- **🖼️ Model-Accurate Printer Photography**: Embedded studio renders for **Bambu A1**, **Bambu P1S / X1C**, and **Bambu A1 Mini**.
- **🎨 Smart Conditional AMS Deck**: Automatically inspects Home Assistant devices and `tray_1..tray_4` entities so **only printers physically equipped with an AMS render the 4-slot AMS deck**. Non-AMS printers display a sleek **Direct External Spool** badge.
- **📹 Live Camera Stream + Lightbox**: Side-by-side printer model visual and live camera stream with 1-click full-screen modal.
- **➕ Built-In Add / Edit / Delete Printer Manager**: Add new printers (LAN Mode or Bambu Cloud), reload integration entries, or remove printers directly from the dashboard.
- **📖 4-Card Visual Setup Walkthrough**: Scannable 4-step onboarding cards—no walls of text.

## 🚀 Quick Start YAML

Add a new panel view to your dashboard and paste:

```yaml
type: custom:bambu-fleet-studio
title: Bambu Lab Fleet Studio
subtitle: Real-Time Telemetry, Live Camera Feeds & Smart Conditional AMS
```

For bug reports and feature requests, visit the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)**.
