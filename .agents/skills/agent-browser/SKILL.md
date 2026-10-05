---
name: agent-browser
description: "Browser automation fallback when a required feature is unavailable in Orca’s built-in browser, or the user explicitly requests another browser. Use orca-cli for ordinary navigation, forms, extraction, screenshots, and web QA."
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*), Bash(mise install npm:agent-browser)
hidden: true
---

# agent-browser

Fast browser automation CLI for AI agents. Chrome/Chromium via CDP with accessibility-tree snapshots and compact `@eN` element refs.

Install the configured version (tools are managed with mise — do not `npm i -g`):

```bash
mise install npm:agent-browser
agent-browser install
```

The version is pinned in `home/dot_config/mise/config.toml` in dotfiles, with a 7day
release cooldown. To change it, edit that source and apply chezmoi from the canonical
checkout before installing. `mise use -g` changes the deployed config and would be
overwritten by the next chezmoi apply.

## When to use this skill

Default path for web work in this environment is Orca's built-in browser, driven through the
`orca` CLI (`orca tab`, `orca goto`, `orca eval`, screenshots). Load the `orca-cli` skill and use
that for navigation, form filling, page text extraction, and ordinary QA; do not treat this skill
as required for anything Orca's browser can already do.

Reach for agent-browser as a fallback when at least one of these holds:

- **A required feature is unavailable in the current Orca browser** — check the
  version-matched `orca-cli` guide first and state the missing feature. Ordinary file
  upload is supported by `orca upload --element <ref> --files <paths>`.
- **Another browser was explicitly requested** by the user or the surrounding task.

The specialized procedures below (HAR/API derivation, Electron, Slack, Vercel Sandbox,
Bedrock AgentCore) and `.agents/skills/pr/references/screenshots.md` remain available under
these conditions. Preserve their CLI steps when required; do not infer an Orca limitation
from their presence. File upload alone is not a reason to bypass Orca.

## Start here

This file is a discovery stub, not the usage guide. Before running any `agent-browser` command, load the actual workflow content from the CLI:

```bash
agent-browser skills get core             # start here — workflows, common patterns, troubleshooting
agent-browser skills get core --full      # include full command reference and templates
```

The CLI serves skill content that always matches the installed version, so instructions never go stale. The content in this stub cannot change between releases, which is why it just points at `skills get core`.

## Specialized skills

Load a specialized skill when the task falls outside browser web pages:

```bash
agent-browser skills get electron          # Electron desktop apps (VS Code, Slack, Discord, Figma, ...)
agent-browser skills get slack             # Slack workspace automation
agent-browser skills get dogfood           # Exploratory testing / QA / bug hunts
agent-browser skills get derive-client     # Record a HAR, derive a standalone API client for a site
agent-browser skills get vercel-sandbox    # agent-browser inside Vercel Sandbox microVMs
agent-browser skills get protected-vercel-deployments  # Access protected Vercel deployments
agent-browser skills get agentcore         # AWS Bedrock AgentCore cloud browsers
```

Run `agent-browser skills list` to see everything available on the installed version.

## Why agent-browser

- Fast native Rust CLI, not a Node.js wrapper
- Works with any AI agent (Cursor, Claude Code, Codex, Continue, Windsurf, etc.)
- Chrome/Chromium via CDP with no Playwright or Puppeteer dependency
- Accessibility-tree snapshots with element refs for reliable interaction
- Sessions, authentication vault, state persistence, video recording
- Specialized skills for Electron apps, Slack, exploratory testing, cloud providers

## Observability Dashboard

The dashboard runs independently of browser sessions on port 4848 and can also be opened through a proxied or forwarded URL such as `https://dashboard.agent-browser.localhost`. Agents should stay on the dashboard origin: session tabs, status, and stream traffic are proxied internally, so session ports do not need to be exposed.
