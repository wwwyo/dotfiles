# UI prototype surface

Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## Build

- **In a project with a dev server (UI)** — prefer a standalone, self-contained HTML harness the user opens directly; an in-project route under file-based routing can ship inside the production build even when unlinked, so only use one when you've verified it's excluded from the build. One file per variant plus a small harness file; nothing imports from the prototype surface into production code.
- **No project / static context (UI)** — a single self-contained HTML file (inline CSS/JS) the user can open directly in a browser. Choose a restrained default look: neutral grays, one accent, system font stack.

For UI, the picker's markup, styles, keyboard wiring, and placement come from [PICKER.md](../PICKER.md), verbatim — load it now and build exactly that. Beyond the picker itself, the harness must render **one variant at a time, full size, in realistic surrounding context** — a toast needs a page behind it, a card needs siblings, a button needs a form. Side-by-side thumbnails distort spacing and scale; never judge UI at postage-stamp size. The picker transition is **instant**, with no animated crossfade or slide between variants. Remount the selected variant as specified in PICKER.md so its own entrance animations replay for comparison.

## Verify

For UI: run the harness. Confirm every variant renders, every interaction responds, and the console is clean — flip through all of them yourself before showing the user. If browser tooling is available, screenshot each variant.
