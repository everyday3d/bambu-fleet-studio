#!/usr/bin/env node
/**
 * Bambu Lab Fleet Studio — Automated Version Bumper & Release Publisher
 * Usage:
 *   node scripts/bump-version.mjs <version> [--publish]
 * Example:
 *   node scripts/bump-version.mjs 1.3.1 --publish
 */

import fs from "fs";
import path from "path";
import os from "os";
import { execSync } from "child_process";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, "..");

const rawVer = (process.argv[2] || "1.3.1").trim().replace(/^[vV]+/, "");
const doPublish = process.argv.includes("--publish");
const tag = `v${rawVer}`;

function replaceInFile(relPath, replacer) {
  const fullPath = path.join(ROOT_DIR, relPath);
  if (!fs.existsSync(fullPath)) return;
  const before = fs.readFileSync(fullPath, "utf8");
  const after = replacer(before);
  if (after !== before) {
    fs.writeFileSync(fullPath, after, "utf8");
    console.log(`[bump] Updated ${relPath} -> ${tag}`);
  }
}

// 1. Update bambu-fleet-cards.js
replaceInFile("bambu-fleet-cards.js", (txt) =>
  txt.replace(/const CARD_VERSION = "[^"]+";/, `const CARD_VERSION = "${rawVer}";`)
);

// 2. Sync custom_components/bambu_fleet_studio/bambu-fleet-cards.js
fs.copyFileSync(
  path.join(ROOT_DIR, "bambu-fleet-cards.js"),
  path.join(ROOT_DIR, "custom_components/bambu_fleet_studio/bambu-fleet-cards.js")
);
console.log(`[bump] Synced custom_components/bambu_fleet_studio/bambu-fleet-cards.js`);

// 3. Update custom_components/bambu_fleet_studio/__init__.py
replaceInFile("custom_components/bambu_fleet_studio/__init__.py", (txt) =>
  txt.replace(/VERSION = "[^"]+"/, `VERSION = "${rawVer}"`)
);

// 4. Update custom_components/bambu_fleet_studio/manifest.json
replaceInFile("custom_components/bambu_fleet_studio/manifest.json", (txt) =>
  txt.replace(/"version":\s*"[^"]+"/, `"version": "${rawVer}"`)
);

// 5. Update README.md & info.md badges and version pills
replaceInFile("README.md", (txt) =>
  txt
    .replace(/\[!\[Release v[0-9.]+\]\(https:\/\/img\.shields\.io\/badge\/Release-v[0-9.]+%20\(Official\)-00e676\?style=flat-square&logo=github\)\]/g,
      `[![Release ${tag}](https://img.shields.io/badge/Release-${tag}%20(Official)-00e676?style=flat-square&logo=github)]`)
    .replace(/Integration Version Badge \(`v[0-9.]+ ✓`\)/g, `Integration Version Badge (\`${tag} ✓\`)`)
);

replaceInFile("info.md", (txt) =>
  txt
    .replace(/^# 🖨️ Bambu Lab Fleet Studio `v[0-9.]+`/m, `# 🖨️ Bambu Lab Fleet Studio \`${tag}\``)
    .replace(/\[!\[Release v[0-9.]+\]\(https:\/\/img\.shields\.io\/badge\/Release-v[0-9.]+%20\(Official\)-00e676\?style=flat-square&logo=github\)\]/g,
      `[![Release ${tag}](https://img.shields.io/badge/Release-${tag}%20(Official)-00e676?style=flat-square&logo=github)]`)
);

console.log(`[bump] All version files synchronized to ${tag}.`);
