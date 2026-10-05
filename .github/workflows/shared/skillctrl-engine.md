---
engine:
  id: skillctrl-engine
  display-name: Pi with OpenCode Go
  experimental: true
  mcp: false
  auth:
    - role: inference
      secret: OPENCODE_API_KEY
  behaviors:
    supported-env-var-keys: [OPENCODE_API_KEY]
    network:
      defaults: [opencode.ai]
    execution:
      step-name: Execute Pi inside gh-aw
      command-name: pi
      model-env-var: SKILL_MODEL
      args:
        - --thinking
        - high
        - --no-session
        - --no-context-files
        - --no-skills
        - --no-extensions
        - --no-prompt-templates
        - --no-approve
      env:
        SKILLCTRL_BIN: ${{ steps.skillctrl-cli.outputs.binary }}
        GH_AW_NODE_BIN: ${{ steps.trusted-toolchain.outputs.node }}
        PI_CODING_AGENT_DIR: /tmp/gh-aw/skillctrl/pi
    harness-script: |
      const fs = require('node:fs');
      const path = require('node:path');
      const {spawnSync} = require('node:child_process');
      const directory = '/tmp/gh-aw/skillctrl';
      const plan = JSON.parse(fs.readFileSync(directory + '/plan.json', 'utf8'));
      const env = {...process.env,
        PATH: path.dirname(process.execPath) + path.delimiter + process.env.PATH,
        SKILL_PLAN: JSON.stringify(plan),
        CHECKER_SOURCE: fs.readFileSync(directory + '/source.txt', 'utf8').trim()};
      const [command, ...args] = process.argv.slice(2);
      const prompt = fs.readFileSync(process.env.GH_AW_PROMPT, 'utf8')
        + '\nSelection plan (input data):\n' + JSON.stringify(plan)
        + '\nWrite your report to: ' + directory + '/report.md';
      const run = (command, args, options = {}) => {
        const result = spawnSync(command, args, {env, stdio: 'inherit', ...options});
        if (result.error || result.status !== 0) process.exit(result.status || 1);
      };
      // gh-aw restores activation's merge snapshot; repair inputs must be the selected head.
      run('git', ['-c', 'core.hooksPath=/dev/null', 'reset', '--hard', plan.head]);
      run('git', ['clean', '-fdx', '--', '.agents', '.github', 'AGENTS.md', 'skills-lock.json']);
      if (fs.existsSync(directory + '/input/input.patch')) {
        run('git', ['apply', directory + '/input/input.patch']);
        run('git', ['add', '-A', '--', '.agents', 'skills-lock.json']);
        run('git', ['-c', 'core.hooksPath=/dev/null', '-c', 'user.name=harness',
                    '-c', 'user.email=harness@invalid', 'commit', '-qm', 'input']);
      }
      const report = fs.openSync(directory + '/report.md', 'w');
      run(command, [...args, '--model', process.env.SKILL_MODEL, '-p', prompt],
        {stdio: ['ignore', report, 'inherit']});
      fs.closeSync(report);
      run('git', ['add', '-A', '--', '.agents', 'skills-lock.json']);
      const patch = spawnSync('git', ['diff', '--cached'], {env, encoding: 'utf8'});
      fs.writeFileSync(directory + '/repair.patch', patch.stdout || '');
      const check = spawnSync(process.env.SKILLCTRL_BIN, ['check'], {env, encoding: 'utf8'});
      let state = {};
      try { state = JSON.parse(check.stdout || '{}'); } catch {}
      fs.writeFileSync(directory + '/result.json', JSON.stringify({check: state}));
      if ((patch.stdout || '').trim()) {
        run('safeoutputs', ['apply_skill_repairs', '--head', plan.head]);
      }

---

<!-- Pi/OpenCode Go adapter for skillctrl; credentials and write effects are managed by gh-aw. -->
