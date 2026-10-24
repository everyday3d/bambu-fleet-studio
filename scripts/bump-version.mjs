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
const DISC_29_ID = "D_kwDOVFBKKc4Ap-ZU";
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

function parseRoadmapFromReadme(rawReadmeText) {
  const readmeText = rawReadmeText.replace(/\r\n/g, "\n");
  const upcomingMatch = readmeText.match(
    /### 🚧 Upcoming Local-LAN Roadmap[^\n]*\n([\s\S]*?)(?=\n> \*\*☁️ Note|\n### ✅ Completed)/
  );
  const completedMatch = readmeText.match(
    /### ✅ Completed & Shipped Roadmap Milestones\n([\s\S]*?)(?=\n---|\n## |$)/
  );

  const upcomingRaw = upcomingMatch ? upcomingMatch[1].trim() : "";
  const completedRaw = completedMatch ? completedMatch[1].trim() : "";

  const upcomingItems = [];
  for (const line of upcomingRaw.split("\n")) {
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
    .split("\n")
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
    `## 🗳️ Help Pick What I Build Next for Bambu Lab Fleet Studio! (\`${currentTag}\`)`,
    "",
    `[![Release ${currentTag}](https://img.shields.io/badge/Release-${currentTag}%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)`,
    "",
    "Hey everyone! I'm building this dashboard for my own print room and sharing it with the community, so I'd love your help deciding what to work on next. Below is my to-do list of upcoming features, followed by everything that's **already been built and shipped (`~~...~~ ✅`)** at the bottom.",
    "",
    "### 👇 How to Vote",
    `Just scroll down to the **${upcomingItems.length} comments below** and click the **👍 (Thumbs Up)** button on the feature(s) you'd use the most in your shop! Feel free to vote for more than one or reply if you have another idea.`,
    "",
    "---",
    "",
    "### 🗺️ What's on the To-Do List",
    "",
    "| # | Feature Idea | What It Does |",
    "| :--- | :--- | :--- |",
    ...tableRows,
    "",
    "> **☁️ Quick Note on Bambu Firmware Limits**:",
    "> Because **Bambu Lab Fleet Studio** talks directly to your printers over your home network without using Bambu Cloud, a couple of things that Bambu locks to the printer's physical screen—specifically **starting an active AMS drying cycle remotely** and **editing custom non-RFID spool slots**—still have to be started on the printer itself. *(Reading live AMS humidity, temperature, and Bambu RFID spools works 100% locally!)*",
    "",
    "---",
    "",
    "### ✅ Already Built & Shipped",
    ...completedLines,
    "",
    "---",
    "*Click 👍 on the comments below to vote, or drop a reply if there's something else that would make your print room easier to run!*"
  ].join("\n");

  const disc30Title = `📊 [Roadmap Poll] What should I build next for Bambu Lab Fleet Studio (${currentTag})?`;

  runGraphQL({
    query: `mutation($id: ID!, $title: String!, $body: String!) {
      updateDiscussion(input: { discussionId: $id, title: $title, body: $body }) {
        discussion { id title url }
      }
    }`,
    variables: { id: DISC_30_ID, title: disc30Title, body: disc30Body }
  });
  console.log(`[discussions] Updated Discussion #30 title & body (${upcomingItems.length} options + ${completedLines.length} shipped milestones -> ${currentTag}).`);

  // 2. Sync Discussion #30 Voting Comments (1️⃣ .. N️⃣) + Check Discussion #29
  const existingRes = runGraphQL({
    query: `query {
      repository(owner: "everyday3d", name: "bambu-fleet-studio") {
        disc30: discussion(number: 30) {
          comments(first: 30) {
            nodes { id body }
          }
        }
        disc29: discussion(number: 29) {
          id
          viewerCanUpdate
        }
      }
    }`
  });
  const existingComments = existingRes?.data?.repository?.disc30?.comments?.nodes || [];

  for (const item of upcomingItems) {
    const marker = `Vote Option ${item.numInt}:`;
    const existing = existingComments.find((c) => c.body.includes(marker));
    const commentBody = [
      `### ${item.emojiNum} Vote Option ${item.numInt}: ${item.title}${item.extraTag}`,
      `- ${item.desc}`,
      "",
      `👉 **Click 👍 on this comment if you want me to build ${item.title} next!**`
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

  // 3. Build & Update Discussion #29 (Welcome & Roadmap Overview — Title + Body)
  const disc29Id = existingRes?.data?.repository?.disc29?.id || "D_kwDOVFBKKc4Ap-ZU";
  const disc29Title = `👋 Welcome to Bambu Lab Fleet Studio! — What It Is, What's New in ${currentTag} & What's Coming Next`;
  const disc29Body = [
    `## 👋 Hey Makers — Welcome to Bambu Lab Fleet Studio! (\`${currentTag}\`)`,
    "",
    `[![Release ${currentTag}](https://img.shields.io/badge/Release-${currentTag}%20(Official)-00e676?style=flat-square&logo=github)](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)`,
    "",
    "Thanks for checking out **Bambu Lab Fleet Studio**! This is a project I've been working on for my own shop, and I'm really excited to share it with the community.",
    "",
    "Having every Bambu Lab printer in my shop (`A1`, `A1 Mini`, `A2L`, `P1P`, `P1S`, `P2S`, `X1C`, `X1E`, `X2D`, `H2C`, `H2D`, `H2D Pro`, `H2S`, and the `R1` Laser) on a single, clean Home Assistant screen has been a total game-changer—glancing at live camera streams, checking nozzle and bed temperatures, seeing exact layer progress and finish times, and immediately spotting which filament colors and materials are loaded in each AMS without bouncing between apps is ridiculously handy.",
    "",
    "Since this is an actively growing project, **expect some bugs!** If you run into anything weird or have an idea that would make your print room easier to run, please let me know in the **[Issue Tracker](https://github.com/everyday3d/bambu-fleet-studio/issues)** and I'll get it fixed.",
    "",
    "### 🚀 Helpful Links",
    `- 📦 **[Latest Release (\`${currentTag}\`) & Install Guide](https://github.com/everyday3d/bambu-fleet-studio/releases/latest)**`,
    "- 📌 **[Release Updates & What's New (Issue #1)](https://github.com/everyday3d/bambu-fleet-studio/issues/1)**",
    "- 🗳️ **[Vote on What I Build Next (Discussion #30)](https://github.com/everyday3d/bambu-fleet-studio/discussions/30)**",
    "- 🐛 **[Report a Bug or Ask for a Feature](https://github.com/everyday3d/bambu-fleet-studio/issues/new/choose)**",
    "",
    "---",
    "",
    "### 🚧 What's on the To-Do List ([Vote in Discussion #30](https://github.com/everyday3d/bambu-fleet-studio/discussions/30))",
    ...upcomingItems.map((item) => item.rawLine),
    "",
    "### ✅ Already Built & Shipped",
    ...completedLines,
    "",
    "---",
    "Drop a comment below to say hi and let me know what printers you're running in your shop! 🖨️"
  ].join("\n");

  runGraphQL({
    query: `mutation($id: ID!, $title: String!, $body: String!) {
      updateDiscussion(input: { discussionId: $id, title: $title, body: $body }) {
        discussion { id title url }
      }
    }`,
    variables: { id: disc29Id, title: disc29Title, body: disc29Body }
  });
  console.log(`[discussions] Updated Discussion #29 title & body (-> ${currentTag}).`);
}

if (!discussionsOnly) {
  // 1. Update custom_components/bambu_fleet_studio/bambu-fleet-cards.js
  replaceInFile("custom_components/bambu_fleet_studio/bambu-fleet-cards.js", (txt) =>
    txt
      .replace(/const CARD_VERSION = "[^"]+";/, `const CARD_VERSION = "${rawVer}";`)
      .replace(/(@version\s+)[0-9]+\.[0-9]+\.[0-9]+/, `$1${rawVer}`)
  );
  console.log(`[bump] Updated custom_components/bambu_fleet_studio/bambu-fleet-cards.js`);

  // 3. Update custom_components/bambu_fleet_studio/__init__.py
  replaceInFile("custom_components/bambu_fleet_studio/__init__.py", (txt) =>
    txt.replace(/VERSION = "[^"]+"/, `VERSION = "${rawVer}"`)
  );

  // 4. Update custom_components/bambu_fleet_studio/manifest.json
  replaceInFile("custom_components/bambu_fleet_studio/manifest.json", (txt) =>
    txt.replace(/"version":\s*"[^"]+"/, `"version": "${rawVer}"`)
  );

  // 5. Update CHANGELOG.md if [Unreleased] exists or scaffold new section
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

  // Extract latest CHANGELOG section for README.md & info.md What's New block
  const clText = fs.readFileSync(path.join(ROOT_DIR, "CHANGELOG.md"), "utf8").replace(/\r\n/g, "\n");
  const clSecRegex = new RegExp(`## \\[${rawVer.replace(/\./g, "\\.")}\\][^\n]*\n([\s\S]*?)(?=\n## \\[|$)`);
  const clMatch = clText.match(clSecRegex);
  const whatsNewBody = clMatch
    ? clMatch[1].trim().replace(/^### [^\n]+\n+/gm, "")
    : "";

  // 6. Update README.md & info.md H1 version, badges, What's New section, and version pills
  replaceInFile("README.md", (txt) => {
    let out = txt
      .replace(/^# 🖨️ Bambu Lab Fleet Studio(?:\s*`\[v[0-9.]+\]`)?\s*—/m, `# 🖨️ Bambu Lab Fleet Studio \`[${tag}]\` —`)
      .replace(
        /\[!\[Release v[0-9.]+\]\(https:\/\/img\.shields\.io\/badge\/Release-v[0-9.]+%20\(Official\)-00e676\?style=flat-square&logo=github\)\]/g,
        `[![Release ${tag}](https://img.shields.io/badge/Release-${tag}%20(Official)-00e676?style=flat-square&logo=github)]`
      )
      .replace(/Integration Version Badge \(`v[0-9.]+ ✓`\)/g, `Integration Version Badge (\`${tag} ✓\`)`);
    if (whatsNewBody && /## 🆕 What's New in `v[0-9.]+`/.test(out)) {
      out = out.replace(
        /## 🆕 What's New in `v[0-9.]+`[\s\S]*?(?=\n---\r?\n\r?\n## 🌟)/,
        `## 🆕 What's New in \`${tag}\`\n\n${whatsNewBody}\n`
      );
    }
    return out;
  });

  replaceInFile("info.md", (txt) => {
    let out = txt
      .replace(/^# 🖨️ Bambu Lab Fleet Studio `v[0-9.]+`/m, `# 🖨️ Bambu Lab Fleet Studio \`${tag}\``)
      .replace(/^## 🆕 What's New in `v[0-9.]+`/m, `## 🆕 What's New in \`${tag}\``)
      .replace(
        /\[!\[Release v[0-9.]+\]\(https:\/\/img\.shields\.io\/badge\/Release-v[0-9.]+%20\(Official\)-00e676\?style=flat-square&logo=github\)\]/g,
        `[![Release ${tag}](https://img.shields.io/badge/Release-${tag}%20(Official)-00e676?style=flat-square&logo=github)]`
      );
    if (whatsNewBody && /## 🆕 What's New in `v[0-9.]+`/.test(out)) {
      out = out.replace(
        /## 🆕 What's New in `v[0-9.]+`[\s\S]*?(?=\n## ✨ Key Highlights)/,
        `## 🆕 What's New in \`${tag}\`\n\n${whatsNewBody}\n`
      );
    }
    return out;
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
    execSync(`gh release upload ${tag} "${path.join(ROOT_DIR, "custom_components/bambu_fleet_studio/bambu-fleet-cards.js")}" --repo ${REPO} --clobber`, {
      stdio: "inherit"
    });
  } catch {
    execSync(
      `gh release create ${tag} "${path.join(ROOT_DIR, "custom_components/bambu_fleet_studio/bambu-fleet-cards.js")}" --repo ${REPO} --title "${releaseTitle}" --notes-file "${notesFile}" --latest`,
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
