#!/usr/bin/env python3
"""Generate the standard skill-creator viewer with script-safe artifact data."""

import argparse
import importlib.util
import json
from pathlib import Path

from run import HERE


def safe_embedded_data(html):
    marker = 'const EMBEDDED_DATA = '
    start = html.index(marker) + len(marker)
    data, length = json.JSONDecoder().raw_decode(html[start:])
    # A literal closing script tag in a generated HTML artifact terminates the
    # viewer's data script even when it occurs inside a valid JSON string.
    encoded = json.dumps(data).replace('<', '\\u003c')
    return html[:start] + encoded + html[start + length:]


def comparison_benchmark(benchmark):
    # The standard aggregator adds delta even when no baseline was executed.
    configurations = set(benchmark.get('run_summary', {})) - {'delta'} if benchmark else set()
    return benchmark if len(configurations) >= 2 else None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--benchmark', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    path = HERE / 'vendor/skill-creator/generate_review.py'
    spec = importlib.util.spec_from_file_location('skill_review', path)
    viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(viewer)
    runs = viewer.find_runs(args.workspace)
    runs.sort(key=lambda run: (run['eval_id'], 'old_skill' in run['id']))
    benchmark = json.loads(args.benchmark.read_text()) if args.benchmark else None
    benchmark = comparison_benchmark(benchmark)
    html = viewer.generate_html(runs, 'skill-quality', {}, benchmark)
    args.output.write_text(safe_embedded_data(html))
