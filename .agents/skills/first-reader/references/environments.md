Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## Adapting to your environment

This skill runs in any SKILL.md-compatible coding agent, but three
capabilities vary. Check what you have BEFORE the run starts, adapt
silently, and tell the user only what changes for them, in one line.

**Subagents.** If you can spawn fresh agents (Claude Code's agent tool,
or any delegation mechanism), each reader is one. If you cannot, you
play the readers yourself, one persona at a time, and the order of
operations becomes everything: do NOT read or open the draft file for
any reason before the reads; start immediately with the feed script and
meet the piece one passage at a time in persona (file mode; served
mode is pointless when reader and reviewer share a mind). Run file mode
as `scripts/feed.py start <draft> --session <run-dir>/<reader>` — write each
reader's session into a `<run-dir>/<reader>/` subdirectory named after
its cast, matching the layout `scripts/room.py` and `scripts/ask.py` expect (a session
left directly under the run dir makes step 7 and later "ask" fail; if
that happens, move the files and say the page needed a fix, honestly).
Do the skeptic's read
in a later, separate pass from the sympathetic one; run recall by
answering the quiz from the transcript alone before ever seeing the
full text. This is a weaker experiment than fresh minds, so say so once
in the verdict ("I played both readers myself here, so treat the
findings as slightly softer") and never pretend otherwise. If the draft
is already in your context (you read it earlier in the session, it was
pasted, or your harness auto-loaded it), solo mode cannot blind you; do
the reads anyway as honest role-passes, and weight the mechanical
signals (quit logic, recall-from-log, `scripts/signals.py`) more heavily than the
needle.

**A place for the page.** With artifact publishing (Claude Code on
claude.ai), the page is a private link. Without it, it is a local HTML
file next to the run, opened for the user. The page is read, not
clicked; questions to the readers come to you in chat.

**Turn budget.** In agents where every script call is a visible tool
step, the full run is many steps. Say so up front in the starting line
("this takes a few minutes and a lot of small steps") and never ask
permission step by step; batch where your harness allows.

The first time the skill runs in a session, the starting line also
teaches the interface in passing, because nothing else will: "Reading
it as your audience would, about 5 minutes. When I'm back: where each
reader leaned in or left, what stuck with them, and a page with their
comments beside your draft. You can ask them follow-ups, and 'again'
re-reads after you revise."
