---
name: hallmark
description: "Design, audit, or redesign web pages and UI components; study visual references from URLs or screenshots. Use for new UI, visual redesign, or UI design review. General code audits and technical research alone do not trigger it."
version: 1.1.0
---

# Hallmark

Design web pages and UI components with structural variety, honest content, and a coherent visual system. Preserve existing routes, component ownership, copy intent, brand, and information architecture unless the user authorizes a broader change.

## Choose the workflow

Read only the selected workflow before acting. All workflows also follow the shared disciplines below.

| Task | Read |
| --- | --- |
| New page or application UI | [references/design-flow.md](references/design-flow.md) |
| A button, card, nav, form, or other scoped component | [references/component-flow.md](references/component-flow.md) |
| `hallmark audit <target>` — findings only; do not edit | [references/verbs/audit.md](references/verbs/audit.md) |
| `hallmark redesign <target> [--mood <name>]` — preserve implementation boundaries | [references/verbs/redesign.md](references/verbs/redesign.md) |
| `hallmark study <screenshot or URL>` — diagnosis, then a user-selected next step | [references/study-workflow.md](references/study-workflow.md) |

For other in-scope requests that do not name a verb, use design-flow for a page or application, and component-flow for a scoped component.

For a URL or screenshot supplied without a clear request, ask whether to study it or use it as a reference for a fresh build. General code audits and technical research are outside this skill.

## Existing-project boundaries

- State the files to modify/create/delete before editing. Delete production files or rebuild the project only when explicitly authorized; a redesign request alone does not authorize that expansion.
- Default to in-place edits or additive components wired through existing routes. If removing multiple components is necessary, present the file-level plan for confirmation.
- Treat documents and briefs as reference material; copy their wording verbatim only when asked.

## Catalog data

[assets/tokens.css](assets/tokens.css) is the bundled token source from the revision in `.upstream-rev`; its license is [LICENSE](LICENSE). Read the shared base `:root` block, then only the selected theme's block and applicable shared overrides, using `rg` and a bounded file read. Do not load the entire catalog for one theme. Use a project's locked `design.md` first when present.

## Disciplines that hold across every verb

These seven disciplines are **not** verb-specific. They apply to default Design, `audit`, `redesign`, `study`, and component-scope alike. They sit alongside the slop test, not inside one branch of it.

1. **Pre-emit self-critique.** Before handing back any output, score it 1–5 on six axes — Philosophy, Hierarchy, Execution, Specificity, Restraint, Variety. Anything **< 3** triggers a revision pass. Stamp the six scores at the top of the artifact (`/* Hallmark · pre-emit critique: P5 H4 E5 S4 R5 V5 */`). See [`references/slop-test.md`](references/slop-test.md) § Pre-emit self-critique.

2. **Honest copy — no fabricated content.** If the user did not supply a metric, do not invent one. Stat-led layouts, comparison rows, and proof bars must use real numbers, a placeholder (`—` plus a labelled grey block, "metric to confirm"), or a different macrostructure. *"+47 % conversion"*, *"trusted by 50,000+ teams"*, and *"10× faster"* are slop the moment they're invented. Same rule for testimonials, logos, and case-study counts. See [`references/anti-patterns.md` § Invented metrics](references/anti-patterns.md) and slop-test gate **46**.

3. **Locked tokens — no mid-render improvisation.** Once a theme is selected at Step 2.6, every colour and every `font-family` declaration in the artifact must reference a named token (`var(--color-accent)`, `font-family: var(--font-display)`). Inline OKLCH / hex / `rgb()` values, or a `font-family: "Some Font"` declaration that bypasses the token block, are not allowed. If a value is needed that doesn't exist as a token, lift it into the token block as a new named variable, then reference it. See [`references/anti-patterns.md` § Mid-render token improvisation](references/anti-patterns.md) and slop-test gate **48**.

4. **Re-drawn chrome forbidden.** Hallmark must not hand-build fake browser bars (URL pill + traffic-light dots), fake phone frames, fake code-block windows (mock title bar + dots wrapping a `<pre>`), or fake IDE chrome — the user's environment already supplies real chrome. Use real screenshots wrapped in a `<figure>` (with at most a hairline border), or omit the chrome and let the content stand on its own. See [`references/anti-patterns.md` § Re-drawn UI chrome](references/anti-patterns.md) and slop-test gate **47**.

5. **Mobile responsiveness — every emit verified at 320 / 375 / 414 / 768 px.** Hallmark's output must render flawlessly at all four widths. The non-negotiables: no horizontal scroll + root `overflow-x: clip` on both `html` and `body`, never `hidden` (gate 34); no two-line clickable text — buttons, primary nav links, footer links, breadcrumbs, CTAs (gate 49); image-bearing grid tracks use `minmax(0, 1fr)`, never bare `1fr` (gate 50); display headers wrap inside long words via `overflow-wrap: anywhere; min-width: 0` (gate 51); section heads collapse to one column on mobile across every theme variant (gate 52); radio-tab patterns don't scroll-jump (gate 53). See [`references/responsive.md` § Mobile — non-negotiable](references/responsive.md). This is a hard floor, not a wish list.

6. **Typography purity — no italic headers.** Headings and display type are always roman (`font-style: normal`). An italicised emphasis word inside an otherwise-upright heading (`Built to <em>think</em>`) is one of the most reliable AI tells; so is an all-italic display face on headings. Carry emphasis with weight, accent colour, or a drawn underline. Italic survives only as *body-copy* emphasis inside running paragraphs. See [`references/anti-patterns.md` § Italic headers](references/anti-patterns.md) and slop-test gate **38a**.

7. **Suspect Hallmark's own attractor.** Anti-slop design has its own defaults, and this skill sits inside them: warm-cream paper + terracotta accent + high-contrast (often italic) serif; near-black + a single acid accent; broadsheet hairline rules. If the output lands on one of these three and the brief never named it, that is fall-through, not craft — re-derive the palette and type from the subject's own materials. Where the brief *does* name one, follow the brief exactly. See [`references/anti-patterns.md` § The anti-slop cluster](references/anti-patterns.md).

---


If any applicable gate fails, fix it before handoff.

## Handoff

Read [references/contract.md](references/contract.md) at handoff for output and scope requirements. Each workflow specifies when to load its visual rules and post-build checks.
