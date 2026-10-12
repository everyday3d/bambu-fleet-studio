#!/usr/bin/env node
/**
 * Bambu Lab Fleet Studio — Automated Version Bumper, Discussion Sync & Release Publisher
 *
 * Updates all versioned files AND GitHub Discussions (#29 & #30 + Vote Comments) in one pass:
 *   1. bambu-fleet-cards.js (CARD_VERSION + @version header)
 *   2. custom_components/bambu_fleet_studio/bambu-fleet-cards.js (synced bundle)
 *   3. custom_components/bambu_fleet_studio/__init__.py (VERSION / INTEGRATION_VERSION)
 *   4. custom_components/bambu_fleet_studio/manifest.json ("version")
 *   5. README.md (Release badge, version badge pills & roadmap version references)
 *   6. info.md (H1 header & Release badge)
 *   7. CHANGELOG.md (promotes [Unreleased] or scaffolds [X.Y.Z] section)
 *   8. GitHub Discussions #29 (Welcome & Roadmap) & #30 (Roadmap Poll + Vote Comments)
 *
 * Usage:
 *   node scripts/bump-version.mjs <X.Y.Z> [--publish] [--no-discussions]
 *   node scripts/bump-version.mjs --discussions
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
const DISC_29_ID = "D_kwDOVFBKKc4Ap-Zm";
const DISC_30_ID = "D_kwDOVFBKKc4Ap-Zn";

const args = process.argv.slice(2);
const discussionsOnly = args.includes("--discussions") || args.includes("--discussions-only");
const skipDiscussions = args.includes("--no-discussions");
const doPublish = args.includes("--publish");

const manifestPath = path.join(ROOT_DIR, "custom_components/bambu_fleet_studio/manifest.json");
const currentManifestVer = JSON.parse(fs.readFileSync(manifestPath, "utf8")).version;

const verArg = args.find((a) => !a.startsWith("--"));
const rawVer = discussionsOnly
  ? (verArg ? verArg.trim().replace(/^[vV]+/, "") : currentManifestVer)
  : (verArg || "").trim().replace(/^[vV]+/, "");

if (!rawVer || !/^\d+\.\d+\.\d+/.test(rawVer)) {
  console.error(
    "Usage:\n" +
      "  node scripts/bump-version.mjs <X.Y.Z> [--publish] [--no-discussions]\n" +
      "  node scripts/bump-version.mjs --discussions"
  );
  process.exit(1);
}

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

function runGraphQL(payloadObj) {
  const tmpFile = path.join(os.tmpdir(), `bfs_graphql_${Date.now()}.json`);
  fs.writeFileSync(tmpFile, JSON.stringify(payloadObj), "utf8");
  try {
    const out = execSync(`gh api graphql --input "${tmpFile}"`, { encoding: "utf8" });
    return JSON.parse(out);
  } finally {
    try {
      fs.unlinkSync(tmpFile);
    } catch {}
  }
}

function parseRoadmapFromReadme(readmeText) {
  const upcomingMatch = readmeText.match(
    /### 🚧 Upcoming Local-LAN Roadmap[^\n]*\n([\s\S]*?)(?=\n> \*\*☁️ Note|\n### ✅ Completed)/
  );
  const completedMatch = readmeText.match(
    /### ✅ Completed & Shipped Roadmap Milestones\n([\s\S]*?)(?=\n---|\n## |$)/
  );

  const upcomingRaw = upcomingMatch ? upcomingMatch[1].trim() : "";
  const completedRaw = completedMatch ? completedMatch[1].trim() : "";

  const upcomingItems = [];
  for (const line of upcomingRaw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("- [ ]")) continue;
    // Match: - [ ] **1️⃣ Title** *(optional note)*: Description
    const m = trimmed.match(/^- \[ \]\s*\*\*(\d️⃣)\s+([^*]+)\*\*(?:\s*(\*\([^)]+\)\*))?:\s*(.+)$/);
    if (m) {
      const emojiNum = m[1];
      const numInt = parseInt(emojiNum, 10) || upcomingItems.length + 1;
      const title = m[2].trim();
      const extraTag = m[3] ? ` ${m[3].trim()}` : "";
      const desc = m[4].trim();
      upcomingItems.push({ emojiNum, numInt, title, extraTag, desc, rawLine: trimmed });
    }
  }

  const completedLines = completedRaw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.startsWith("- [x]"));

  return { upcomingItems, completedLines };
}

function syncGitHubDiscussions(currentTag) {
  const readmePath = path.join(ROOT_DIR, "README.md");
  const readmeText = fs.readFileSync(readmePath, "utf8");
  const { upcomingItems, completedLines } = parseRoadmapFromReadme(readmeText);

  if (!upcomingItems.length) {
    console.warn("[discussions] Could not parse upcoming roadmap items from README.md; skipping discussion sync.");
    return;
  }

  // 1. Build Discussion #30 (Community Roadmap Poll) body
  const tableRows = upcomingItems.map(
    (item) => `| **${item.emojiNum}** | **${item.title}**${item.extraTag} | ${item.desc} |`
  );

  const disc30Body = [
    `## 🗳️ Vote on the Bambu Lab Fleet Studio Local-LAN Roadmap! (\`${currentTag}\`)`,
    "",
    `[![Release ${currentTag}](https://img.shields.io/badge/Release-${currentTag}%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)`,
    "",
    "We want to build what matters most to your workshop and print farm! Below are the upcoming **100% Local-LAN** feature modules planned for **Bambu Lab Fleet Studio**, followed by all roadmap items we've **already shipped (`~~...~~ ✅`)** at the bottom.",
    "",
    "### 👇 How to Vote on What We Build Next",
    `Scroll down to the **${upcomingItems.length} feature comments below** and click the **👍 (Thumbs Up)** reaction on the feature(s) you want us to prioritize next! You can vote for multiple options or reply with specific requests.`,
    "",
    "---",
    "",
    "### 🗺️ Candidate Local-LAN Roadmap Features",
    "",
    "| Option | Feature Module | Status & What It Does |",
    "| :--- | :--- | :--- |",
    ...tableRows,
    "",
    "> **☁️ Note on Cloud-Only / Touchscreen Firmware Restrictions**:",
    "> Because **Bambu Lab Fleet Studio** runs **100% over Local LAN (`Port 8883 TLS`)**, features restricted by Bambu Lab firmware to Bambu Cloud or physical printer touchscreen confirmation — specifically **Remote AMS Active Drying Initiation** and **Custom Non-RFID AMS Slot Writing** — are marked **Cloud / Touchscreen Only** and excluded from the Local LAN roadmap. *(Passive AMS humidity `%`, temperature `°C`, and official Bambu RFID spool telemetry remain 100% supported over Local LAN!)*",
    "",
    "---",
    "",
    "### ✅ Completed & Shipped Roadmap Milestones",
    ...completedLines,
    "",
    "---",
    "*Vote with 👍 on the comments below, or drop a new comment if you have another killer Local-LAN feature idea!*"
  ].join("\n");

  runGraphQL({
    query: `mutation($id: ID!, $body: String!) {
      updateDiscussion(input: { discussionId: $id, body: $body }) {
        discussion { id url }
      }
    }`,
    variables: { id: DISC_30_ID, body: disc30Body }
  });
  console.log(`[discussions] Updated Discussion #30 body (${upcomingItems.length} options + ${completedLines.length} shipped milestones).`);

  // 2. Sync Discussion #30 Voting Comments (1️⃣ .. N️⃣)
  const existingRes = runGraphQL({
    query: `query {
      repository(owner: "everyday3d", name: "bambu-fleet-studio") {
        discussion(number: 30) {
          comments(first: 30) {
            nodes { id body }
          }
        }
      }
    }`
  });
  const existingComments = existingRes?.data?.repository?.discussion?.comments?.nodes || [];

  for (const item of upcomingItems) {
    const marker = `Vote Option ${item.numInt}:`;
    const existing = existingComments.find((c) => c.body.includes(marker));
    const commentBody = [
      `### ${item.emojiNum} Vote Option ${item.numInt}: ${item.title}${item.extraTag}`,
      `- ${item.desc}`,
      "",
      `👉 **React with 👍 on this comment to vote for ${item.title}!**`
    ].join("\n");

    if (existing) {
      if (existing.body !== commentBody) {
        runGraphQL({
          query: `mutation($id: ID!, $body: String!) {
            updateDiscussionComment(input: { commentId: $id, body: $body }) {
              comment { id }
            }
          }`,
          variables: { id: existing.id, body: commentBody }
        });
        console.log(`[discussions] Updated Discussion #30 Vote Option ${item.numInt} comment.`);
      }
    } else {
      runGraphQL({
        query: `mutation($discussionId: ID!, $body: String!) {
          addDiscussionComment(input: { discussionId: $discussionId, body: $body }) {
            comment { id }
          }
        }`,
        variables: { discussionId: DISC_30_ID, body: commentBody }
      });
      console.log(`[discussions] Created Discussion #30 Vote Option ${item.numInt} comment.`);
    }
  }

  // 3. Build & Update Discussion #29 (Welcome & Roadmap Overview)
  const disc29Body = [
    `## 👋 Welcome to the Bambu Lab Fleet Studio Community! (\`${currentTag}\`)`,
    "",
    `[![Release ${currentTag}](https://img.shields.io/badge/Release-${currentTag}%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)`,
    "",
    "Thank you for checking out **Bambu Lab Fleet Studio** — the 100% Standalone Local-LAN, zero-YAML Command Center and Lovelace Dashboard for Bambu Lab 3D printers & lasers (**X1C, X1E, X2D, P1S, P1P, P2S, A1, A1 Mini, A2L, H2C, H2D, H2D Pro, H2S, R1 Laser**) in Home Assistant!",
    "",
    "### 🚀 Quick Links",
    `- 📦 **[Latest Release (\`${currentTag}\`) & HACS Install Guide](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)**`,
    "- 📌 **[Live Release Feed & Changelog (Issue #1)](https://github.com/everyday3d/bambu-fleet-studio/issues/1)**",
    "- 🗳️ **[Vote on the Local-LAN Feature Roadmap Poll (Discussion #30)](https://github.com/everyday3d/bambu-fleet-studio/discussions/30)**",
    "- 🐛 **[Report a Bug or Hardware Issue](https://github.com/everyday3d/bambu-fleet-studio/issues/new/choose)**",
    "",
    "---",
    "",
    "### 💬 What to Post in Discussions",
    "1. **📸 Show & Tell (Your Fleet Setups!)**: Share screenshots of your Bambu Lab Fleet Studio dashboard, WLED status strips, or multi-printer farm layouts!",
    "2. **💡 Feature Requests & Local-LAN Roadmap Ideas**: Have an idea for AMS management, Spoolman integration, AI vision inspection (`Ollama` / `Gemini` / `OpenAI` / `Claude`), WLED effects, or camera widgets? Drop it here or vote in **[Discussion #30](https://github.com/everyday3d/bambu-fleet-studio/discussions/30)**!",
    "3. **🛠️ Setup & LAN Mode Q&A**: Need help finding your printer's 8-character LAN Access Code, configuring Docker/VLAN subnets, or setting up Port `322` RTSPS / Port `6000` TLS cameras? Ask away!",
    "",
    "---",
    "",
    "### 🚧 Upcoming Local-LAN Roadmap ([Vote in Discussion #30](https://github.com/everyday3d/bambu-fleet-studio/discussions/30))",
    ...upcomingItems.map((item) => item.rawLine),
    "",
    "### ✅ Completed & Shipped Roadmap Milestones",
    ...completedLines,
    "",
    "---",
    "Drop a comment below to introduce yourself and let us know what printers are in your fleet! 🖨️🔥"
  ].join("\n");

  runGraphQL({
    query: `mutation($id: ID!, $body: String!) {
      updateDiscussion(input: { discussionId: $id, body: $body }) {
        discussion { id url }
      }
    }`,
    variables: { id: DISC_29_ID, body: disc29Body }
  });
  console.log(`[discussions] Updated Discussion #29 (Welcome & Roadmap Overview -> ${currentTag}).`);
}

if (!discussionsOnly) {
  // 1. Update bambu-fleet-cards.js
  replaceInFile("bambu-fleet-cards.js", (txt) =>
    txt
      .replace(/const CARD_VERSION = "[^"]+";/, `const CARD_VERSION = "${rawVer}";`)
      .replace(/(@version\s+)[0-9]+\.[0-9]+\.[0-9]+/, `$1${rawVer}`)
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

  // 6. Update CHANGELOG.md if [Unreleased] exists or scaffold new section
  replaceInFile("CHANGELOG.md", (txt) => {
    if (txt.includes(`## [${rawVer}]`)) return txt;
    if (txt.includes("## [Unreleased]")) {
      return txt.replace("## [Unreleased]", `## [${rawVer}] - ${today}`);
    }
    const firstHeaderIdx = txt.indexOf("\n## [");
    if (firstHeaderIdx !== -1) {
      const scaffold = `\n## [${rawVer}] - ${today}\n\n### Changed\n- Synchronized release bundle and integration manifest to \`${tag}\`.\n`;
      return txt.slice(0, firstHeaderIdx) + scaffold + txt.slice(firstHeaderIdx);
    }
    return txt;
  });

  console.log(`[bump] All 7 versioned files synchronized to ${tag}.`);
}

if (!skipDiscussions) {
  syncGitHubDiscussions(tag);
}

if (doPublish) {
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
    execSync(`gh release upload ${tag} "${path.join(ROOT_DIR, "bambu-fleet-cards.js")}" --repo ${REPO} --clobber`, {
      stdio: "inherit"
    });
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
