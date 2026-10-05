#!/usr/bin/env python3
"""notes - a local note store CLI that is safe to drive from an AI agent.

Human surface:  ./cli.py list
                 ./cli.py rename --id n1 --title "New"
Agent surface:  ./cli.py --output json list --fields id,title
                 ./cli.py rename --json '{"id":"n1","patch":{"title":"New"}}' --dry-run
                 ./cli.py schema rename

Only the Python standard library is used. There is no network, no server, no
MCP, and no authentication: the only data source is ./notes.json in the current
working directory.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

PROG = "cli.py"

# ---------------------------------------------------------------- exit codes --

EXIT_OK = 0
EXIT_USAGE = 2  # argparse/flag errors, unknown command
EXIT_INVALID = 3  # input validation (bad payload, bad id, bad title)
EXIT_NOT_FOUND = 4  # the note id does not exist (never auto-created)
EXIT_DATA = 5  # notes.json missing / unreadable / malformed

EXIT_CODES = {
    EXIT_OK: "success",
    EXIT_USAGE: "usage error (unknown flag, missing argument, bad --output value)",
    EXIT_INVALID: "input validation error (payload/id/title rejected, unknown field)",
    EXIT_NOT_FOUND: "note not found (no write is performed, nothing is created)",
    EXIT_DATA: "local data error (notes.json missing, unreadable, or malformed)",
}

# ------------------------------------------------------------ data contract --

DATA_FILENAME = "notes.json"
NOTE_FIELDS = ("id", "title", "body", "tags")
IMMUTABLE_FIELDS = ("id", "body", "tags")
PATCHABLE_FIELDS = ("title",)
MAX_TITLE_LENGTH = 200
MAX_ID_LENGTH = 64

# An id is a path segment-ish token. The pattern rejects '/', '\\', '.', '..',
# '?', '#', '%', control characters and surrounding whitespace, so an id can
# never escape into a path, a query string, or a URL.
ID_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,%d}\Z" % (MAX_ID_LENGTH - 1))

# Heuristic prompt-injection markers used by --sanitize. Documented as best
# effort: it is a defence in depth, not a guarantee.
INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)", re.I),
    re.compile(r"disregard\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)", re.I),
    re.compile(r"you\s+are\s+now\b", re.I),
    re.compile(r"system\s*prompt", re.I),
    re.compile(r"</?\s*(?:system|assistant|user|tool)\s*>", re.I),
    re.compile(r"(?:reveal|print|show)\s+(?:your\s+)?(?:prompt|instructions)", re.I),
)
SANITIZED_MARKER = "[redacted:suspicious-instruction]"


# ------------------------------------------------------------------ errors ---


class CliError(Exception):
    """An error that is reported as a machine-readable envelope on stderr."""

    def __init__(self, code, message, exit_code=EXIT_INVALID, field=None, hint=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.field = field
        self.hint = hint

    def to_envelope(self):
        error = {"code": self.code, "message": self.message}
        if self.field:
            error["field"] = self.field
        if self.hint:
            error["hint"] = self.hint
        return {"ok": False, "error": error}


# --------------------------------------------------------- input validation ---


def check_control_chars(value, field):
    for ch in value:
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            raise CliError(
                "control_character",
                "%s contains a control character (U+%04X); "
                "control characters are not accepted." % (field, ord(ch)),
                field=field,
                hint="Strip ANSI escapes, NUL bytes and newlines before calling the CLI.",
            )
    return value


def validate_id(raw):
    if not isinstance(raw, str):
        raise CliError("invalid_type", "id must be a string.", field="id")
    check_control_chars(raw, "id")
    if not raw:
        raise CliError("empty_id", "id must not be empty.", field="id")
    if not ID_RE.match(raw):
        raise CliError(
            "invalid_id",
            "id %r is not a valid note id." % raw,
            field="id",
            hint="Use 1-%d chars from [A-Za-z0-9._-] starting with a letter or digit; "
            "'/', '\\', '?', '#', '%' and '..' are rejected." % MAX_ID_LENGTH,
        )
    return raw


def validate_title(raw):
    if not isinstance(raw, str):
        raise CliError("invalid_type", "title must be a string.", field="patch.title")
    check_control_chars(raw, "patch.title")
    title = raw.strip()
    if not title:
        raise CliError("empty_title", "title must be a non-empty string.", field="patch.title")
    if len(title) > MAX_TITLE_LENGTH:
        raise CliError(
            "title_too_long",
            "title is %d characters; the limit is %d." % (len(title), MAX_TITLE_LENGTH),
            field="patch.title",
        )
    return title


def parse_rename_payload(raw):
    """Validate the {"id": ..., "patch": {...}} payload. Unknown keys are errors."""
    if not isinstance(raw, dict):
        raise CliError(
            "invalid_payload",
            "--json payload must be a JSON object, got %s." % type(raw).__name__,
            field="payload",
        )
    unknown = sorted(set(raw) - {"id", "patch"})
    if unknown:
        raise CliError(
            "unknown_field",
            "unknown key(s) in --json payload: %s." % ", ".join(unknown),
            field=unknown[0],
            hint="Only 'id' and 'patch' are accepted; input values are never "
            "interpreted as file paths or other side channels.",
        )
    if "id" not in raw:
        raise CliError("missing_field", "--json payload requires 'id'.", field="id")
    if "patch" not in raw:
        raise CliError("missing_field", "--json payload requires 'patch'.", field="patch")

    patch = raw["patch"]
    if not isinstance(patch, dict):
        raise CliError(
            "invalid_type", "patch must be a JSON object.", field="patch"
        )
    unknown_patch = sorted(set(patch) - set(PATCHABLE_FIELDS))
    if unknown_patch:
        first = unknown_patch[0]
        immutable = first in IMMUTABLE_FIELDS
        raise CliError(
            "immutable_field" if immutable else "unknown_field",
            "patch.%s is not renameable." % first,
            field="patch.%s" % first,
            hint=("rename may only change 'title'." if immutable else
                  "rename may only change %s." % ", ".join(PATCHABLE_FIELDS)),
        )
    if "title" not in patch:
        raise CliError(
            "missing_field",
            "patch must contain 'title'.",
            field="patch.title",
        )

    return validate_id(raw["id"]), validate_title(patch["title"])


def read_payload_text(text):
    if text == "-":
        text = sys.stdin.read()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CliError(
            "invalid_json",
            "--json payload is not valid JSON: %s" % exc,
            field="payload",
            hint='Example: --json \'{"id":"n1","patch":{"title":"New"}}\'',
        ) from None


# ------------------------------------------------------------ local storage ---


def data_path():
    """The only data source: ./notes.json. Inputs never influence this path."""
    return Path.cwd() / DATA_FILENAME


def load_notes():
    path = data_path()
    if not path.is_file():
        raise CliError(
            "data_not_found",
            "%s not found in the current directory." % DATA_FILENAME,
            exit_code=EXIT_DATA,
            hint="Run the CLI from the directory that holds %s." % DATA_FILENAME,
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError(
            "data_unreadable", "cannot read %s: %s" % (DATA_FILENAME, exc), exit_code=EXIT_DATA
        ) from None
    try:
        notes = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(
            "data_invalid", "%s is not valid JSON: %s" % (DATA_FILENAME, exc), exit_code=EXIT_DATA
        ) from None
    if not isinstance(notes, list):
        raise CliError(
            "data_invalid", "%s must contain a JSON array of notes." % DATA_FILENAME,
            exit_code=EXIT_DATA,
        )

    seen = set()
    for index, note in enumerate(notes):
        if not isinstance(note, dict) or "id" not in note or "title" not in note:
            raise CliError(
                "data_invalid",
                "%s entry %d must be an object with at least 'id' and 'title'."
                % (DATA_FILENAME, index),
                exit_code=EXIT_DATA,
            )
        if note["id"] in seen:
            raise CliError(
                "data_invalid", "duplicate note id %r in %s." % (note["id"], DATA_FILENAME),
                exit_code=EXIT_DATA,
            )
        seen.add(note["id"])
    return notes


def write_notes(notes):
    """Atomic replace so a crash cannot truncate the store."""
    path = data_path()
    payload = json.dumps(notes, ensure_ascii=False, indent=2) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".notes-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp, path)
    except OSError as exc:
        Path(tmp).unlink(missing_ok=True)
        raise CliError("write_failed", "cannot write %s: %s" % (DATA_FILENAME, exc),
                       exit_code=EXIT_DATA) from None


def find_note(notes, note_id):
    for note in notes:
        if note.get("id") == note_id:
            return note
    raise CliError(
        "note_not_found",
        "no note with id %r." % note_id,
        exit_code=EXIT_NOT_FOUND,
        field="id",
        hint="List existing ids first; the CLI never creates notes implicitly.",
    )


# ------------------------------------------------------------------ output ---


def project(note, fields, sanitize):
    out = {}
    for field in fields:
        value = note.get(field)
        if sanitize and isinstance(value, str) and looks_suspicious(value):
            value = SANITIZED_MARKER
        out[field] = value
    return out


def looks_suspicious(text):
    return any(pattern.search(text) for pattern in INJECTION_PATTERNS)


def emit(payload, fmt, ndjson_records=None):
    """Write one command result to stdout in the requested machine format."""
    if fmt == "text":
        return
    if fmt == "ndjson" and ndjson_records is not None:
        for record in ndjson_records:
            sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
        return
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")


def emit_error(err, fmt):
    envelope = err.to_envelope()
    if fmt in ("json", "ndjson"):
        sys.stderr.write(json.dumps(envelope, ensure_ascii=False) + "\n")
    else:
        sys.stderr.write("error[%s]: %s%s\n" % (
            err.code, err.message, (" (%s)" % err.hint) if err.hint else ""))


def resolve_format(args):
    explicit = getattr(args, "output", None) or os.environ.get("NOTES_OUTPUT_FORMAT")
    if explicit:
        if explicit not in ("text", "json", "ndjson"):
            raise CliError(
                "invalid_output_format",
                "unknown output format %r; use text, json or ndjson." % explicit,
                exit_code=EXIT_USAGE,
                field="--output",
            )
        return explicit
    # Agent default: structured output whenever stdout is not a terminal.
    return "text" if sys.stdout.isatty() else "ndjson"


def emit_text_lines(notes, fields, sanitize, stream=None):
    stream = stream or sys.stdout
    for note in notes:
        row = project(note, fields, sanitize)
        stream.write("%s: %s\n" % (row.get("id", ""), row.get("title", "")))


# ----------------------------------------------------------------- commands --


def cmd_list(args, fmt):
    notes = load_notes()
    fields = args.fields.split(",") if args.fields else list(NOTE_FIELDS)
    fields = [f.strip() for f in fields]
    bad = [f for f in fields if f not in NOTE_FIELDS]
    if bad:
        raise CliError(
            "unknown_field",
            "unknown field(s) in --fields: %s." % ", ".join(bad),
            field="--fields",
            hint="Available fields: %s." % ", ".join(NOTE_FIELDS),
        )
    offset = args.offset
    window = notes[offset:offset + args.limit] if args.limit is not None else notes[offset:]
    records = [project(note, fields, args.sanitize) for note in window]

    payload = {
        "ok": True,
        "command": "list",
        "count": len(records),
        "total": len(notes),
        "offset": offset,
        "fields": fields,
        "notes": records,
    }
    if fmt == "text":
        emit_text_lines(window, fields, args.sanitize)
    else:
        emit(payload, fmt, ndjson_records=records)
    return EXIT_OK


def resolve_rename_input(args):
    if args.payload is not None and (args.id is not None or args.title is not None):
        raise CliError(
            "conflicting_input",
            "--json and --id/--title are mutually exclusive; pick one.",
            field="--json",
            hint="Prefer --json for agent use; it maps 1:1 to the data contract.",
        )
    if args.payload is not None:
        return parse_rename_payload(read_payload_text(args.payload))
    if args.id is None or args.title is None:
        raise CliError(
            "missing_field",
            "rename requires either --json or both --id and --title.",
            field="--id/--title",
        )
    return validate_id(args.id), validate_title(args.title)


def cmd_rename(args, fmt):
    note_id, new_title = resolve_rename_input(args)
    notes = load_notes()
    note = find_note(notes, note_id)
    before_title = note["title"]
    changed = before_title != new_title

    payload = {
        "ok": True,
        "command": "rename",
        "dry_run": bool(args.dry_run),
        "written": False,
        "changed": changed,
        "id": note_id,
        "before": {"id": note_id, "title": before_title},
        "after": {"id": note_id, "title": new_title},
    }

    if args.dry_run:
        payload["data_file"] = str(data_path())
        if fmt == "text":
            sys.stdout.write("Would rename %s: %s -> %s (dry run, no changes written)\n"
                             % (note_id, before_title, new_title))
        else:
            emit(payload, fmt, ndjson_records=[payload])
        return EXIT_OK

    require_confirmation(args)
    if changed:
        note["title"] = new_title  # body, tags and id are never touched
        write_notes(notes)
    payload["written"] = changed
    payload["data_file"] = str(data_path())

    if fmt == "text":
        sys.stdout.write("Renamed!\n")
    else:
        emit(payload, fmt, ndjson_records=[payload])
    return EXIT_OK


def require_confirmation(args):
    """Opt-in guardrail: NOTES_REQUIRE_CONFIRM=1 demands an explicit --yes."""
    require = os.environ.get("NOTES_REQUIRE_CONFIRM", "").lower() in ("1", "true", "yes")
    if require and not getattr(args, "yes", False):
        raise CliError(
            "confirmation_required",
            "NOTES_REQUIRE_CONFIRM is set: re-run with --yes to write.",
            field="--yes",
            hint="Use --dry-run first to inspect the planned change.",
        )


# ------------------------------------------------------------------ schema ---


def schema_document():
    return {
        "ok": True,
        "kind": "schema",
        "version": 1,
        "prog": PROG,
        "description": "Local note store CLI (stdlib only, no network/auth/server).",
        "data_contract": {
            "data_file": DATA_FILENAME,
            "location": "current working directory only",
            "note_fields": {
                "id": "immutable string, [%A-Za-z0-9._-], 1-%d chars" % MAX_ID_LENGTH,
                "title": "non-empty string, max %d chars" % MAX_TITLE_LENGTH,
                "body": "opaque string, not modified by rename",
                "tags": "array of strings, not modified by rename",
            },
            "rename_payload": {"id": "<note id>", "patch": {"title": "<new title>"}},
            "rename_patchable_fields": list(PATCHABLE_FIELDS),
            "rename_immutable_fields": list(IMMUTABLE_FIELDS),
            "unknown_keys": "rejected with error code unknown_field",
            "missing_note": "error note_not_found (exit %d); notes are never auto-created" % EXIT_NOT_FOUND,
        },
        "commands": {
            "list": {
                "summary": "List notes from ./notes.json",
                "positionals": [],
                "flags": {
                    "--fields": {"value": "comma separated field subset",
                                 "default": ",".join(NOTE_FIELDS)},
                    "--limit": {"type": "integer", "default": "all"},
                    "--offset": {"type": "integer", "default": 0},
                    "--sanitize": {"type": "flag",
                                   "summary": "mask strings matching injection heuristics"},
                },
                "output": {"text": "'<id>: <title>' per line",
                           "json": "{ok, command, count, total, offset, fields, notes}",
                           "ndjson": "one note object per line"},
                "exit_codes": [EXIT_OK, EXIT_DATA, EXIT_INVALID, EXIT_USAGE],
            },
            "rename": {
                "summary": "Change exactly one note's title",
                "positionals": [],
                "flags": {
                    "--json": {"value": "rename payload JSON, or '-' to read stdin",
                               "schema": {"id": "string", "patch": {"title": "string"}}},
                    "--id": {"value": "note id (human path, pairs with --title)"},
                    "--title": {"value": "new title (human path, pairs with --id)"},
                    "--dry-run": {"type": "flag",
                                  "summary": "validate and show the plan, never write"},
                    "--yes": {"type": "flag",
                              "summary": "required only when NOTES_REQUIRE_CONFIRM=1"},
                },
                "output": {"text": "'Renamed!'",
                           "json": "{ok, command, dry_run, written, changed, id, before, after, data_file}",
                           "ndjson": "same object on a single line"},
                "exit_codes": [EXIT_OK, EXIT_NOT_FOUND, EXIT_INVALID, EXIT_DATA, EXIT_USAGE],
            },
            "schema": {
                "summary": "Machine-readable description of this CLI",
                "positionals": [{"name": "command",
                                 "choices": ["all", "list", "rename"], "default": "all"}],
                "flags": {},
                "output": {"text": "human summary", "json": "this document", "ndjson": "one line"},
                "exit_codes": [EXIT_OK, EXIT_USAGE],
            },
        },
        "global_flags": {
            "--output": {"choices": ["text", "json", "ndjson"],
                         "default": "text on a TTY, ndjson otherwise",
                         "env": "NOTES_OUTPUT_FORMAT"},
            "-h/--help": {"json": "combine with --json for a machine-readable help envelope"},
        },
        "environment": {
            "NOTES_OUTPUT_FORMAT": "text | json | ndjson (overrides the default)",
            "NOTES_REQUIRE_CONFIRM": "1/true/yes makes rename require --yes",
        },
        "errors": {
            "envelope": "{ok: false, error: {code, message, field?, hint?}} on stderr",
            "codes": {
                "invalid_json": "the --json payload is not parseable JSON",
                "invalid_payload": "payload is not a JSON object",
                "missing_field": "required id/patch/title absent",
                "unknown_field": "key outside the contract (includes id/body/tags in patch)",
                "immutable_field": "patch tried to change an immutable field",
                "invalid_id": "id fails the charset/control-character rules",
                "empty_title": "title is empty or whitespace only",
                "control_character": "input contains C0/DEL control characters",
                "title_too_long": "title exceeds %d characters" % MAX_TITLE_LENGTH,
                "conflicting_input": "--json mixed with --id/--title",
                "confirmation_required": "NOTES_REQUIRE_CONFIRM=1 and --yes absent",
                "note_not_found": "unknown id; nothing is written or created",
                "data_not_found": "notes.json is missing",
                "data_invalid": "notes.json is not a valid note array",
            },
        },
        "exit_codes": {str(code): text for code, text in EXIT_CODES.items()},
    }


def cmd_schema(args, fmt):
    doc = schema_document()
    target = args.command or "all"
    if target != "all":
        doc = dict(doc, kind="schema", command=target, commands={target: doc["commands"][target]})
    if fmt == "text":
        if target == "all":
            sys.stdout.write("%s - %s\n" % (PROG, doc["description"]))
            for name, spec in doc["commands"].items():
                sys.stdout.write("  %-8s %s\n" % (name, spec["summary"]))
            sys.stdout.write("  --output text|json|ndjson (default: ndjson when not a TTY)\n")
        else:
            sys.stdout.write(json.dumps(doc["commands"][target], ensure_ascii=False, indent=2) + "\n")
    else:
        emit(doc, fmt, ndjson_records=[doc])
    return EXIT_OK


# --------------------------------------------------------------- arg parsing --


_ARGV = []


class CliParser(argparse.ArgumentParser):
    """argparse that reports usage errors in the same machine-readable envelope."""

    def error(self, message):  # noqa: D102
        err = CliError("usage", message, exit_code=EXIT_USAGE, hint="Run `%s schema all`." % PROG)
        emit_error(err, resolve_output_hint(_ARGV))
        raise SystemExit(EXIT_USAGE)


def common_flags():
    """Flags accepted both before and after the subcommand."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--output", choices=["text", "json", "ndjson"], default=argparse.SUPPRESS,
                        help="output format (default: ndjson when stdout is not a TTY)")
    parent.add_argument("--sanitize", action="store_true", default=argparse.SUPPRESS,
                        help="mask strings that match prompt-injection heuristics")
    return parent


