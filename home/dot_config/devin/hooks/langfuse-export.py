#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["langfuse==4.15.4", "requests==2.34.2"]
# ///
"""langfuse-export — Devin の session transcript を Langfuse trace として送る。

Usage:
    uv run --script langfuse-export.py devin SESSION_ID  # Devin session を全件 export
    --dry-run                                            # emit せず正規化した turn 数だけ表示

実行は `uv run --script` 前提。PEP723 metadata から langfuse SDK が resolve
される（exact pin は supply chain 方針。upstream の plugin hook と同じ方式）。
turn 組立・Langfuse emit・SDK 内部 API への依存は同じ dir の vendored
langfuse_hook.py を import して使う（同じロジックを複写しないため。
upstream 追従の単位も 1 箇所に保つ）。

Devin には project file 経由の opt-in 経路がないため、env の
DEVIN_TRACE_TO_LANGFUSE のみを見る（repo-local mise.local.toml に書くのが opt-in
手段）。codex plugin の gate 変数 TRACE_TO_LANGFUSE と別名にしている —
dotfiles 等の opt-in repo の env を引き継いだ codex が別 repo で plugin を
有効化しないようにするため。pi は公式 @langfuse/pi-observability-plugin に
任せ、この exporter では扱わない。
"""

import base64
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# LANGFUSE_HOOK_DIR は test/worktree 用の override。本番では同じ dir の
# vendored script を参照する。
sys.path.insert(0, os.environ.get(
    "LANGFUSE_HOOK_DIR", str(Path(__file__).resolve().parent)))
try:
    import langfuse_hook as lh
except SystemExit:
    raise
except Exception:
    sys.exit(0)

STATE_DIR = Path.home() / ".local" / "state" / "langfuse-export"
STATE_FILE = STATE_DIR / "state.json"
LOCK_FILE = STATE_DIR / "state.lock"
MIGRATIONS_FILE = STATE_DIR / "migrations.json"
DEVIN_DB = Path.home() / ".local" / "share" / "devin" / "cli" / "sessions.db"


class LegacyMigrationRequired(RuntimeError):
    """Legacy coverage does not identify delivered source nodes or cloud IDs."""


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError("invalid checkpoint")
    return state


def save_state(state: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE_FILE)


# ----------------- transcript → Claude-format rows -----------------
# langfuse_hook の build_turns/emit_turn が読む形:
# {"type": "user"|"assistant", "message": {"role","id","model","content":[parts]},
#  "timestamp": ISO8601}
# parts: {"type":"text"} / {"type":"tool_use","id","name","input"} /
#        {"type":"tool_result","tool_use_id","content"}


def _text_part(text: Any) -> Optional[Dict[str, Any]]:
    return {"type": "text", "text": text} if isinstance(text, str) and text else None


def _tool_result_row(tool_use_id: Any, content: Any, ts: Optional[str],
                     is_error: bool = False) -> Dict[str, Any]:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": content,
                 **({"is_error": True} if is_error else {})}
            ],
        },
        "timestamp": ts,
    }


