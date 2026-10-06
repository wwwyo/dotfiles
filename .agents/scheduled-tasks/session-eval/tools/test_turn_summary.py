"""Exercise the transcript CLI through a paged local Observations API."""
import json
import os
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SCRIPT = Path(__file__).with_name('session_eval.py')
SID = 'compact-fixture'
TS = '2026-10-06T00:00:00Z'


def observation(oid, kind='AGENT', parent=None, summary=None, root=False, trace='trace-1'):
    metadata = {'source': 'fixture'}
    if summary is not None:
        metadata['telemetry_summary'] = summary
    return {'id': oid, 'traceId': trace, 'sessionId': SID, 'type': kind,
            'name': oid, 'parentObservationId': parent, 'isRootObservation': root,
            'startTime': TS, 'endTime': TS, 'metadata': metadata,
            'input': 'question', 'output': 'final answer', 'level': 'DEFAULT'}


def summary(name='exec', errors=True):
    return {'version': 1, 'generation_count': 2, 'tool_call_count': 1,
            'tool_names': {name: 1}, 'usage_by_model': {},
            'errors': [{'name': name, 'status_message': 'command failed', 'start_time': TS}]
            if errors else []}


class TranscriptTest(unittest.TestCase):
    def run_transcript(self, rows):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                query = parse_qs(urlsplit(self.path).query)
                requests.append(query)
                selected = list(rows)
                if 'filter' in query:
                    selected = [row for row in selected if row['isRootObservation']]
                if 'io' not in query['fields'][0].split(','):
                    selected = [{k: v for k, v in row.items() if k not in ('input', 'output')}
                                for row in selected]
                index = int(query.get('cursor', ['0'])[0])
                body = json.dumps({'data': selected[index:index + 2], 'meta': {
                    'cursor': str(index + 2) if index + 2 < len(selected) else None}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            env = dict(os.environ, LANGFUSE_PUBLIC_KEY='pk-fixture', LANGFUSE_SECRET_KEY='sk-fixture',
                       LANGFUSE_BASE_URL=f'http://127.0.0.1:{server.server_port}')
            result = subprocess.run([sys.executable, str(SCRIPT), 'transcript', SID],
                                    env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(all('telemetry_summary' in q['expandMetadata'][0] for q in requests))
            return json.loads(result.stdout)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_compact_and_full_signals_coexist_without_old_child_duplicates(self):
        compact = observation('compact', summary=json.dumps(summary()), root=True)
        old_gen = observation('old-generation', kind='GENERATION', parent='compact')
        old_tool = observation('old-tool', kind='TOOL', parent='old-generation')
        old_tool.update(level='ERROR', statusMessage='stale duplicate')
        # Subagent shares its parent's trace; its own summary must still be read.
        sub = observation('subagent', parent='compact', summary=summary('sub-tool', False))
        full = observation('full', kind='SPAN', root=True, trace='trace-2')
        tool = observation('full-tool', kind='TOOL', parent='full', trace='trace-2')
        tool.update(level='ERROR', statusMessage='full-mode failure', input='SECRET TOOL BODY')
        result = self.run_transcript([compact, old_gen, old_tool, sub, full, tool])
        self.assertEqual(result['turn_count'], 2)
        self.assertEqual(result['tool_calls'], 3)
        self.assertEqual(result['error_count'], 2)
        self.assertIn('generations: 4', result['transcript'])
        self.assertIn('exec×1', result['transcript'])
        self.assertIn('sub-tool×1', result['transcript'])
        self.assertIn('command failed', result['transcript'])
        self.assertIn('full-mode failure', result['transcript'])
        self.assertNotIn('stale duplicate', result['transcript'])
        self.assertNotIn('SECRET TOOL BODY', result['transcript'])
        self.assertIn('[user]\nquestion', result['transcript'])
        self.assertIn('[assistant]\nfinal answer', result['transcript'])

    def test_invalid_summary_keeps_full_mode_evidence(self):
        root = observation('root', summary='invalid-json', root=True)
        tool = observation('tool', kind='TOOL', parent='root')
        tool.update(level='ERROR', statusMessage='tool failed')
        result = self.run_transcript([root, tool])
        self.assertEqual(result['tool_calls'], 1)
        self.assertEqual(result['error_count'], 1)
        self.assertIn('tool failed', result['transcript'])

    def test_incomplete_summary_and_full_subagent_keep_error_evidence(self):
        root = observation('root', summary=json.dumps(summary()), root=True)
        sub = observation('subagent', parent='root', summary={'version': 1})
        gen = observation('generation', kind='GENERATION', parent='subagent')
        tool = observation('tool', kind='TOOL', parent='generation')
        tool.update(level='ERROR', statusMessage='subagent failed')
        result = self.run_transcript([root, sub, gen, tool])
        self.assertEqual(result['tool_calls'], 2)
        self.assertEqual(result['error_count'], 2)
        self.assertIn('subagent failed', result['transcript'])


if __name__ == '__main__':
    unittest.main()
