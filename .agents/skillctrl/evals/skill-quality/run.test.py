"""Check that failures and incomplete pairs cannot inflate eval scores."""

import unittest
from contextlib import redirect_stdout
import io
import run
import tasks
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from run import bind_manifest, cached_run, completed_agent, run_trigger, summarize, tool_path, write_json
from tasks import execute
from review import safe_embedded_data, comparison_benchmark


class PairedScores(unittest.TestCase):
    def test_default_current_and_explicit_baseline_select_matching_task_runs(self):
        for baseline in (None, 'baseline-ref'):
            with self.subTest(baseline=baseline), tempfile.TemporaryDirectory() as temp:
                workspace = Path(temp)
                catalog_names = {item['skill'] for item in json.loads((run.HERE / 'triggers.json').read_text())}
                catalog_names |= {item['skill_name'] for item in json.loads((run.HERE / 'tasks.json').read_text())}

                def snapshot(ref, destination):
                    self.assertIn(ref, ('HEAD', 'baseline-ref'))
                    for name in catalog_names:
                        path = destination / '.agents/skills' / name / 'SKILL.md'
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text('fixture')
                    oid = 'current-commit' if ref == 'HEAD' else 'baseline-commit'
                    (destination / '.snapshot-ref').write_text(oid)
                    return oid

                argv = ['run.py', '--workspace', str(workspace), '--model', 'fixture', '--ids', 'browser-positive']
                if baseline:
                    argv += ['--before', baseline]
                with patch.object(sys, 'argv', argv), \
                     patch('run.snapshot', side_effect=snapshot), \
                     patch('run.inspect_catalog', return_value={}), \
                     patch('run.subprocess.check_output', return_value='0.87.1'), \
                     patch('run.run_trigger', side_effect=lambda item, variant, *args: {
                         **self.row(item['id'], variant, True, True), 'status': 'completed'}) as trigger, \
                     redirect_stdout(io.StringIO()):
                    run.main()
                self.assertEqual(trigger.call_count, 2 if baseline else 1)
                manifest = json.loads((workspace / 'manifest.json').read_text())
                refs = {'after': 'current-commit', **({'before': 'baseline-commit'} if baseline else {})}
                self.assertEqual(manifest['refs'], refs)
                self.assertEqual((workspace / 'snapshots/before').exists(), bool(baseline))
                summary = json.loads((workspace / 'trigger-results.json').read_text())
                self.assertEqual(set(summary['summary']), set(refs))
                self.assertEqual('paired_summary' in summary, bool(baseline))

                eval_name = json.loads((tasks.HERE / 'tasks.json').read_text())[0]['eval_name']
                with patch.object(sys, 'argv', ['tasks.py', '--workspace', str(workspace), '--model', 'fixture',
                                               '--ids', eval_name]), \
                     patch('tasks.execute', side_effect=lambda item, variant, *args: {
                         'eval_name': item['eval_name'], 'variant': variant,
                         'status': 'completed', 'changed_files': []}) as task, \
                     redirect_stdout(io.StringIO()):
                    tasks.main()
                self.assertEqual(task.call_count, len(refs))
                self.assertEqual({call.args[1] for call in task.call_args_list}, set(refs))
                self.assertEqual(bool(list(workspace.glob('eval-*/old_skill'))), bool(baseline))


    def test_standard_aggregator_delta_does_not_invent_a_baseline_view(self):
        current = {'run_summary': {'with_skill': {'pass_rate': 1}, 'delta': {'pass_rate': '+1'}}}
        self.assertIsNone(comparison_benchmark(current))
        paired = {'run_summary': {**current['run_summary'], 'old_skill': {'pass_rate': 0}}}
        self.assertIs(comparison_benchmark(paired), paired)
        self.assertIsNone(comparison_benchmark(None))

    def test_html_artifacts_do_not_terminate_the_viewer_data_script(self):
        data = {'runs': [{'content': '</script><script>alert(1)</script>'}]}
        html = '<script>const EMBEDDED_DATA = ' + json.dumps(data) + ';</script>'
        safe = safe_embedded_data(html)
        self.assertEqual(safe.count('</script>'), 1)
        encoded = safe.split('const EMBEDDED_DATA = ', 1)[1].removesuffix(';</script>')
        self.assertEqual(json.loads(encoded), data)

    def test_artifact_capture_does_not_turn_a_model_error_into_success(self):
        for stop in ('stop', 'error'):
            with self.subTest(stop=stop), tempfile.TemporaryDirectory() as temp:
                workspace = Path(temp)
                fake = workspace / 'fake-pi.py'
                fake.write_text('#!/usr/bin/env python3\n'
                                'from pathlib import Path\n'
                                'Path("nested").mkdir()\n'
                                'Path("nested/out.md").write_text("artifact")\n'
                                'print(' + repr(json.dumps({'type': 'agent_end', 'messages': [
                                    {'role': 'assistant', 'stopReason': stop}]})) + ')\n')
                fake.chmod(0o755)
                item = {'id': 1, 'eval_name': 'fixture', 'skill_name': 'fixture', 'prompt': 'Complete the artifact',
                        'input_files': [{'path': 'input.txt', 'content': 'immutable'}]}
                with patch('tasks.command', return_value=[str(fake)]):
                    result = execute(item, 'after', workspace, 'fixture')
                run_dir = workspace / 'eval-fixture/with_skill/run-1'
                self.assertEqual(result['status'], 'completed' if stop == 'stop' else 'model_error')
                self.assertEqual(result['changed_files'], ['nested/out.md'])
                self.assertEqual((run_dir / 'outputs/nested__out.md').read_text(), 'artifact')
                self.assertEqual(result['initial_hashes']['input.txt'], result['final_hashes']['input.txt'])

    def test_pi_file_aliases_resolve_to_the_actual_read_target(self):
        root = Path('/tmp/fixture').resolve()
        self.assertEqual(tool_path('@nested/SKILL.md', root), root / 'nested/SKILL.md')
        self.assertEqual(tool_path('file:///tmp/other%20skill/SKILL.md', root), Path('/tmp/other skill/SKILL.md').resolve())
        self.assertEqual(tool_path('~/SKILL.md', root), Path.home() / 'SKILL.md')

    def test_retry_archives_partial_fixture_and_keeps_completed_results(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            directory = workspace / 'eval-fixture/old_skill'
            directory.mkdir(parents=True)
            (directory / 'partial.md').write_text('partial output')
            write_json(directory / 'result.json', {'scorable': False})
            cached = cached_run(directory, workspace, False, lambda row: row['scorable'])
            self.assertFalse(cached['scorable'])
            self.assertIsNone(cached_run(directory, workspace, True, lambda row: row['scorable']))
            self.assertFalse(directory.exists())
            self.assertEqual(len(list((workspace / 'attempts').rglob('partial.md'))), 1)
            write_json(directory / 'result.json', {'scorable': True})
            self.assertTrue(cached_run(directory, workspace, True, lambda row: row['scorable'])['scorable'])

    def test_cached_results_cannot_be_reused_with_a_different_model(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'manifest.json'
            bind_manifest(path, {'model': 'one'}, ('model',))
            with self.assertRaises(ValueError):
                bind_manifest(path, {'model': 'two'}, ('model',))
            self.assertEqual(json.loads(path.read_text())['model'], 'one')

    def test_only_a_successful_target_read_is_consultation(self):
        for failed in (False, True):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as temp:
                workspace = Path(temp)
                target = workspace / 'snapshots/after/.agents/skills/fixture/SKILL.md'
                target.parent.mkdir(parents=True)
                target.write_text('fixture')
                events = [
                    {'type': 'tool_execution_start', 'toolCallId': '1', 'toolName': 'read',
                     'args': {'path': str(target)}},
                    {'type': 'tool_execution_end', 'toolCallId': '1', 'isError': failed},
                    {'type': 'agent_end', 'messages': [{'role': 'assistant', 'stopReason': 'stop'}]}]
                script = 'print(' + repr('\n'.join(json.dumps(e) for e in events)) + ')'
                with patch('run.command', return_value=[sys.executable, '-c', script]):
                    result = run_trigger({'id': 'read', 'skill': 'fixture', 'query': 'raw',
                                          'should_trigger': True}, 'after', workspace, 'fixture', 5)
                self.assertEqual(result['triggered'], not failed)
                self.assertEqual(result['passed'], not failed)
                self.assertTrue(result['scorable'])

    def test_model_failure_is_not_a_completed_negative(self):
        event = {'type': 'agent_end', 'messages': [
            {'role': 'assistant', 'stopReason': 'toolUse'},
            {'role': 'assistant', 'stopReason': 'error', 'errorMessage': 'Endpoint unavailable'}]}
        self.assertFalse(completed_agent(event))
        event['messages'][-1]['stopReason'] = 'stop'
        self.assertTrue(completed_agent(event))
        self.assertFalse(completed_agent({'type': 'agent_end', 'messages': []}))

    def row(self, ident, variant, should, triggered, scorable=True):
        return {"id": ident, "variant": variant, "skill": "fixture", "should_trigger": should,
                "triggered": triggered, "scorable": scorable,
                "passed": triggered == should if scorable else None}

    def test_timeout_excludes_both_sides_from_paired_metrics(self):
        result = summarize([self.row("missing", "before", True, True),
                            self.row("missing", "after", True, False, False),
                            self.row("valid", "before", False, False),
                            self.row("valid", "after", False, False)])
        self.assertEqual(result["summary"]["after"]["incomplete"], 1)
        self.assertEqual(result["paired_summary"]["before"]["pairs"], 1)
        self.assertEqual(result["paired_summary"]["before"]["tp"], 0)
        self.assertEqual(result["paired_summary"]["after"]["tn"], 1)
        self.assertEqual(result["paired_changes"], [])

    def test_regression_and_false_positive_remain_failures(self):
        result = summarize([self.row("positive", "before", True, True),
                            self.row("positive", "after", True, False),
                            self.row("negative", "before", False, False),
                            self.row("negative", "after", False, True)])
        self.assertEqual(result["paired_summary"]["after"]["fn"], 1)
        self.assertEqual(result["paired_summary"]["after"]["fp"], 1)
        self.assertEqual(result["paired_summary"]["after"]["accuracy"], 0)
        self.assertEqual([row["change"] for row in result["paired_changes"]], ["regressed", "regressed"])


if __name__ == "__main__":
    unittest.main()