def devin_messages(session_id: str, *, earliest: bool = False, legacy: bool = False) -> Optional[Tuple[List[Dict[str, Any]], Path]]:
    """sessions.db の message_nodes を Claude 形式に正規化する。
    戻り値は (rows, working_directory)。hidden session や DB 不備では None。

    - readonly URI (mode=ro): 動作中の Devin が DB を WAL で掴んでいる。
      コピー方式は -wal/-shm の取りこぼしと checkpoint 中のちぎれがある。
      readonly なら writer を止めずトランザクション境界は sqlite が守る
    - hidden=1 は Devin 内部の session（title 生成・commit message 生成等）
      で export する価値がない
    - message_id で dedup: context 再作成ごとに Devin は過去の発話を同じ
      message_id で丸ごと再保存するので、素の全件は同じ発言が重複する
      （main_chain_id から parent を辿ると chain 再作成で root が NULL の
      新枝になり session 前半が欠けるため最初の row_id 順に並べる）。
      本文は最新 payload、tool_calls は版をまたいだ ID の和集合を使う。
      初回 export 前に新版から消えた呼び出しも落とさない
    """
    if not DEVIN_DB.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{DEVIN_DB}?mode=ro", uri=True)
    except Exception:
        return None
    try:
        row = con.execute(
            "select working_directory, hidden, model from sessions where id = ? limit 1",
            (session_id,),
        ).fetchone()
        if not row or row[1] == 1:
            return None
        cwd = Path(row[0] or "")
        model = row[2] or "devin"
        identity = ("coalesce(json_extract(chat_message, '$.message_id'), cast(row_id as text))"
                    if legacy else "coalesce(nullif(json_extract(case when json_valid(chat_message) "
                    "then chat_message else '{}' end, '$.message_id'), ''), 'row:' || row_id)")
        rows = con.execute(
            "with nodes as ("
            f" select row_id, chat_message, {identity} as identity"
            " from message_nodes where session_id = ?"
            "), revisions as ("
            " select row_id, chat_message, min(row_id) over (partition by identity) as first_row"
            " from nodes"
            ") select first_row, chat_message from revisions order by first_row, row_id",
            (session_id,),
        ).fetchall()
    except Exception:
        return None
    finally:
        con.close()

    # A newer context copy can omit previously recorded calls. Keep their IDs,
    # while allowing the newest payload for an existing call to update it.
    messages: Dict[int, Dict[str, Any]] = {}
    calls_by_node: Dict[int, Dict[str, Dict[str, Any]]] = {}
    for first_row, raw in rows:
        try:
            m = json.loads(raw)
        except Exception:
            continue
        if not isinstance(m, dict) or (earliest and first_row in messages):
            continue
        source_id = str(m.get("message_id") or f"row:{first_row}")
        if m.get("role") == "assistant" and not legacy:
            calls = calls_by_node.setdefault(first_row, {})
            missing_ids: Dict[str, int] = {}
            for tc in m.get("tool_calls") or []:
                tool_id = tc.get("id")
                if not tool_id:
                    digest = _digest(tc)
                    occurrence = missing_ids.get(digest, 0)
                    missing_ids[digest] = occurrence + 1
                    tool_id = f"missing:{source_id}:{digest}:{occurrence}"
                calls[str(tool_id)] = {**tc, "id": tool_id}
            m["tool_calls"] = list(calls.values())
        messages[first_row] = m

    out: List[Dict[str, Any]] = []
    for first_row, m in messages.items():
        source_id = str(m.get("message_id") or f"row:{first_row}")
        md = m.get("metadata") or {}
        ts = md.get("created_at")
        role = m.get("role")
        if role == "user":
            part = _text_part(m.get("content"))
            if part:
                out.append({
                    "type": "user",
                    "message": {"role": "user", "id": source_id, "content": [part]},
                    "timestamp": ts,
                })
        elif role == "assistant":
            parts: List[Dict[str, Any]] = []
            text = _text_part(m.get("content"))
            if text:
                parts.append(text)
            for tc in m.get("tool_calls") or []:
                parts.append({
                    "type": "tool_use",
                    "id": tc.get("id"),
                    "name": tc.get("name"),
                    "input": tc.get("arguments"),
                })
            if parts:
                # get_usage() が期待する Anthropic 形式に写す。無いと
                # generation に token usage / cost が乗らない
                metrics = md.get("metrics") or {}
                usage = {
                    "input_tokens": metrics.get("input_tokens"),
                    "output_tokens": metrics.get("output_tokens"),
                    "cache_read_input_tokens": metrics.get("cache_read_tokens"),
                    "cache_creation_input_tokens": metrics.get("cache_creation_tokens"),
                }
                usage = {k: v for k, v in usage.items() if isinstance(v, int)}
                out.append({
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "id": source_id,
                        "model": md.get("generation_model") or model,
                        "usage": usage,
                        "content": parts,
                    },
                    "timestamp": ts,
                })
        elif role == "tool":
            timing = (md.get("extensions") or {}).get("chisel/tool_call_timing") or {}
            out.append(_tool_result_row(
                m.get("tool_call_id"), m.get("content"),
                timing.get("finished_at") or ts,
                is_error=m.get("is_error") is True or md.get("is_error") is True,
            ))
    return out, cwd


# ----------------- emit -----------------

def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()).hexdigest()


