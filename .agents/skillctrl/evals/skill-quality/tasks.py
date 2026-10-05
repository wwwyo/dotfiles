#!/usr/bin/env python3
"""Execute fixture tasks with the selected skill snapshot(s)."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from run import HERE, bind_manifest, cached_run, command, completed_agent, write_json


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def configuration(variant):
    return 'with_skill' if variant == 'after' else 'old_skill'


def execute(item, variant, workspace, model, retry_incomplete=False, timeout=600):
    config = configuration(variant)
    run_dir = workspace / ('eval-' + item['eval_name']) / config / 'run-1'
    cached = cached_run(run_dir, workspace, retry_incomplete, lambda row: row['status'] == 'completed')
    if cached is not None:
        return cached
    fixture = run_dir / 'fixture'
    fixture.mkdir(parents=True, exist_ok=True)
    for file in item['input_files']:
        path = fixture / file['path']
        if not path.resolve().is_relative_to(fixture.resolve()):
            raise ValueError('Fixture input path is outside its run directory')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file['content'])
    before = hashes(fixture)
    skills = workspace / 'snapshots' / variant / '.agents/skills'
    skill = skills / item['skill_name'] / 'SKILL.md'
    prompt = (f"Read and apply this skill: {skill}\nWorking directory: {fixture}\n"
              "Modify only files within this fixture. The file tools are available; shell, browser, network and external services are unavailable. "
              "Complete the requested artifacts using the supplied facts. Do not claim you ran checks that require unavailable tools.\n\n"
              + item['prompt'])
    argv = command(skills, prompt, model, 'read,grep,find,ls,write,edit')
    argv[1:1] = ['-e', str(HERE / 'fixture-guard.ts')]
    env = dict(os.environ, SKILL_EVAL_READ_ROOT=str(skills))
    started = time.monotonic()
    status = 'completed'
    with (run_dir / 'transcript.jsonl').open('w') as output, (run_dir / 'stderr.txt').open('w') as errors:
        proc = subprocess.Popen(argv, cwd=fixture, env=env, stdout=output, stderr=errors)
        try:
            code = proc.wait(timeout=timeout)
            if code != 0:
                status = 'process_error'
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            status = 'timeout'
    final, tokens, tools, completed, models = '', 0, [], False, set()
    for line in (run_dir / 'transcript.jsonl').read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'agent_end':
            completed = completed_agent(event)
        if event.get('type') == 'message_end' and event.get('message', {}).get('role') == 'assistant':
            message = event['message']
            models.add((message.get('provider'), message.get('model')))
            text = '\n'.join(block.get('text', '') for block in message.get('content', []) if block.get('type') == 'text')
            if text:
                final = text
            tokens += message.get('usage', {}).get('totalTokens', 0)
        if event.get('type') == 'tool_execution_start':
            tools.append({'tool': event.get('toolName'), 'args': event.get('args')})
    if status == 'completed' and not completed:
        status = 'model_error'
    duration = round(time.monotonic() - started, 3)
    write_json(run_dir / 'timing.json', {'total_tokens': tokens, 'duration_ms': round(duration * 1000), 'total_duration_seconds': duration})
    artifacts = run_dir / 'outputs'
    artifacts.mkdir(exist_ok=True)
    (artifacts / 'response.md').write_text(final)
    after = hashes(fixture)
    changed = [path for path in sorted(before.keys() | after.keys()) if before.get(path) != after.get(path)]
    for path in changed:
        source = fixture / path
        if source.is_file():
            shutil.copy2(source, artifacts / path.replace('/', '__'))
    result = {'eval_id': item['id'], 'eval_name': item['eval_name'], 'variant': variant,
              'status': status, 'duration_seconds': duration, 'total_tokens': tokens,
              'observed_models': sorted(models),
              'changed_files': changed, 'initial_hashes': before, 'final_hashes': after,
              'tool_calls': tools}
    write_json(run_dir / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--ids', help='Comma-separated eval names to execute')
    parser.add_argument('--retry-incomplete', action='store_true')
    parser.add_argument('--timeout', type=int, default=600)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    dataset = HERE / 'tasks.json'
    items = json.loads(dataset.read_text())
    trigger_manifest = json.loads((workspace / 'manifest.json').read_text())
    if trigger_manifest['model'] != args.model:
        raise ValueError('Tasks must use the same model as the trigger evaluation')
    for variant, ref in trigger_manifest['refs'].items():
        if (workspace / 'snapshots' / variant / '.snapshot-ref').read_text().strip() != ref:
            raise ValueError('Task snapshot differs from trigger manifest')
        for item in items:
            if not (workspace / 'snapshots' / variant / '.agents/skills' / item['skill_name'] / 'SKILL.md').is_file():
                raise ValueError(f"Target skill {item['skill_name']} is absent from {variant}")
    manifest = {key: trigger_manifest[key] for key in ('refs', 'model', 'thinking', 'pi_version')}
    manifest['dataset_sha256'] = hashlib.sha256(dataset.read_bytes()).hexdigest()
    bind_manifest(workspace / 'task-manifest.json', manifest, tuple(manifest))
    if args.ids:
        ids = set(args.ids.split(','))
        items = [item for item in items if item['eval_name'] in ids]
        if len(items) != len(ids):
            raise ValueError('Unknown eval name')
    variants = list(trigger_manifest['refs'])
    configurations = [configuration(variant) for variant in variants]
    for item in items:
        eval_dir = workspace / ('eval-' + item['eval_name'])
        metadata = {'eval_id': item['id'], 'eval_name': item['eval_name'], 'prompt': item['prompt'],
                    'assertions': [a['text'] for a in item['assertions']]}
        for destination in [eval_dir, *(eval_dir / config for config in configurations)]:
            write_json(destination / 'eval_metadata.json', metadata)
    work = [(item, variant) for i, item in enumerate(items)
            for variant in (variants if i % 2 else variants[::-1])]
    selected = {item['eval_name'] for item in items}
    results = [json.loads(p.read_text()) for p in workspace.glob('eval-*/*/run-*/result.json')
               if p.parent.parent.parent.name.removeprefix('eval-') not in selected
               and p.parent.parent.name in configurations]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(execute, item, variant, workspace, args.model, args.retry_incomplete, args.timeout)
                   for item, variant in work]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps({key: result[key] for key in ('eval_name', 'variant', 'status', 'changed_files')}), flush=True)
            write_json(workspace / 'task-results.json', results)


if __name__ == '__main__':
    main()
