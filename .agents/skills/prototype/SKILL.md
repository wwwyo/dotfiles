---
name: prototype
description: Build multiple distinct variants of a UI piece, a type/API design, or a Markdown document for human comparison, with rubric-based checks and an independent assessment as input. Only runs when explicitly invoked; it does not trigger on its own.
---

# Prototyping Variants

A divergence skill. It does ONE thing: take a described artifact ("a toast", "the pricing card", "the retry policy's public type", "the intro section of this design doc"), build several genuinely different versions of it, and let the user choose a winner. **UI** goes behind a visual picker (unchanged mechanism). **Non-UI** — type/API design, module shape, markdown documents — gets one directory per variant under `.agent/prototypes/<slug>/` plus a `README.md` index. Either way, a rubric is frozen before variants exist, and an AI assessment against it runs before hand-off. Non-selected variants may lend compatible elements to the winner afterward. It does not review existing UI (that's `review-animations`), plan fixes for it (that's `improve-animations`), or choose dependencies (that's `pick-ui-library`).

## Operating Posture

You are a senior engineer running a design exploration. The entire value of this skill is **divergence**: three tints of the same idea waste the comparison — the user learns nothing by flipping between them. Each variant must be a direction you could defend shipping on its own, exploring a genuinely different answer to the same brief.

Divergence is not an excuse to drop the craft bar. For UI, every variant individually meets Emil Kowalski's standards — right easing (`ease-out` on entrances, never `ease-in`), sub-300ms UI motion, correct `transform-origin`, `transform`/`opacity` only, reduced-motion handled. A sloppy variant doesn't widen the exploration; it just loses on execution and teaches nothing about the direction it represents.

## Hard Rules

1. **The human makes the final pick; AI assessment is input, never a verdict.** Gates, measurements, and judge observations appear in the hand-off table; the skill never promotes, ranks, or scores a variant into a recommendation.
2. **Never touch production code during exploration.** Everything lives in an isolated prototype surface (see Phase 5). Integration happens only in Phase 8, only for the variant the user picked.
3. **Variants diverge on a named axis** — layout, density, personality, motion, interaction model, or (non-UI) type shape, API surface, argument for a design choice, structure of a document. Before building, you must be able to state each variant's axis in a phrase. Sharing the project's tokens or conventions is not convergence; variants *should* feel native to the codebase.
4. **Every variant meets its artifact's completion bar.** UI: real interactions, real motion, realistic content — actual product-shaped copy, plausible names and numbers, no lorem ipsum, no dead buttons. Type/API: a compilable file with at least one example call site. Document: full text of the scoped artifact (a section scope means the finished section), not an outline.
5. **The picker is chrome, not a contestant.** Its exact markup, styles, and behavior are specified in [PICKER.md](PICKER.md) — copy them verbatim. Its look is not a design decision and never adapts to the project.
6. **The rubric is frozen before variants are built (Phase 3) and never bent to fit what got built.** A criterion that turns out wrong is a note for the next round, not a same-round edit.
7. **Clean up after the choice.** When a winner is promoted, delete the prototype surface unless the user asks to keep it.

## Workflow

### Phase 1 — Scope

One thing per run. If the description spans multiple components ("the dashboard", "the whole spec"), narrow it: pick the single highest-leverage piece, say which and why, and offer the rest as follow-up runs. Restate the brief in one sentence — what the thing is, where it will live, what it must do.

### Phase 2 — Recon

Before designing anything, map the ground the variants must stand on.

UI:
- **Stack**: framework, styling system (Tailwind, CSS modules, vanilla), motion library if any.
- **Tokens**: colors, radii, spacing, fonts, easing/duration variables. Variants use these — every variant should look like it could ship in this product tomorrow.
- **Personality**: playful consumer app or crisp dashboard? This bounds how far the boldest variant may go.
- **Context**: where the piece renders — against what background, beside what neighbors, at what sizes.

Non-UI:
- **Code**: existing types, naming conventions, the callers that will consume the design.
- **Documents**: the audience, any external criteria (a reviewer's rubric, a submission's stated evaluation points, length limits), and the strongest existing example in the repo or `output/` directory to match register.

### Phase 3 — Freeze brief and rubric

Before any variant is built, fix what every variant must satisfy and how the human will compare them. This runs once; it does not move once Phase 4 starts.

- **Gates**: required conditions every variant must meet before hand-off (compiles, required sections present, within length limit, etc.). A variant that fails a gate gets fixed or dropped before it is ever presented as an option.
- **Comparison axes**: the dimensions the human will weigh variants on (distinct from each variant's own identity-axis from Phase 4).
- **Judgment criteria**: 3–6 criteria, each with a one-line anchor for scores 1, 3, and 5 — what a poor / adequate / excellent variant looks like on that criterion.
- **Fixed vs. free**: which properties variants may diverge on, and which facts, terms, or constraints every variant must share.

**Completion criterion:** gates, comparison axes, and 1/3/5 anchors are written down before Phase 4 starts, and stay unchanged through hand-off.

### Phase 4 — Choose directions

Default **3 variants**; up to 5 when the user asks or the design space is genuinely wide. More than 5 dilutes the comparison.

Before writing any code, list the set: a name and an axis for each. Names describe the direction — "Quiet", "Editorial", "Playful", "Dense" — never "Option A/B/C". If two proposed directions would differ only in accent color or copy, they are one direction; replace one with a real alternative. If you notice two directions have already converged, replace one now — this is the only point where an author may drop a direction unilaterally (past this point, see Phase 6's convergence handling).

**Completion criterion:** every variant has a name and a stated axis, and no two variants share an axis position.

### Phase 5 — Build the surface

For UI, read [references/ui.md](references/ui.md). For types, APIs, or documents, read [references/non-ui.md](references/non-ui.md). Follow the chosen surface’s build and verification recipe. Keep prototypes isolated from production; UI uses the exact [PICKER.md](PICKER.md) contract, non-UI uses per-variant directories and documents also need comparison.md.

### Phase 6 — AI assessment

Before hand-off, run every variant against the rubric frozen in Phase 3, split three ways:

a. **Gates**: run each as a script or command; every variant must pass every gate. A failing variant gets fixed or dropped — it never appears in the hand-off table.
b. **Measurements**: objective counts with no inherent good/bad (word count, public symbol count, etc.) — report the numbers, not a ranking.
c. **Judgment**: spawn ONE read-only judge subagent, preferably on a different model family from the one that wrote the variants. Give it only what the artifact needs to be judged, never the README's axis names, and use neutral labels (`v1`, `v2`, …) or bare paths so variant names or directories don't leak the direction:
   - **UI** — the running URL, one screenshot per variant, and the interaction steps to exercise.
   - **Type/API** — the source, the shared call-site/type-test file, and compiler diagnostics.
   - **Document** — the text, the frozen brief, and any external criteria.
   The judge answers each judgment criterion with a one-line observation and names any variants that appear to have converged. It never aggregates, ranks, or averages.
d. **Fallback**: if no other model family can be selected, say so in the hand-off table header (same-family judging, flagged). If no subagent can be spawned at all, skip judgment and say so — never present the author's own scoring as an independent judge.

### Phase 7 — Verify and hand off

Run the verification in the surface reference selected in Phase 5. Every variant must render or compile, meet its gates, and be reachable before handoff.

Then present the set and **stop — the choice belongs to the user**:

| # | Variant | Axis | When it's the right choice | Its cost | Gates | Extensibility | Audience fit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Quiet | Minimal motion, borders over shadows | The product is a daily-use tool | Least memorable | all passed | Easy to extend | Clear, generic hover state |
| 2 | Editorial | Large type, generous whitespace | The moment deserves weight | Eats vertical space | all passed | Layout constraints increase | Best fit, but longest |

`Gates` reads "all passed" — a gate failure never reaches this table. Judgment columns carry the judge's one-line observation per criterion, never a score or rank. Report any measurements (word count, public symbol count, …) beneath the table as plain numbers. If the judge flagged a convergence, report it with its evidence and leave both variants in the table — the user decides whether to treat them as one.

Close with where the picker is running (URL or file path), the keys to flip, or (non-UI) the `.agent/prototypes/<slug>/` path — for documents and design docs, point at `comparison.md` first and the per-variant dirs only as detail, and generate the hand-off table from `comparison.md`'s axis rows so the file stays the single source the hand-off transcribes.

**Completion criterion:** every variant is reachable and behaves correctly; no console/compile errors; the table names each variant's tradeoff honestly.

### Phase 8 — Choose, then keep

- `choose <variant>`: a provisional pick. Production stays untouched; list graft candidates (zero is a valid answer) from the non-selected variants.
- `keep <variant>`: promote that variant as-is, then clean up.
- `keep <variant>, graft <part> from <variant>`: fold the named parts in by hand — never paste them mechanically — so the result stays coherent under the winner's mental model, then promote, then clean up.
- `grafts?`: valid only after a `choose`; lists candidates for the chosen variant without promoting.

**Grafts**: candidates may be zero. Only elements compatible with the chosen variant's mental model qualify; each candidate states its benefit and its cost or conflict; grafts are never picked from judge scores. Refer to the rest as "non-selected variants" offering "compatible elements" — not "losers" or "best parts".

**Graft record**: goes in the commit message when a commit is made; otherwise state it in the final hand-off message. Never record it in the prototype README — that's deleted at cleanup.

If the user wants another round instead, keep the surface and run Phase 4 again, diverging around the direction they gravitated to. The rubric from Phase 3 stays frozen unless the user explicitly revises it.

## Invocation Variants

| Invocation | Behavior |
| --- | --- |
| `<description of a UI piece>` | Full workflow: scope → recon → freeze rubric → variants → picker → assessment → wait for choice |
| `<description of a type/API/document>` | Same, non-UI branch: one directory per variant under `.agent/prototypes/<slug>/` instead of a picker |
| `<description> x5` | Same, with that many variants (capped at 5) |
| `riff <variant>` | New round: keep the surface, generate a fresh set diverging around the named variant's direction |
| `choose <variant>` | Provisional pick; production untouched; lists graft candidates |
| `keep <variant>` | Promote that variant into the codebase as-is and clean up |
| `keep <variant>, graft <part> from <variant>` | Graft, then promote, then clean up |
| `grafts?` | List graft candidates for the chosen variant (valid only after `choose`) |
| `keep <variant>, leave the picker` | Promote, but keep the prototype surface around |

## Tone

Sell each variant honestly — one line on when it wins, one on what it costs. The judge's observations are shown, never argued for; if the user asks which you'd choose, answer from the product or the audience, not from the assessment.
