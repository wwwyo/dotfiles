#!/usr/bin/env node

const { execSync } = require("child_process");
const os = require("os");

const R = "\x1b[0m";
const DIM = "\x1b[2m";
const BOLD = "\x1b[1m";
const CYAN = "\x1b[36m";

const RINGS = ["○", "◔", "◑", "◕", "●"];

const gradient = (pct) => {
  if (pct < 50) {
    const r = Math.round(pct * 5.1);
    return `\x1b[38;2;${r};200;80m`;
  }
  const g = Math.max(0, Math.round(200 - (pct - 50) * 4));
  return `\x1b[38;2;255;${g};60m`;
};

const ring = (pct) => RINGS[Math.min(Math.floor(pct / 25), 4)];

const fmt = (label, pct) => {
  const p = Math.round(pct);
  return `${DIM}${label}${R} ${gradient(pct)}${ring(pct)} ${p}%${R}`;
};

const getGitBranch = (cwd) => {
  try {
    return execSync("git rev-parse --abbrev-ref HEAD 2>/dev/null", {
      cwd,
      encoding: "utf8",
    }).trim();
  } catch {
    return "";
  }
};

const getGitDiffStat = (cwd) => {
  try {
    const stat = execSync(
      "git diff --shortstat HEAD 2>/dev/null || git diff --shortstat 2>/dev/null",
      { cwd, encoding: "utf8" },
    ).trim();
    if (!stat) return { added: 0, removed: 0 };
    const addMatch = stat.match(/(\d+) insertion/);
    const delMatch = stat.match(/(\d+) deletion/);
    return {
      added: addMatch ? Number(addMatch[1]) : 0,
      removed: delMatch ? Number(delMatch[1]) : 0,
    };
  } catch {
    return { added: 0, removed: 0 };
  }
};

const buildStatusLine = (input) => {
  const data = JSON.parse(input);
  const home = os.homedir();
  const cwd = data.workspace?.current_dir || data.cwd || ".";
  const folder = cwd.startsWith(home) ? `~${cwd.slice(home.length)}` : cwd;
  const model = data.model?.display_name || data.model?.id || "";

  // Line 1: [folder]  model
  const line1 = `[${BOLD}${gradient(0)}${folder}${R}]  ${DIM}${model}${R}`;

  // Line 2: [branch] +added -removed
  const branch = getGitBranch(cwd);
  let line2 = "";
  if (branch) {
    const { added, removed } = getGitDiffStat(cwd);
    const diffParts = [];
    if (added > 0) diffParts.push(`${gradient(0)}+${added}${R}`);
    if (removed > 0) diffParts.push(`${gradient(100)}-${removed}${R}`);
    const diff = diffParts.length > 0 ? ` ${diffParts.join(" ")}` : "";
    line2 = `[${CYAN}${branch}${R}]${diff}`;
  }

  // Line 3: Ring Meter — ctx / 5h / 7d
  const parts = [];

  const ctxPct = data.context_window?.used_percentage;
  if (ctxPct != null) parts.push(fmt("ctx", ctxPct));

  const fiveHour = data.rate_limits?.five_hour?.used_percentage;
  if (fiveHour != null) parts.push(fmt("5h", fiveHour));

  const sevenDay = data.rate_limits?.seven_day?.used_percentage;
  if (sevenDay != null) parts.push(fmt("7d", sevenDay));

  const line3 = parts.join("  ");

  return [line1, line2, line3].filter(Boolean).join("\n");
};

const chunks = [];
process.stdin.on("data", (chunk) => chunks.push(chunk));
process.stdin.on("end", () => console.log(buildStatusLine(chunks.join(""))));