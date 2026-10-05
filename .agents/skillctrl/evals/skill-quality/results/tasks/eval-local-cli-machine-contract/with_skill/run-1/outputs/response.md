Implementation complete. Summary of the work:

## Files changed (fixture only)

**`fixture/cli.py`** — rewritten (stdlib only, no network/server/MCP/auth):

| Area | What was added |
|---|---|
| Machine output | `--output {text,json,ndjson}` accepted **before or after** the subcommand, plus `NOTES_OUTPUT_FORMAT`. Default is `ndjson` when stdout isn't a TTY, `text` on a TTY, so legacy `list` / `rename` output (`n1: Alpha`, `Renamed!`) is preserved for humans while agents get parseable output for free. |
| Error contract | All failures go to **stderr** as `{"ok":false,"error":{code,message,field?,hint?}}`; success carries `ok:true`. Distinct exit codes: `2` usage, `3` validation, `4` note not found, `5` data error. argparse errors go through the same envelope. |
| Self-describing schema | `schema [all\|list\|rename]` and `--help --json` return flags, defaults, output shapes, data contract, error codes and exit codes as JSON — the runtime source of truth instead of prose in the prompt. |
| rename payload | `--json '{"id":"n1","patch":{"title":"New"}}'` (plus `--json -` for stdin). The legacy `--id/--title` path is kept; mixing the two is an error (`conflicting_input`). |
| Input hardening | id must match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` (rejects `/ \ ? # % ..`); control chars (C0/DEL) rejected in id and title; title trimmed, non-empty, ≤200 chars; `patch` may only contain `title` (`id`/`body`/`tags` → `immutable_field`); any extra top-level key → `unknown_field`, so an input value can never become a file path — `data_path()` is always `./notes.json`. |
| Unknown note | `note_not_found`, exit 4, nothing written and nothing auto-created. |
| Pre-change confirmation | `--dry-run` validates and returns `before`/`after`/`changed`/`written:false` without touching the file. Opt-in hard guardrail `NOTES_REQUIRE_CONFIRM=1` makes writes require `--yes`. Non-interactive by contract. |
| Context savings | `--fields` mask, `--limit`/`--offset` paging, `--sanitize` (masks injection-marker strings as defence in depth). |
| Durability | Atomic temp-file + `os.replace`; store validated on load (array shape, required keys, duplicate ids). |

**`fixture/CLI.md`** — usage examples for every surface: output formats, error envelope + exit-code table, schema discovery, field masks, dry-run/confirm workflow, the input-hardening table with concrete rejection examples, both rename input paths, and a short "recommended agent rules" list.

`fixture/notes.json` and `fixture/requirements.md` were left untouched.

Caveat: no shell is available in this fixture, so I could not execute `cli.py` to verify the outputs above — the examples in `CLI.md` are derived from the code paths, not from a captured run.