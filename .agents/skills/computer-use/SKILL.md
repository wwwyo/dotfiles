---
name: computer-use
description: "Control visible native-app or external-browser windows when a CLI, filesystem, or API cannot reach the needed GUI. Use the bundled computer-use plugin by default; the Orca computer route requires an explicit request. Orca’s embedded browser uses orca-cli."
---

# Computer Use

GUI control for a window that no shell, filesystem, git, HTTP or existing CLI can reach. Do not
use it for Orca's embedded browser — that is `orca-cli`'s job.

## Which GUI path to use

1. **Bundled computer-use plugin (default here).** `~/.codex/config.toml` enables
   `computer-use@openai-bundled` and `unified-computer-use@openai-bundled`. In a Codex session,
   drive the GUI with the tools that plugin exposes, reading the plugin's own instructions and
   tool list from the running session for what is available. Never guess a command or tool name
   that you have not seen there — if the session does not expose the plugin, say so instead of
   substituting a different API.
2. **Orca CLI route (explicit request).** Use the `orca computer` procedure below only when the user
   explicitly asks for the Orca path. Plugin unavailability alone does not authorize switching
   the GUI path. Do not run it for ordinary GUI work just because it is
   documented here.

## Orca CLI route (explicit request only)

This discovery stub loads the version-matched guide from the Orca executable used for this session.

### Resolve the CLI for this session

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

### Load the version-matched guide before running Orca commands

```text
ORCA skills get computer-use
```

Prefer `--json`. Use the selected executable's `--help` for commands or flags the guide does
not cover. If a command reports that Orca is not running, start it with `ORCA open --json`
and retry. If it fails with `runtime_access_denied`, your sandbox blocked the connection:
re-run it with escalated permissions, and do not run `ORCA open` or restart Orca. If
`skills get` is unknown, explain that updating Orca restores the guide; use `--help` for
read-only discovery and do not guess unsupported commands.