def _git(cwd: Path, *args: str) -> Optional[str]:
    try:
        # rev-parse 系は local FS に対して ms オーダーなので、10s 待つ価値がある
        # のは既に何かが壊れている時だけ → 短く切る
        r = subprocess.run(["git", "-C", str(cwd), *args],
                           capture_output=True, text=True, timeout=3)
        return r.stdout.strip() or None if r.returncode == 0 else None
    except Exception:
        return None


def repo_metadata(cwd: Path) -> Dict[str, str]:
    """emit 時点で repo 識別を確定する。読み手側の path 推測は dir の実在を
    要求するが orca worktree は短命なので間に合わない — dir が生きている
    送信側で解決して metadata に焼く。`--git-common-dir` 経由なら linked
    worktree でも canonical repo root（共有 .git の親）が取れる。"""
    # Path("") は "." になる — working_directory が空の session を
    # 現在 dir の repo に誤帰属させない
    if str(cwd) in ("", "."):
        return {}
    md: Dict[str, str] = {"cwd": str(cwd)}
    common = _git(cwd, "rev-parse", "--path-format=absolute",
                  "--git-common-dir")
    # bare repo（自身が git dir）や submodule（<top>/.git/modules/<sub>）
    # では親が repo root にならないので basename が ".git" の形だけ採る
    if common and os.path.basename(common) == ".git":
        root = str(Path(common).resolve().parent)
        md["repo_root"] = root
        md["repo_name"] = os.path.basename(root)
    branch = _git(cwd, "branch", "--show-current")
    if branch:
        md["git_branch"] = branch
    return md


def turn_key(turn: Any, session_id: str, source: str) -> str:
    return _digest(lh.observation_seed(source, session_id, "turn", lh.get_message_id(turn.user_msg)))


def turn_fingerprints(turns: List[Any], session_id: str, source: str,
                      source_path: Path, extra: Optional[Dict[str, str]]) -> Dict[str, str]:
    return {turn_key(turn, session_id, source): _digest({
        "user": turn.user_msg, "assistants": turn.assistant_msgs,
        "tool_results": turn.tool_results_by_id, "turn_number": number,
        "source_path": str(source_path), "metadata": extra,
    }) for number, turn in enumerate(turns, 1)}


def emit_turns(lf: Any, msgs: List[Dict[str, Any]], session_id: str,
               source: str, label: str, ss: Dict[str, Any], source_path: Path,
               extra: Optional[Dict[str, str]] = None) -> int:
    """Stage fingerprints; the caller commits them only after successful delivery.

    Ordinals and timestamps can move when Devin rebuilds context. Source message
    IDs define identity; the full normalized payload defines whether it changed.
    Legacy checkpoints lack delivery proof and cloud/source identity mappings.
    Do not silently replay history or mark an unknown snapshot as delivered.
    Only fresh or verified state enters this lane; unresolved sessions use the
    legacy lane, preserving its existing exporter behavior.
    """
    if ss and ss.get("version") != 2:
        raise LegacyMigrationRequired("legacy checkpoint needs explicit migration")
    if not ss:
        ss.update(version=2, turns={})
    fingerprints = ss.setdefault("turns", {})
    emitted = 0
    turns = lh.build_turns(msgs)
    current = turn_fingerprints(turns, session_id, source, source_path, extra)
    for turn_num, turn in enumerate(turns, 1):
        key = turn_key(turn, session_id, source)
        fingerprint = current[key]
        if fingerprints.get(key) == fingerprint:
            continue
        try:
            lh.emit_turn(lf, session_id, turn_num, turn, source_path,
                         source=source, label=label, extra_metadata=extra,
                         deterministic_ids=True,
                         detail=os.environ.get("DEVIN_LANGFUSE_DETAIL", "turn"))
        except Exception as e:
            # Partial deliveries are retried under the same IDs on the next hook.
            lh.info(f"emit_turn failed: {type(e).__name__}")
            continue
        fingerprints[key] = fingerprint
        emitted += 1
    ss["updated"] = datetime.now(timezone.utc).isoformat()
    return emitted


