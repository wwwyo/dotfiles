# Type/API and document prototype surfaces

Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## Build

- **Non-UI artifact** — one directory per variant: `.agent/prototypes/<slug>/<variant>/`, each holding the artifact, an `example.*` call site (types) or the full text (documents), and a shared check command. This repo already keeps design material gitignored under `.agent/`. `.agent/prototypes/<slug>/README.md` holds: the frozen brief and rubric, a link to each variant, what each variant deliberately changed, the check commands and their output, and open questions. For types, add each variant's public surface list and migration cost; for documents, add word count and section outline. No standalone project to build against (type/API): confirm language, toolchain and target versions, module system, and assumed caller before writing anything. No standalone project (document): confirm audience, purpose, length, and publication medium.
  - **Documents and design docs additionally need a single comparison file** — `.agent/prototypes/<slug>/comparison.md`. Per-variant full text is for depth, not for comparison: the human must not have to cross-read three files to see the differences. Give every variant the same heading set, and put the variants side by side in one file — a compact diagram per variant (flow, layout, or diff-like blocks) plus a single table with one row per comparison axis (what differs, when it wins, what it costs). Ordering, depth, and emphasis stay free per variant, so "structure of a document" remains available as a divergence axis. The comparison file is the reading surface; the per-variant files are the detail behind it.

## Verify

For type/API: confirm every variant compiles and typechecks via the shared check command. For documents: confirm the text renders as Markdown, links resolve, required sections are present, it's within the length limit, and it has no placeholders or TODOs; check that shared facts and names stay consistent across variants. For documents and design docs, also confirm `comparison.md` exists, renders as Markdown, covers every variant under the shared heading set with a compact diagram each, and has one comparison-table row per axis. "Reads complete" is a judgment criterion, not a check.
