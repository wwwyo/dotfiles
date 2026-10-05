---
name: langfuse-cli
description: Langfuse CLI usage reference — install, resource/action discovery, credentials, and common usage tips for `langfuse-cli`. Use for further tips on using the Langfuse CLI.
---

# Langfuse CLI Reference

Documentation: https://langfuse.com/docs/api-and-data-platform/features/cli

## Setup

Use the `npm:@langfuse/cli` tool managed by mise; its executable is `langfuse`. Check the current tool configuration before running it.

Canonical dotfiles pins `npm:@langfuse/cli` in `home/dot_config/mise/config.toml`; read its exact version there. Install that configured version with `mise install npm:@langfuse/cli` before the first CLI call. The package is the maintained name recommended by the [official CLI docs](https://langfuse.com/docs/api-and-data-platform/features/cli); the executable remains `langfuse`.

Apply the config from the canonical checkout before installation. If the configured pin is not yet deployed, validate it with `mise exec npm:@langfuse/cli@<configured-version> -- langfuse --help`, substituting the exact version read from the config. Preserve exact pins and the seven-day release cooldown. Do not use npm global, npx, or bunx to bypass them.

All examples run through `mise exec` so tools and encrypted environment variables are resolved together.

## Discovery

```bash
# List all resources and auth info
mise exec -- langfuse api __schema

# List actions for a resource
mise exec -- langfuse api <resource> --help

# Show args/options for a specific action
mise exec -- langfuse api <resource> <action> --help

# Preview the curl command without executing
mise exec -- langfuse api <resource> <action> --curl
```

## Credentials

Credentials are `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL`. Manage them through [secret-env](../../secret-env/SKILL.md) using mise+age, and verify presence without printing values. Use the configured base URL; do not substitute an example cloud region.

## Tips

- Use `--json` for machine-readable JSON output
- Use `--curl` to preview the HTTP request without executing
- All list commands support filtering — check `<resource> <action> --help` for available options
- Prefer `observations` over `legacy-observations-v1s` — `observations` is the modern high-performance endpoint (cursor pagination, selective field groups); `legacy-observations-v1s` is the deprecated v1
- Prefer `metrics` over `legacy-metrics-v1s` for the same reason
- Prefer `scores` over `legacy-score-v1s` for list/get operations
- Always query via `observations`, not `traces`, even when the user phrases the request in terms of traces — the `traces` endpoints are outdated (add `--trace-id` to scope to a known trace). See the [Observations API docs](https://langfuse.com/docs/api-and-data-platform/features/observations-api) for the v1 → v2 mapping.
- Pagination: legacy v1 endpoints use `--limit` and `--page`; modern endpoints (`observations`, `metrics`, `scores`) use cursor-based pagination — pass `--limit`, then thread `meta.cursor` from the response into the next request's `--cursor`