def verified_migration(session_id: str, checkpoint: Dict[str, Any], public_key: str,
                       host: str) -> Optional[Dict[str, Any]]:
    try:
        manifest = json.loads(MIGRATIONS_FILE.read_text(encoding="utf-8"))
        entry = manifest["sessions"][session_id]
        if (manifest.get("schema_version") != 1 or manifest.get("base_url") != host.rstrip("/") or
                manifest.get("auth_fingerprint") != hashlib.sha256(public_key.encode()).hexdigest() or
                entry.get("legacy_fingerprint") != _digest(checkpoint)):
            return None
        identities = entry["identities"]
        if not identities or not isinstance(entry["turns"], dict):
            return None
        if any(not re.fullmatch(r"[0-9a-f]{64}", seed) or
               not re.fullmatch(r"[0-9a-f]{16}", ids["span_id"]) or
               not re.fullmatch(r"[0-9a-f]{32}", ids["trace_id"])
               for seed, ids in identities.items()):
            return None
        return {"version": 2, "turns": dict(entry["turns"]),
                "identities": identities, "migrated_project": entry["project_id"]}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def emit_legacy_turns(lf: Any, msgs: List[Dict[str, Any]], session_id: str,
                      checkpoint: Dict[str, Any], source_path: Path,
                      extra: Dict[str, str]) -> int:
    """Retain the old exporter lane until a complete cloud mapping is verified.

    This keeps its existing signature/attempt checkpoint semantics, including its
    known random-ID resume duplication. It does not claim successful delivery.
    """
    state = lh.load_session_state({"legacy": checkpoint}, "legacy")
    turns = lh.build_turns(msgs)
    emitted = 0
    for i, turn in enumerate(turns):
        signature = f"{len(turn.assistant_msgs)}:{lh.get_message_id(turn.assistant_msgs[-1])}:{len(turn.tool_results_by_id)}"
        if i < state.turn_count or (i == state.turn_count and state.buffer == signature):
            continue
        emitted += 1
        try:
            lh.emit_turn(lf, session_id, i + 1, turn, source_path, source="devin",
                         label="Devin", extra_metadata=extra,
                         detail=os.environ.get("DEVIN_LANGFUSE_DETAIL", "turn"))
        except Exception as error:
            lh.info(f"legacy emit failed: {type(error).__name__}")
    if turns:
        state.turn_count = len(turns) - 1
        last = turns[-1]
        state.buffer = f"{len(last.assistant_msgs)}:{lh.get_message_id(last.assistant_msgs[-1])}:{len(last.tool_results_by_id)}"
    wrapper: Dict[str, Any] = {}
    lh.write_session_state(wrapper, "legacy", state)
    checkpoint.clear()
    checkpoint.update(wrapper["legacy"])
    return emitted


def create_client(public_key: str, secret_key: str, host: str) -> Tuple[Any, Any, Any]:
    """Use SDK/OTel extension points so export failure cannot advance checkpoints."""
    from langfuse import Langfuse
    from requests import Session
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceResponse
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    class CheckedSession(Session):
        rejected = False

        def request(self, *args, **kwargs):
            response = super().request(*args, **kwargs)
            # The stock OTel exporter reports success for any HTTP 2xx, including
            # OTLP partial rejection. Such batches must not advance our checkpoint.
            if response.ok and response.content:
                # Langfuse returns a JSON queue acknowledgement, including for
                # protobuf requests. Standard OTLP collectors use protobuf replies.
                if "application/json" in response.headers.get("Content-Type", ""):
                    reply = response.json()
                    if not isinstance(reply, dict) or reply.get("error"):
                        raise RuntimeError("invalid ingestion acknowledgement")
                    partial = reply.get("partialSuccess", reply.get("partial_success", {}))
                    rejected = int(partial.get("rejectedSpans", partial.get("rejected_spans", 0)))
                else:
                    rejected = ExportTraceServiceResponse.FromString(
                        response.content).partial_success.rejected_spans
                if rejected:
                    self.rejected = True
                    raise RuntimeError("OTLP partial rejection")
            return response

    class CheckedExporter(SpanExporter):
        def __init__(self, delegate: SpanExporter):
            self.delegate = delegate
            self.failed = False

        def export(self, spans):
            try:
                result = self.delegate.export(spans)
            except Exception:
                self.failed = True
                raise
            if result != SpanExportResult.SUCCESS or checked_session.rejected:
                self.failed = True
            return result

        def shutdown(self):
            self.delegate.shutdown()

    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    path = os.environ.get("LANGFUSE_OTEL_TRACES_EXPORT_PATH", "api/public/otel/v1/traces")
    checked_session = CheckedSession()
    delivery = CheckedExporter(OTLPSpanExporter(
        endpoint=f"{host.rstrip('/')}/{path}", timeout=None, session=checked_session,
        headers={"Authorization": "Basic " + auth,
                 "x-langfuse-sdk-name": "python",
                 "x-langfuse-sdk-version": version("langfuse"),
                 "x-langfuse-public-key": public_key,
                 "x-langfuse-ingestion-version": "4"},
    ))
    # Let the SDK retain its configured environment, release and sampling rules.
    lf = Langfuse(public_key=public_key, secret_key=secret_key, host=host,
                  id_generator=lh.SourceIdGenerator(), span_exporter=delivery)
    provider = lh.otel_trace_api.get_tracer_provider()
    if not isinstance(getattr(provider, "id_generator", None), lh.SourceIdGenerator):
        lf.shutdown()
        raise RuntimeError("source ID generator not configured")
    return lf, provider, delivery


