---
name: orca-cli
description: "Operate Orca worktrees, terminals, repos, automations, artifacts, skill sharing, and the embedded browser through the Orca CLI. Use for Orca-managed state and full ownership handoffs; supervised worker coordination uses orchestration."
---

# Orca CLI

This discovery stub loads the version-matched guide from the Orca executable used for this session.

## Resolve the CLI for this session

Choose the executable once and reuse it for every later command:

- If the `ORCA_CLI_COMMAND` environment variable is set, use its value. Orca exports this
  for managed WSL sessions.
- Otherwise, in a dev checkout whose session exposes `ORCA_DEV_REPO_ROOT`, use `orca-dev`.
- Otherwise, on Linux outside an Orca-managed terminal, use `orca-ide`. Never run bare
  `orca` there — outside Orca's terminals it normally resolves to the
  GNOME Orca screen reader (`/usr/bin/orca`) and starts speech on the user's machine.
- Otherwise, use `orca`.

Below, `ORCA` is a placeholder for the executable you resolved. Substitute it before
running anything; do not create a shell variable or run `ORCA` literally. This works the
same way in POSIX shells, PowerShell, and cmd.exe.

If the selected executable cannot run, report its exact error and stop. Do not fall through
to another executable, which could silently target a different Orca build.

## Load the version-matched guide before running Orca commands

```text
ORCA skills get orca-cli
```

Prefer `--json`. Use the selected executable's `--help` for commands or flags the guide does
not cover. If a command reports that Orca is not running, start it with `ORCA open --json`
and retry. If it fails with `runtime_access_denied`, your sandbox blocked the connection:
re-run it with escalated permissions, and do not run `ORCA open` or restart Orca. If
`skills get` is unknown, explain that updating Orca restores the guide; use `--help` for
read-only discovery and do not guess unsupported commands.

## Preserve the user's focus during browser automation

Keep the user's terminal or other app focused by default:

- Omit `--focus` from `ORCA tab switch` unless the user asks to reveal or switch
  to the browser pane.
- After creating a tab, get its `browserPageId` from the result or
  `ORCA tab list --json` and target later commands with `--page <browserPageId>`.
  Avoid unnecessary tab switches.

These choices reduce focus changes; they do not guarantee background input.
Browser clicks and mouse actions can still steal focus even with `--page`.
Do not invent a `--no-focus` flag or claim focus is preserved without observing it.
For version-specific bugs and fix availability, read
[the Orca focus notes](../dev-env/references/orca.md#embedded-browser-がユーザーのフォーカスを奪うとき).
