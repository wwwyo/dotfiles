#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
python3 .agents/skillctrl/evals/skill-quality/run.test.py
node .agents/skillctrl/evals/skill-quality/fixture-paths.test.mjs
