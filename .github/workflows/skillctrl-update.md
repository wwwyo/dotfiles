---
name: Skillctrl Update
description: Refresh upstream skills weekly and reconcile them with saved customization intent.
intent: Acquire upstream originals on a schedule, adapt installed skills to saved intent, and open a draft PR.
on:
  schedule:
    - cron: "0 0 * * 6" # 土曜09:00 JST
  workflow_dispatch:
  needs: [select]
permissions:
  contents: read
  pull-requests: read
strict: true
runs-on: ubuntu-latest
runs-on-slim: ubuntu-latest
concurrency:
  group: skillctrl-update
  cancel-in-progress: true
if: always() && !cancelled() && needs.select.result == 'success' && needs.select.outputs.changed == 'true' && needs.select.outputs.review == 'true' && needs.select.outputs.authenticated == 'true'
checkout:
  ref: ${{ github.sha }}
  fetch-depth: 0
network:
  allowed: [defaults, opencode.ai]
tools:
  cli-proxy: true
model: opencode-go/space-bunny-free
runtimes:
  node:
    version: ${{ needs.select.outputs.node }}
imports:
  - shared/skillctrl-engine.md
steps:
  - name: Read the trusted skillctrl pin
    run: |
      mkdir -p /tmp/gh-aw/skillctrl-cli
      python3 - <<'PYTHON'
      import json, os, re, subprocess, tomllib
      from pathlib import Path
      source = os.environ['CHECKER_SOURCE']
      if not re.fullmatch(r'[0-9a-f]{40}', source):
          raise ValueError('trusted source must be a commit')
      config = tomllib.loads(subprocess.check_output(['git', 'show', source + ':home/dot_config/mise/config.toml'], text=True))
      pin = config['tools']['go:github.com/wwwyo/skillctrl']
      if not isinstance(pin, str) or not re.fullmatch(r'[0-9a-f]{40}', pin):
          raise ValueError('trusted skillctrl version must be an exact commit pin')
      toolchain = config['tools']['go']
      if not isinstance(toolchain, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', toolchain):
          raise ValueError('trusted go toolchain must be an exact pin')
      lines = ['[tools]', '"go:github.com/wwwyo/skillctrl" = ' + json.dumps(pin), 'go = ' + json.dumps(toolchain), '', '[settings]']
      for name in ['pin', 'minimum_release_age']:
          lines.append(name + ' = ' + json.dumps(config['settings'][name]))
      Path('/tmp/gh-aw/skillctrl-cli/mise.toml').write_text('\n'.join(lines) + '\n')
      Path('/tmp/gh-aw/skillctrl-cli/global.toml').write_text('')
      node = config['tools'].get('node', '')
      Path('/tmp/gh-aw/skillctrl-cli/node.txt').write_text(str(node))
      pi = config['tools'].get('npm:@earendil-works/pi-coding-agent', '')
      Path('/tmp/gh-aw/skillctrl-cli/pi.txt').write_text(str(pi))
      lock_text = subprocess.check_output(['git', 'show', source + ':home/dot_config/mise/mise.lock'], text=True)
      selected_blocks = []
      for tool, version in [('go:github.com/wwwyo/skillctrl', pin), ('go', toolchain)]:
          name = json.dumps(tool) if ':' in tool else tool
          blocks = re.findall(r'(?ms)^\[\[tools\.' + re.escape(name) + r'\]\]\n.*?(?=^\[\[tools\.|\Z)', lock_text)
          matching = [block for block in blocks if tomllib.loads(block)['tools'][tool][0]['version'] == version]
          if len(matching) != 1:
              raise ValueError(f'trusted {tool} lock must match the exact pin')
          selected_blocks.append(matching[0])
      Path('/tmp/gh-aw/skillctrl-cli/mise.lock').write_text(''.join(selected_blocks))
      PYTHON
  - uses: jdx/mise-action@c2a87611a18de5b3828c5652fe268e992400cb5c
    env:
      MISE_GLOBAL_CONFIG_FILE: /tmp/gh-aw/skillctrl-cli/global.toml
      MISE_DATA_DIR: /tmp/gh-aw/skillctrl-cli/data
    with:
      version: 2026.9.12
      working_directory: /tmp/gh-aw/skillctrl-cli
      env: false
      cache: false
      add_shims_to_path: false
      export_path: false
  - name: Bind the trusted skillctrl executable
    id: skillctrl-cli
    working-directory: /tmp/gh-aw/skillctrl-cli
    env:
      MISE_GLOBAL_CONFIG_FILE: /tmp/gh-aw/skillctrl-cli/global.toml
      MISE_DATA_DIR: /tmp/gh-aw/skillctrl-cli/data
    run: |
      binary="$(mise which skillctrl)"
      echo "SKILLCTRL_BIN=$binary" >> "$GITHUB_ENV"
      echo "binary=$binary" >> "$GITHUB_OUTPUT"
  - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c
    with:
      name: skillctrl-input
      path: /tmp/gh-aw/skillctrl/input
  - name: Prepare immutable selection and trusted validator
    env:
      CHECKER_SOURCE: ${{ needs.select.outputs.source }}
      SKILL_PLAN: ${{ needs.select.outputs.plan }}
    run: |
      mkdir -p /tmp/gh-aw/skillctrl/pi
      printf '%s' "$SKILL_PLAN" > /tmp/gh-aw/skillctrl/plan.json
      printf '%s' "$CHECKER_SOURCE" > /tmp/gh-aw/skillctrl/source.txt
      git show "$CHECKER_SOURCE:home/dot_pi/agent/models.json" > /tmp/gh-aw/skillctrl/pi/models.json
      python3 - <<'PYTHON'
      import json, os, subprocess, tomllib
      from pathlib import Path
      source = os.environ['CHECKER_SOURCE']
      config = tomllib.loads(subprocess.check_output(['git', 'show', source + ':home/dot_config/mise/config.toml'], text=True))
      tools = {'node': config['tools']['node'],
               'npm:@earendil-works/pi-coding-agent': config['tools']['npm:@earendil-works/pi-coding-agent']}
      lines = ['[tools]'] + [json.dumps(k) + ' = ' + json.dumps(v) for k, v in tools.items()]
      lines += ['', '[settings]']
      for name in ['pin', 'minimum_release_age']:
          lines.append(name + ' = ' + json.dumps(config['settings'][name]))
      Path('/tmp/gh-aw/skillctrl/mise.toml').write_text('\n'.join(lines) + '\n')
      PYTHON
  - uses: jdx/mise-action@c2a87611a18de5b3828c5652fe268e992400cb5c
    with:
      version: 2026.9.12
      working_directory: /tmp/gh-aw/skillctrl
      env: true
      cache: false
      add_shims_to_path: false
  - name: Bind the agent runtime to the trusted mise pin
    id: trusted-toolchain
    working-directory: /tmp/gh-aw/skillctrl
    env:
      EXPECTED_NODE: ${{ needs.select.outputs.node }}
    run: |
      node="$(mise which node)"
      test "$("$node" --version)" = "v$EXPECTED_NODE"
      echo "node=$node" >> "$GITHUB_OUTPUT"
post-steps:
  - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
    with:
      name: skillctrl-repair
      path: |
        /tmp/gh-aw/skillctrl/repair.patch
        /tmp/gh-aw/skillctrl/report.md
        /tmp/gh-aw/skillctrl/result.json
      if-no-files-found: error
      retention-days: 7
safe-outputs:
  activation-comments: false
  report-failure-as-issue: false
  threat-detection:
    engine: false
  jobs:
    apply-skill-repairs:
      description: Validate repairs and publish to the triggering PR or a verified scheduled update draft PR.
      runs-on: ubuntu-latest
      inputs:
        head:
          type: string
          required: true
          description: Selected immutable skill input SHA.
      permissions:
        contents: write
        pull-requests: write
      env:
        PR_BASE: ${{ github.event.pull_request.base.sha || github.sha }}
        PR_HEAD: ${{ github.event.pull_request.head.sha || github.sha }}
        PR_REF: ${{ github.event.pull_request.head.ref }}
        PR_NUMBER: ${{ github.event.pull_request.number }}
        DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}
        CI_DIR: /tmp/skillctrl
        CHECKER_SOURCE: ${{ github.event.pull_request.base.sha || github.sha }}
        GH_TOKEN: ${{ github.token }}
      steps:
        - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
          with:
            ref: ${{ github.event.pull_request.head.sha || github.sha }}
            fetch-depth: 0
            persist-credentials: false
        - name: Read the trusted skillctrl pin
          run: |
            mkdir -p /tmp/gh-aw/skillctrl-cli
            python3 - <<'PYTHON'
            import json, os, re, subprocess, tomllib
            from pathlib import Path
            source = os.environ['CHECKER_SOURCE']
            if not re.fullmatch(r'[0-9a-f]{40}', source):
                raise ValueError('trusted source must be a commit')
            config = tomllib.loads(subprocess.check_output(['git', 'show', source + ':home/dot_config/mise/config.toml'], text=True))
            pin = config['tools']['go:github.com/wwwyo/skillctrl']
            if not isinstance(pin, str) or not re.fullmatch(r'[0-9a-f]{40}', pin):
                raise ValueError('trusted skillctrl version must be an exact commit pin')
            toolchain = config['tools']['go']
            if not isinstance(toolchain, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', toolchain):
                raise ValueError('trusted go toolchain must be an exact pin')
            lines = ['[tools]', '"go:github.com/wwwyo/skillctrl" = ' + json.dumps(pin), 'go = ' + json.dumps(toolchain), '', '[settings]']
            for name in ['pin', 'minimum_release_age']:
                lines.append(name + ' = ' + json.dumps(config['settings'][name]))
            Path('/tmp/gh-aw/skillctrl-cli/mise.toml').write_text('\n'.join(lines) + '\n')
            Path('/tmp/gh-aw/skillctrl-cli/global.toml').write_text('')
            node = config['tools'].get('node', '')
            Path('/tmp/gh-aw/skillctrl-cli/node.txt').write_text(str(node))
            pi = config['tools'].get('npm:@earendil-works/pi-coding-agent', '')
            Path('/tmp/gh-aw/skillctrl-cli/pi.txt').write_text(str(pi))
            lock_text = subprocess.check_output(['git', 'show', source + ':home/dot_config/mise/mise.lock'], text=True)
            selected_blocks = []
            for tool, version in [('go:github.com/wwwyo/skillctrl', pin), ('go', toolchain)]:
                name = json.dumps(tool) if ':' in tool else tool
                blocks = re.findall(r'(?ms)^\[\[tools\.' + re.escape(name) + r'\]\]\n.*?(?=^\[\[tools\.|\Z)', lock_text)
                matching = [block for block in blocks if tomllib.loads(block)['tools'][tool][0]['version'] == version]
                if len(matching) != 1:
                    raise ValueError(f'trusted {tool} lock must match the exact pin')
                selected_blocks.append(matching[0])
            Path('/tmp/gh-aw/skillctrl-cli/mise.lock').write_text(''.join(selected_blocks))
            PYTHON
        - uses: jdx/mise-action@c2a87611a18de5b3828c5652fe268e992400cb5c
          env:
            MISE_GLOBAL_CONFIG_FILE: /tmp/gh-aw/skillctrl-cli/global.toml
            MISE_DATA_DIR: /tmp/gh-aw/skillctrl-cli/data
          with:
            version: 2026.9.12
            working_directory: /tmp/gh-aw/skillctrl-cli
            env: false
            cache: false
            add_shims_to_path: false
            export_path: false
        - name: Bind the trusted skillctrl executable
          id: skillctrl-cli
          working-directory: /tmp/gh-aw/skillctrl-cli
          env:
            MISE_GLOBAL_CONFIG_FILE: /tmp/gh-aw/skillctrl-cli/global.toml
            MISE_DATA_DIR: /tmp/gh-aw/skillctrl-cli/data
          run: |
            binary="$(mise which skillctrl)"
            echo "SKILLCTRL_BIN=$binary" >> "$GITHUB_ENV"
            echo "binary=$binary" >> "$GITHUB_OUTPUT"
        - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c
          with:
            name: skillctrl-input
            path: /tmp/skillctrl/input
        - name: Apply the scheduled import input
          run: |
            mkdir -p "$CI_DIR"
            git apply "$CI_DIR/input/input.patch"
            cp "$CI_DIR/input/plan.json" "$CI_DIR/plan.json"
        - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c
          with:
            name: skillctrl-repair
            path: /tmp/gh-aw/skillctrl
        - name: Validate repair scope and apply the patch
          run: |
            python3 - <<'PY'
            import re
            from pathlib import Path
            patch = Path('/tmp/gh-aw/skillctrl/repair.patch').read_text()
            paths = set()
            for line in patch.splitlines():
                m = re.match(r'^diff --git [^/]+/(\S+) [^/]+/(\S+)$', line)
                if m:
                    paths.update(m.groups())
            allowed = re.compile(r'^(?:\.agents/skills/|skills-lock\.json$|\.agents/skillctrl/lock\.json$|\.agents/skillctrl/upstreams\.json$|\.agents/skillctrl/intents/lock\.json$)')
            bad = [p for p in paths if not allowed.match(p)]
            if bad:
                raise SystemExit('repair touches out-of-scope paths: ' + ', '.join(sorted(bad)))
            if not patch.strip():
                raise SystemExit('repair patch is empty')
            PY
            git apply --check /tmp/gh-aw/skillctrl/repair.patch
            git apply /tmp/gh-aw/skillctrl/repair.patch
        - name: Run repository checks
          run: |
            set -euo pipefail
            for t in tests/*.test.sh .agents/skillctrl/*.test.sh; do
              echo "=== $t ==="
              bash "$t"
            done
        - name: Verify the accepted lock and publish
          run: |
            "$SKILLCTRL_BIN" check > "$CI_DIR/check.json"
            jq -e '.local.lock_changed == false' "$CI_DIR/check.json"
            cp "$CI_DIR/check.json" /tmp/skillctrl-lock-state.json
            git add -A -- .agents skills-lock.json
            if git diff --cached --quiet; then
              echo 'No changes to publish.'
              exit 0
            fi
            git -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
              -c core.hooksPath=/dev/null commit -qm 'chore(skills): reconcile skillctrl lock state'
            credential="$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 | tr -d '\n')"
            echo "::add-mask::$credential"
            git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $credential" \
              fetch origin refs/heads/automation/skillctrl-update || true
            if git rev-parse --verify -q FETCH_HEAD > /dev/null; then
              git -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
                -c core.hooksPath=/dev/null merge -s ours --no-edit -m 'chore(skills): supersede previous upstream refresh' FETCH_HEAD
            fi
            git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $credential" \
              push origin "HEAD:refs/heads/automation/skillctrl-update"
            existing="$(jq -r '.existing_pr // empty' "$CI_DIR/plan.json" 2>/dev/null || true)"
            if [[ -z "$existing" ]]; then
              gh pr create --draft --base "$DEFAULT_BRANCH" --head automation/skillctrl-update \
                --title "chore(skills): weekly upstream refresh" \
                --body "Automated upstream skill refresh reconciled with saved intents by the skillctrl update workflow."
            fi
        - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
          if: always()
          with:
            name: skillctrl-lock-state
            path: /tmp/skillctrl-lock-state.json
            if-no-files-found: error
            retention-days: 7
jobs:
  agent:
    if: "!cancelled() && needs.activation.result == 'success'"
  activation:
    needs: [select]
    if: needs.select.outputs.changed == 'true' && needs.select.outputs.review == 'true' && needs.select.outputs.authenticated == 'true'
  select:
    permissions:
      contents: read
      pull-requests: read
    if: github.ref == format('refs/heads/{0}', github.event.repository.default_branch)
    runs-on: ubuntu-latest
    outputs:
      authenticated: ${{ steps.auth.outputs.ready }}
      changed: ${{ steps.plan.outputs.changed }}
      review: ${{ steps.plan.outputs.review }}
      plan: ${{ steps.plan.outputs.plan }}
      source: ${{ steps.plan.outputs.source }}
      node: ${{ steps.plan.outputs.node }}
    env:
      PR_BASE: ${{ github.event.pull_request.base.sha || github.sha }}
      PR_HEAD: ${{ github.event.pull_request.head.sha || github.sha }}
      CI_DIR: /tmp/skillctrl
      DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}
      CHECKER_SOURCE: ${{ github.event.pull_request.base.sha || github.sha }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          fetch-depth: 0
          persist-credentials: false
      - name: Read the trusted skillctrl pin
        run: |
          mkdir -p /tmp/gh-aw/skillctrl-cli
          python3 - <<'PYTHON'
          import json, os, re, subprocess, tomllib
          from pathlib import Path
          source = os.environ['CHECKER_SOURCE']
          if not re.fullmatch(r'[0-9a-f]{40}', source):
              raise ValueError('trusted source must be a commit')
          config = tomllib.loads(subprocess.check_output(['git', 'show', source + ':home/dot_config/mise/config.toml'], text=True))
          pin = config['tools']['go:github.com/wwwyo/skillctrl']
          if not isinstance(pin, str) or not re.fullmatch(r'[0-9a-f]{40}', pin):
              raise ValueError('trusted skillctrl version must be an exact commit pin')
          toolchain = config['tools']['go']
          if not isinstance(toolchain, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', toolchain):
              raise ValueError('trusted go toolchain must be an exact pin')
          lines = ['[tools]', '"go:github.com/wwwyo/skillctrl" = ' + json.dumps(pin), 'go = ' + json.dumps(toolchain), '', '[settings]']
          for name in ['pin', 'minimum_release_age']:
              lines.append(name + ' = ' + json.dumps(config['settings'][name]))
          Path('/tmp/gh-aw/skillctrl-cli/mise.toml').write_text('\n'.join(lines) + '\n')
          Path('/tmp/gh-aw/skillctrl-cli/global.toml').write_text('')
          node = config['tools'].get('node', '')
          Path('/tmp/gh-aw/skillctrl-cli/node.txt').write_text(str(node))
          pi = config['tools'].get('npm:@earendil-works/pi-coding-agent', '')
          Path('/tmp/gh-aw/skillctrl-cli/pi.txt').write_text(str(pi))
          lock_text = subprocess.check_output(['git', 'show', source + ':home/dot_config/mise/mise.lock'], text=True)
          selected_blocks = []
          for tool, version in [('go:github.com/wwwyo/skillctrl', pin), ('go', toolchain)]:
              name = json.dumps(tool) if ':' in tool else tool
              blocks = re.findall(r'(?ms)^\[\[tools\.' + re.escape(name) + r'\]\]\n.*?(?=^\[\[tools\.|\Z)', lock_text)
              matching = [block for block in blocks if tomllib.loads(block)['tools'][tool][0]['version'] == version]
              if len(matching) != 1:
                  raise ValueError(f'trusted {tool} lock must match the exact pin')
              selected_blocks.append(matching[0])
          Path('/tmp/gh-aw/skillctrl-cli/mise.lock').write_text(''.join(selected_blocks))
          PYTHON
      - uses: jdx/mise-action@c2a87611a18de5b3828c5652fe268e992400cb5c
        env:
          MISE_GLOBAL_CONFIG_FILE: /tmp/gh-aw/skillctrl-cli/global.toml
          MISE_DATA_DIR: /tmp/gh-aw/skillctrl-cli/data
        with:
          version: 2026.9.12
          working_directory: /tmp/gh-aw/skillctrl-cli
          env: false
          cache: false
          add_shims_to_path: false
          export_path: false
      - name: Bind the trusted skillctrl executable
        id: skillctrl-cli
        working-directory: /tmp/gh-aw/skillctrl-cli
        env:
          MISE_GLOBAL_CONFIG_FILE: /tmp/gh-aw/skillctrl-cli/global.toml
          MISE_DATA_DIR: /tmp/gh-aw/skillctrl-cli/data
        run: |
          binary="$(mise which skillctrl)"
          echo "SKILLCTRL_BIN=$binary" >> "$GITHUB_ENV"
          echo "binary=$binary" >> "$GITHUB_OUTPUT"
      - name: Check inference credential availability
        id: auth
        env:
          OPENCODE_API_KEY: ${{ secrets.OPENCODE_API_KEY }}
        run: |
          if [[ -n "$OPENCODE_API_KEY" ]]; then
            echo 'ready=true' >> "$GITHUB_OUTPUT"
          else
            echo 'ready=false' >> "$GITHUB_OUTPUT"
            echo 'Intent review is inactive: configure the repository Actions secret OPENCODE_API_KEY.' >> "$GITHUB_STEP_SUMMARY"
          fi
      - name: Select changed skill inputs
        id: plan
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          mkdir -p "$CI_DIR"
          "$SKILLCTRL_BIN" --adapter git update > "$CI_DIR/update.json"
          git add -A -- .agents skills-lock.json
          git diff --cached > "$CI_DIR/input.patch"
          gh pr list --state open --head automation/skillctrl-update --json url > "$CI_DIR/existing.json" || echo '[]' > "$CI_DIR/existing.json"
          "$SKILLCTRL_BIN" check > "$CI_DIR/check.json"
          jq -er '.local.lock_changed | if type == "boolean" then tostring else error("invalid lock_changed") end' "$CI_DIR/check.json" > /dev/null
          echo "source=$CHECKER_SOURCE" >> "$GITHUB_OUTPUT"
          echo "node=$(cat /tmp/gh-aw/skillctrl-cli/node.txt)" >> "$GITHUB_OUTPUT"
          python3 - <<'PY'
          import json, os
          from pathlib import Path
          ci = Path(os.environ['CI_DIR'])
          check = json.loads((ci / 'check.json').read_text())
          local = check['local']
          plan = {'head': os.environ['PR_HEAD'], 'review_skills': local['review_skills'],
                  'needs_review': local['needs_review'], 'lock_changed': local['lock_changed']}
          changed = (ci / 'input.patch').read_text().strip() != ''
          existing = json.loads((ci / 'existing.json').read_text())
          plan.update(comparison=None, skills=local['skills'],
                      existing_pr=(existing[0]['url'] if existing else None))
          plan['changed'] = changed
          (ci / 'plan.json').write_text(json.dumps(plan))
          with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
              output.write(f"changed={str(changed).lower()}\n")
              output.write(f"review={str(local['needs_review']).lower()}\n")
              output.write('plan=' + json.dumps(plan) + '\n')
          with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
              if plan.get('existing_pr'):
                  summary.write(f"Existing update PR: {plan['existing_pr']}\n")
              summary.write(f"Selected skills: {len(plan['skills'])}; lock refresh: {plan['lock_changed']}\n")
          PY
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        if: steps.plan.outputs.changed == 'true'
        with:
          name: skillctrl-input
          path: |
            /tmp/skillctrl/input.patch
            /tmp/skillctrl/plan.json
            /tmp/skillctrl/check.json
          if-no-files-found: error
          retention-days: 7
  record:
    needs: select
    if: needs.select.outputs.changed == 'true' && needs.select.outputs.review != 'true'
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    env:
      SKILL_PLAN: ${{ needs.select.outputs.plan }}
      CHECKER_SOURCE: ${{ needs.select.outputs.source }}
      CI_DIR: /tmp/skillctrl
      DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}
      PR_REF: ${{ github.event.pull_request.head.ref }}
      GH_TOKEN: ${{ github.token }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          ref: ${{ github.event.pull_request.head.sha || github.sha }}
          fetch-depth: 0
          persist-credentials: false
      - name: Read the trusted skillctrl pin
        run: |
          mkdir -p /tmp/gh-aw/skillctrl-cli
          python3 - <<'PYTHON'
          import json, os, re, subprocess, tomllib
          from pathlib import Path
          source = os.environ['CHECKER_SOURCE']
          if not re.fullmatch(r'[0-9a-f]{40}', source):
              raise ValueError('trusted source must be a commit')
          config = tomllib.loads(subprocess.check_output(['git', 'show', source + ':home/dot_config/mise/config.toml'], text=True))
          pin = config['tools']['go:github.com/wwwyo/skillctrl']
          if not isinstance(pin, str) or not re.fullmatch(r'[0-9a-f]{40}', pin):
              raise ValueError('trusted skillctrl version must be an exact commit pin')
          toolchain = config['tools']['go']
          if not isinstance(toolchain, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', toolchain):
              raise ValueError('trusted go toolchain must be an exact pin')
          lines = ['[tools]', '"go:github.com/wwwyo/skillctrl" = ' + json.dumps(pin), 'go = ' + json.dumps(toolchain), '', '[settings]']
          for name in ['pin', 'minimum_release_age']:
              lines.append(name + ' = ' + json.dumps(config['settings'][name]))
          Path('/tmp/gh-aw/skillctrl-cli/mise.toml').write_text('\n'.join(lines) + '\n')
          Path('/tmp/gh-aw/skillctrl-cli/global.toml').write_text('')
          node = config['tools'].get('node', '')
          Path('/tmp/gh-aw/skillctrl-cli/node.txt').write_text(str(node))
          pi = config['tools'].get('npm:@earendil-works/pi-coding-agent', '')
          Path('/tmp/gh-aw/skillctrl-cli/pi.txt').write_text(str(pi))
          lock_text = subprocess.check_output(['git', 'show', source + ':home/dot_config/mise/mise.lock'], text=True)
          selected_blocks = []
          for tool, version in [('go:github.com/wwwyo/skillctrl', pin), ('go', toolchain)]:
              name = json.dumps(tool) if ':' in tool else tool
              blocks = re.findall(r'(?ms)^\[\[tools\.' + re.escape(name) + r'\]\]\n.*?(?=^\[\[tools\.|\Z)', lock_text)
              matching = [block for block in blocks if tomllib.loads(block)['tools'][tool][0]['version'] == version]
              if len(matching) != 1:
                  raise ValueError(f'trusted {tool} lock must match the exact pin')
              selected_blocks.append(matching[0])
          Path('/tmp/gh-aw/skillctrl-cli/mise.lock').write_text(''.join(selected_blocks))
          PYTHON
      - uses: jdx/mise-action@c2a87611a18de5b3828c5652fe268e992400cb5c
        env:
          MISE_GLOBAL_CONFIG_FILE: /tmp/gh-aw/skillctrl-cli/global.toml
          MISE_DATA_DIR: /tmp/gh-aw/skillctrl-cli/data
        with:
          version: 2026.9.12
          working_directory: /tmp/gh-aw/skillctrl-cli
          env: false
          cache: false
          add_shims_to_path: false
          export_path: false
      - name: Bind the trusted skillctrl executable
        id: skillctrl-cli
        working-directory: /tmp/gh-aw/skillctrl-cli
        env:
          MISE_GLOBAL_CONFIG_FILE: /tmp/gh-aw/skillctrl-cli/global.toml
          MISE_DATA_DIR: /tmp/gh-aw/skillctrl-cli/data
        run: |
          binary="$(mise which skillctrl)"
          echo "SKILLCTRL_BIN=$binary" >> "$GITHUB_ENV"
          echo "binary=$binary" >> "$GITHUB_OUTPUT"
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c
        with:
          name: skillctrl-input
          path: /tmp/skillctrl/input
      - name: Apply imported originals and prune stale accepted hashes
        run: |
          mkdir -p "$CI_DIR"
          git apply "$CI_DIR/input/input.patch"
          "$SKILLCTRL_BIN" record
      - name: Run repository checks
        run: |
          set -euo pipefail
          for t in tests/*.test.sh .agents/skillctrl/*.test.sh; do
            echo "=== $t ==="
            bash "$t"
          done
      - name: Verify the accepted lock and publish
        run: |
          "$SKILLCTRL_BIN" check > "$CI_DIR/check.json"
          jq -e '.local.lock_changed == false' "$CI_DIR/check.json"
          git add -A -- .agents skills-lock.json
          if git diff --cached --quiet; then
            echo 'No changes to publish.'
          else
            git -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
              -c core.hooksPath=/dev/null commit -qm 'chore(skills): reconcile skillctrl lock state'
            credential="$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 | tr -d '\n')"
            echo "::add-mask::$credential"
            git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $credential" \
              fetch origin refs/heads/automation/skillctrl-update || true
            if git rev-parse --verify -q FETCH_HEAD > /dev/null; then
              git -c user.name='github-actions[bot]' -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
                -c core.hooksPath=/dev/null merge -s ours --no-edit -m 'chore(skills): supersede previous upstream refresh' FETCH_HEAD
            fi
            git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $credential" \
              push origin "HEAD:refs/heads/automation/skillctrl-update"
            python3 - <<'PY'
            import json
            from pathlib import Path
            plan = json.loads(Path('/tmp/skillctrl/input/plan.json').read_text())
            Path('/tmp/skillctrl/existing-pr.txt').write_text(plan.get('existing_pr') or '')
            PY
            if [[ ! -s /tmp/skillctrl/existing-pr.txt ]]; then
              gh pr create --draft --base "$DEFAULT_BRANCH" --head automation/skillctrl-update \
                --title "chore(skills): weekly upstream refresh" \
                --body "Automated upstream skill refresh; no saved intents required re-adaptation."
            fi
          fi
          cp "$CI_DIR/check.json" /tmp/skillctrl-lock-state.json
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a
        with:
          name: skillctrl-lock-state
          path: /tmp/skillctrl-lock-state.json
          if-no-files-found: error
          retention-days: 7
  lock-status:
    name: Skill lock status
    needs: [select, record, agent, apply_skill_repairs]
    if: "always() && !cancelled() && needs.select.result != 'skipped'"
    runs-on: ubuntu-latest
    permissions: {}
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c
        if: needs.select.outputs.changed == 'true' && (needs.record.result == 'success' || needs.apply_skill_repairs.result == 'success')
        with:
          name: skillctrl-lock-state
          path: /tmp/skillctrl-status
      - name: Report final skill hash alignment
        env:
          SELECT_RESULT: ${{ needs.select.result }}
          SELECT_PLAN: ${{ needs.select.outputs.plan }}
          CHANGED: ${{ needs.select.outputs.changed }}
          AUTHENTICATED: ${{ needs.select.outputs.authenticated }}
        run: |
          python3 - <<'PY'
          import json, os
          from pathlib import Path
          if os.environ['SELECT_RESULT'] != 'success':
              raise SystemExit('::error::Skill selection failed; final hash alignment is unknown.')
          path = Path('/tmp/skillctrl-status/skillctrl-lock-state.json')
          plan = json.loads(os.environ['SELECT_PLAN'])
          if path.exists():
              state = json.loads(path.read_text())['local']
          else:
              state = {'lock_changed': plan['lock_changed'], 'needs_review': plan['needs_review'],
                       'skills': plan['skills']}
          missing = os.environ['CHANGED'] == 'true' and not path.exists()
          if state['lock_changed'] or missing:
              names = ', '.join(state.get('skills') or []) or 'publication result unavailable'
              reason = 'Inference credential is unavailable. ' if os.environ['AUTHENTICATED'] != 'true' and state.get('needs_review') else ''
              print('::error::' + reason + 'Skill hashes remain unrecorded: ' + names)
              with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
                  summary.write('❌ Skill lock is unresolved: ' + names + '\n')
              raise SystemExit(1)
          with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
              summary.write('✅ Skill hashes match the accepted lock.\n')
          PY
---

# Skill upstream refresh

A scheduled update imported new upstream originals. You reconcile the
installed skills with their saved customization intent. `skills-lock.json`
(repository root) is the native upstream registration and
`.agents/skillctrl/intents/<name>.md` holds each skill's saved intent.

The selection plan lists `review_skills`: registered upstream skills whose
directory hash drifted from the accepted lock after the import, plus `head`,
the default-branch commit being updated. For each one:

1. Read `.agents/skillctrl/intents/<name>.md` and the complete imported
   directory `.agents/skills/<name>/`, including references, scripts, and
   file modes.
2. Adapt the editable skill content so it satisfies its saved intent. Keep
   immutable bundled upstream snapshots under `references/` intact. Do not
   edit intent documents, workflows, or policy.
3. Verify the result, then run `"$SKILLCTRL_BIN" record <name>` for that
   verified skill only. `record` writes `.agents/skillctrl/lock.json`;
   it accepts content, it does not review it.
4. Leave unresolved adaptations unrecorded and report them.

Write a concise English report to the report path named in the prompt without
claiming unperformed checks. Do not commit, push, install dependencies or
execute upstream scripts. The harness validates the resulting patch and
requests `apply_skill_repairs` through safe outputs; a separate job verifies
the scope and the final hash gate, then publishes a draft PR. When no changed
hash requires review, deterministic selection skips this engine. If the
supplied plan is unexpectedly empty, call `noop` and do not request repairs.