def resolve_output_hint(argv):
    for token in argv:
        if token in ("--output", "--json"):
            nxt = argv[argv.index(token) + 1:argv.index(token) + 2]
            if token == "--output" and nxt and nxt[0] in ("text", "json", "ndjson"):
                return nxt[0]
            if token == "--json":
                return "json"
    return "text"


def wants_json_help(argv):
    return any(t in ("-h", "--help", "help") for t in argv) and "--json" in argv


def print_json_help(argv):
    doc = schema_document()
    command = next((t for t in argv if t in doc["commands"]), "all")
    payload = {
        "ok": True,
        "kind": "help",
        "prog": PROG,
        "usage": "%s [--output {text,json,ndjson}] <command> [flags]" % PROG,
        "command": command,
        "commands": {
            name: {"summary": spec["summary"], "flags": spec["flags"],
                   "positionals": spec["positionals"], "exit_codes": spec["exit_codes"]}
            for name, spec in doc["commands"].items()
        },
        "global_flags": doc["global_flags"],
        "environment": doc["environment"],
        "errors": doc["errors"],
        "exit_codes": doc["exit_codes"],
        "data_contract": doc["data_contract"],
        "see_also": ["%s schema all" % PROG, "CLI.md"],
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(EXIT_OK)


def build_parser():
    parser = CliParser(prog=PROG, description="Local note store CLI.",
                       epilog="Machine contract: `%s schema all`, examples in CLI.md." % PROG)
    common = common_flags()
    parser.add_argument("--output", choices=["text", "json", "ndjson"], default=argparse.SUPPRESS)
    parser.add_argument("--sanitize", action="store_true", default=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="subcommand")

    list_p = sub.add_parser("list", parents=[common], help="List notes")
    list_p.add_argument("--fields", help="comma separated subset of %s" % ",".join(NOTE_FIELDS))
    list_p.add_argument("--limit", type=int, help="maximum number of notes to return")
    list_p.add_argument("--offset", type=int, default=0, help="skip this many notes first")

    rename_p = sub.add_parser("rename", parents=[common], help="Change one note's title")
    rename_p.add_argument("--json", dest="payload",
                          help="rename payload as JSON, or '-' to read it from stdin")
    rename_p.add_argument("--id", help="note id (human path; pairs with --title)")
    rename_p.add_argument("--title", help="new title (human path; pairs with --id)")
    rename_p.add_argument("--dry-run", action="store_true",
                          help="validate and show the planned change without writing")
    rename_p.add_argument("--yes", action="store_true",
                          help="confirm the write when NOTES_REQUIRE_CONFIRM is set")

    schema_p = sub.add_parser("schema", parents=[common],
                              help="Print the machine-readable CLI contract")
    schema_p.add_argument("command", nargs="?", choices=["all", "list", "rename"], default="all")
    return parser


HANDLERS = {"list": cmd_list, "rename": cmd_rename, "schema": cmd_schema}


def main(argv=None):
    global _ARGV
    argv = list(sys.argv[1:] if argv is None else argv)
    _ARGV = argv
    if wants_json_help(argv):
        print_json_help(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    # Flags declared with default=SUPPRESS are absent unless the user passed them.
    args.output = getattr(args, "output", None)
    args.sanitize = getattr(args, "sanitize", False)
    if not getattr(args, "subcommand", None):
        parser.error("a command is required (list, rename, schema)")

    fmt = "text"
    try:
        fmt = resolve_format(args)
        if getattr(args, "offset", 0) < 0:
            raise CliError("invalid_value", "--offset must be >= 0.", field="--offset")
        if getattr(args, "limit", None) is not None and args.limit < 0:
            raise CliError("invalid_value", "--limit must be >= 0.", field="--limit")
        return HANDLERS[args.subcommand](args, fmt)
    except CliError as err:
        emit_error(err, fmt)
        return err.exit_code


if __name__ == "__main__":
    sys.exit(main())