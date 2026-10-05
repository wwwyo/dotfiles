#!/usr/bin/env python3
"""Collect runtime evidence from reviewed, local fixture code for task grading."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from run import write_json


def invoke(root, script, arguments):
    result = subprocess.run([sys.executable, script, *arguments], cwd=root,
                            text=True, capture_output=True, timeout=10)
    return {'argv': [script, *arguments], 'exit': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr}


def probe(run):
    result = json.loads((run / 'result.json').read_text())
    if result['status'] != 'completed':
        raise ValueError('Do not grade incomplete execution as success')
    source = run / 'fixture'
    scratch = run / 'runtime-fixture'
    if scratch.exists():
        raise ValueError('Use a new runtime directory for another probe')
    shutil.copytree(source, scratch)
    facts = []
    if (scratch / 'sumcsv.py').exists():
        facts.append(invoke(scratch, 'sumcsv.py', ['examples/expenses.csv']))
    elif (scratch / 'cli.py').exists():
        state = scratch / 'notes.json'
        initial = state.read_bytes()
        def call(arguments):
            state.write_bytes(initial)
            row = invoke(scratch, 'cli.py', arguments)
            row['initial_state_sha256'] = hashlib.sha256(initial).hexdigest()
            row['final_state_sha256'] = hashlib.sha256(state.read_bytes()).hexdigest()
            row['final_state'] = json.loads(state.read_text())
            facts.append(row)
        call(['list'])
        call(['schema', 'rename'])
        valid = json.dumps({'id': 'n1', 'patch': {'title': 'New'}})
        call(['rename', '--json', valid, '--dry-run'])
        call(['rename', '--json', valid])
        invalid = [{'id': 'n1', 'patch': {'title': 'New'}, 'unknown': True},
                   {'id': 'n1', 'patch': {'title': 'New', 'unknown': True}},
                   {'id': 'n1', 'patch': {'title': ''}},
                   {'id': 'missing', 'patch': {'title': 'New'}}]
        invalid.extend({'id': 'n1' + suffix, 'patch': {'title': 'New'}}
                       for suffix in ('?', '#', '%', '\x00', '\x1b'))
        for payload in invalid:
            call(['rename', '--json', json.dumps(payload)])
        call(['list', '--fields', 'id,title'])
    else:
        facts.append(invoke(scratch, 'packet-report/scripts/summarize.py',
                            ['samples/packets.csv']))
    write_json(run / 'runtime.json', facts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    probe(args.run.resolve())
