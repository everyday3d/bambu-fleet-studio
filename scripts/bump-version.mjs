#!/usr/bin/env node
/**
 * Bambu Lab Fleet Studio — Automated Version Bumper & Release Publisher
 *
 * Updates all versioned files in one pass:
 *   1. bambu-fleet-cards.js (CARD_VERSION)
 *   2. custom_components/bambu_fleet_studio/bambu-fleet-cards.js (synced bundle)
 *   3. custom_components/bambu_fleet_studio/__init__.py (VERSION)
 *   4. custom_components/bambu_fleet_studio/manifest.json ("version")
 *   5. README.md (Release badge & version badge references)
 *   6. info.md (H1 header & Release badge)
 *   7. CHANGELOG.md (promotes [Unreleased] or ensures [X.Y.Z] section exists)
 *
 * Usage:
 *   node scripts/bump-version.mjs <version> [--publish] [--title "..."] [--notes-file "..."]
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
const REPO = "everyday3d/bambu-fleet-studio";

const rawVer = (process.argv[2] || "").trim().replace(/^[vV]+/, "");
if (!rawVer || !/^\d+\.\d+\.\d+/.test(rawVer)) {
  console.error("Usage: node scripts/bump-version.mjs <X.Y.Z> [--publish]");
  process.exit(1);
}

const doPublish = process.argv.includes("--publish");
const tag = `v${rawVer}`;
const today = new Date().toISOString().slice(0, 10);

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
    .replace(
      /\[!\[Release v[0-9.]+\]\(https:\/\/img\.shields\.io\/badge\/Release-v[0-9.]+%20\(Official\)-00e676\?style=flat-square&logo=github\)\]/g,
      `[![Release ${tag}](https://img.shields.io/badge/Release-${tag}%20(Official)-00e676?style=flat-square&logo=github)]`
    )
    .replace(/Integration Version Badge \(`v[0-9.]+ ✓`\)/g, `Integration Version Badge (\`${tag} ✓\`)`)
);

replaceInFile("info.md", (txt) =>
  txt
    .replace(/^# 🖨️ Bambu Lab Fleet Studio `v[0-9.]+`/m, `# 🖨️ Bambu Lab Fleet Studio \`${tag}\``)
    .replace(
      /\[!\[Release v[0-9.]+\]\(https:\/\/img\.shields\.io\/badge\/Release-v[0-9.]+%20\(Official\)-00e676\?style=flat-square&logo=github\)\]/g,
      `[![Release ${tag}](https://img.shields.io/badge/Release-${tag}%20(Official)-00e676?style=flat-square&logo=github)]`
    )
);

// 6. Update CHANGELOG.md if [Unreleased] exists
replaceInFile("CHANGELOG.md", (txt) => {
  if (txt.includes(`## [${rawVer}]`)) return txt;
  if (txt.includes("## [Unreleased]")) {
    return txt.replace("## [Unreleased]", `## [${rawVer}] - ${today}`);
  }
  return txt;
});

console.log(`[bump] All version files synchronized to ${tag}.`);

if (doPublish) {
  // Extract latest section from CHANGELOG.md for release notes
  const changelog = fs.readFileSync(path.join(ROOT_DIR, "CHANGELOG.md"), "utf8");
  const secRegex = new RegExp(`## \\[${rawVer.replace(/\./g, "\\.")}\\][^\\n]*\\n([\\s\\S]*?)(?=\\n## \\[|$)`);
  const match = changelog.match(secRegex);
  const sectionBody = match ? match[1].trim() : `Release ${tag}`;

  const releaseTitle = `🖨️ Bambu Lab Fleet Studio ${tag}`;
  const releaseNotes = `## 🎉 Bambu Lab Fleet Studio \`${tag}\` — Official Release\n\n${sectionBody}\n`;
  const notesFile = path.join(os.tmpdir(), `bfs_release_notes_${tag}.md`);
  fs.writeFileSync(notesFile, releaseNotes, "utf8");

  execSync(`git -C "${ROOT_DIR}" add -A`, { stdio: "inherit" });
  try {
    execSync(`git -C "${ROOT_DIR}" commit -m "release: Bambu Lab Fleet Studio ${tag}"`, { stdio: "inherit" });
  } catch {}
  execSync(`git -C "${ROOT_DIR}" push origin main`, { stdio: "inherit" });

  try {
    execSync(`gh release view ${tag} --repo ${REPO}`, { stdio: "ignore" });
    execSync(`gh release edit ${tag} --repo ${REPO} --notes-file "${notesFile}" --latest`, { stdio: "inherit" });
    execSync(`gh release upload ${tag} "${path.join(ROOT_DIR, "bambu-fleet-cards.js")}" --repo ${REPO} --clobber`, { stdio: "inherit" });
  } catch {
    execSync(
      `gh release create ${tag} "${path.join(ROOT_DIR, "bambu-fleet-cards.js")}" --repo ${REPO} --title "${releaseTitle}" --notes-file "${notesFile}" --latest`,
      { stdio: "inherit" }
    );
  }

  // Update Pinned Release Issue #1
  const issue1Title = `🎉 [Official Release] Bambu Lab Fleet Studio ${tag} — Home Assistant Dashboard & Custom Cards`;
  const issue1Body = `# 🎉 Bambu Lab Fleet Studio \`${tag}\` — Official Release Feed\n\n[![Release ${tag}](https://img.shields.io/badge/Release-${tag}%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)\n\n${releaseNotes}`;
  const issue1File = path.join(os.tmpdir(), `bfs_issue_1_${tag}.md`);
  fs.writeFileSync(issue1File, issue1Body, "utf8");
  execSync(`gh issue edit 1 --repo ${REPO} --title "${issue1Title}" --body-file "${issue1File}"`, { stdio: "inherit" });
  execSync(`gh issue comment 1 --repo ${REPO} --body-file "${notesFile}"`, { stdio: "inherit" });
  console.log(`[bump] Published ${tag} and updated Pinned Issue #1!`);
}