def main() -> int:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    if not args:
        return 0

    # opt-in gate は state を触る前に判定する。
    if not dry_run:
        if os.environ.get("DEVIN_TRACE_TO_LANGFUSE", "") != "true":
            return 0
        public_key = os.environ.get("CC_LANGFUSE_PUBLIC_KEY") or os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("CC_LANGFUSE_SECRET_KEY") or os.environ.get("LANGFUSE_SECRET_KEY")
        host = (os.environ.get("CC_LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_BASE_URL")
                or "https://cloud.langfuse.com")
        if not public_key or not secret_key:
            return 0

    source = args[0]
    if source != "devin" or len(args) < 2:
        return 0

    session_id = args[1]
    state_key = f"devin::{session_id}"
    label = "Devin"

    if dry_run:
        res = devin_messages(session_id)
        if res is None:
            return 0
        msgs, source_path = res
        if not msgs:
            return 0
        turns = lh.build_turns(msgs)
        print(f"source={source} session={session_id} turns={len(turns)} "
              f"assistant_msgs={sum(len(t.assistant_msgs) for t in turns)} "
              f"tool_results={sum(len(t.tool_results_by_id) for t in turns)}")
        return 0

    try:
        lf, provider, delivery = create_client(public_key, secret_key, host)
    except Exception as error:
        lh.info(f"export client unavailable; retry pending: {type(error).__name__}")
        return 0

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        # Reading before locking lets an older hook overwrite a newer snapshot.
        with lh.FileLock(LOCK_FILE, timeout_s=30):
            try:
                state = load_state()
                pending = dict(state.get(state_key) or {})
                legacy = bool(pending) and pending.get("version") != 2
                if legacy:
                    migrated = verified_migration(session_id, pending, public_key, host)
                    if migrated is not None:
                        pending = migrated
                        legacy = False
                    else:
                        lh.info("unverified migration: retaining legacy exporter behavior")
                res = devin_messages(session_id, earliest=legacy, legacy=legacy)
                if res is None:
                    return 0
                msgs, source_path = res
                extra = repo_metadata(source_path)
                if legacy:
                    n = emit_legacy_turns(lf, msgs, session_id, pending, source_path, extra)
                else:
                    if not pending:
                        pending = {"version": 2, "turns": {}}
                    pending["turns"] = dict(pending.get("turns") or {})
                    provider.id_generator.identities = pending.get("identities", {})
                    n = emit_turns(lf, msgs, session_id, source, label, pending,
                                   source_path, extra=extra)
                lf.flush()
                flushed = provider.force_flush()
                if not legacy and (not flushed or delivery.failed):
                    raise RuntimeError("observation delivery failed; checkpoint retained")
                state[state_key] = pending
                save_state(state)
                lh.info(f"exported {n} turns (source={source} session={session_id})")
            finally:
                # Drain any timed-out delivery before a newer hook gets the lock.
                try:
                    lf.shutdown()
                finally:
                    try:
                        provider.shutdown()
                    finally:
                        lf = None

    except Exception as e:
        lh.info(f"export retry pending: {type(e).__name__}")
    finally:
        if lf is not None:
            try:
                try:
                    lf.shutdown()
                finally:
                    provider.shutdown()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
