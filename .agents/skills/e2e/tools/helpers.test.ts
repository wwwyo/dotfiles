import { test, expect } from 'bun:test';
import { mkdtemp, mkdir, writeFile, readFile, rm, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { setTimeout as delay } from 'node:timers/promises';

const modelHelper = join(import.meta.dir, 'check-model.ts');
const auditHelper = join(import.meta.dir, 'audit-artifacts.ts');
const fixtureSecret = 'fixture-secret-never-print';
async function fixture(run: (root: string) => Promise<void>) {
  const root = await mkdtemp(join(tmpdir(), 'e2e-helpers-'));
  try { await run(root); } finally { await rm(root, { recursive: true, force: true }); }
}
function environment(root: string, extra: Record<string, string> = {}) {
  return { PATH: '/usr/bin:/bin', HOME: root, ...extra };
}
function cli(root: string, helper: string, args: string[] = [], extra: Record<string, string> = {}) {
  const result = spawnSync(process.execPath, [helper, ...args], { cwd: root, env: environment(root, extra), timeout: 15_000, encoding: 'utf8' });
  expect(result.error).toBeUndefined();
  expect(result.stderr).toBe('');
  expect(result.stdout).not.toContain(fixtureSecret);
  return { code: result.status, output: result.stdout };
}
async function modelProject(root: string, mode = 'pass') {
  for (const name of ['ai', 'playwright']) {
    await mkdir(join(root, 'node_modules', name), { recursive: true });
    await writeFile(join(root, 'node_modules', name, 'package.json'), JSON.stringify({ name, type: 'module', main: 'index.js' }));
  }
  await writeFile(join(root, 'e2e.config.ts'), `console.warn('${fixtureSecret}'); if (process.env.E2E_TELEMETRY_DISABLED !== '1') throw new Error(); export default { agents: { default: { model: { doGenerate() {}, projectModel: true } } } };`);
  await writeFile(join(root, 'node_modules/playwright/index.js'), `
    import { appendFileSync } from 'node:fs';
    export const chromium = { async launch(options) {
      if (options.env.FIXTURE_KEY) throw new Error();
      let color;
      return { async close() { appendFileSync('events', 'closed\\n'); ${mode === 'cleanup' ? 'throw new Error();' : ''} }, async newPage() { return {
        setDefaultTimeout() {}, async setContent(html) { color = html.includes('background:red') ? 'red' : 'blue'; },
        async screenshot() { return Buffer.from(color); }
      }; } };
    } };`);
  await writeFile(join(root, 'node_modules/ai/index.js'), `
    import { appendFileSync } from 'node:fs';
    export const jsonSchema = x => x; export const tool = x => x; export const Output = { object: x => x };
    export async function generateText(options) {
      if (!options.model.projectModel || options.maxRetries !== 0 || options.experimental_telemetry.isEnabled !== false || !options.abortSignal) throw new Error();
      appendFileSync('events', (options.tools ? 'tool-call' : 'vision') + '\\n');
      ${mode === 'hang' ? `await new Promise((_, reject) => options.abortSignal.addEventListener('abort', () => reject(new Error('${fixtureSecret}'))));` : ''}
      ${mode === 'error' ? `throw new Error('${fixtureSecret}');` : ''}
      const color = Buffer.from(options.messages[0].content[1].data).toString();
      if (options.tools) return { toolCalls: [{ toolName: 'record_color', input: { color: ${mode === 'tool' ? "'red'" : 'color'} } }] };
      if (!options.output.schema.required.includes('color')) throw new Error();
      return { output: { color: ${mode === 'vision' ? "'green'" : 'color'} } };
    }`);
}

test('help and invalid inputs need no project dependencies and never echo arguments', async () => fixture(async root => {
  for (const helper of [modelHelper, auditHelper]) {
    expect(cli(root, helper, ['--help']).code).toBe(0);
    expect(cli(root, helper, ['--invalid', fixtureSecret]).code).toBe(2);
  }
}));
test('project config and project packages perform exactly three checks and clean up', async () => fixture(async root => {
  await modelProject(root);
  const result = cli(root, modelHelper, [], { FIXTURE_KEY: fixtureSecret });
  expect(result.code).toBe(0);
  expect(JSON.parse(result.output)).toEqual({ status: 'passed', checks: ['vision-red', 'vision-blue', 'json-schema', 'tool-call'], requests: 3 });
  expect(await readFile(join(root, 'events'), 'utf8')).toBe('vision\nvision\ntool-call\nclosed\n');
}));
test('model failures, invalid capabilities and cleanup failure expose fixed verdicts', async () => {
  for (const [mode, code] of [['error', 'MODEL_CAPABILITY_FAILED'], ['vision', 'MODEL_VISION_INVALID'], ['tool', 'MODEL_TOOLS_INVALID'], ['cleanup', 'BROWSER_CLEANUP_FAILED']]) {
    await fixture(async root => {
      await modelProject(root, mode);
      const result = cli(root, modelHelper);
      expect(result.code).toBe(1);
      expect(JSON.parse(result.output).code).toBe(code);
      expect(await readFile(join(root, 'events'), 'utf8')).toContain('closed\n');
    });
  }
});
test('missing, ambiguous and explicit configs are deterministic', async () => fixture(async root => {
  expect(JSON.parse(cli(root, modelHelper).output).code).toBe('CONFIG_NOT_UNIQUE');
  await modelProject(root);
  await writeFile(join(root, 'e2e.config.mts'), 'export default {}');
  expect(JSON.parse(cli(root, modelHelper).output).code).toBe('CONFIG_NOT_UNIQUE');
  expect(cli(root, modelHelper, ['--config', 'e2e.config.ts']).code).toBe(0);
  expect(JSON.parse(cli(root, modelHelper, ['--config', 'e2e.config.mts']).output).code).toBe('MODEL_NOT_CONFIGURED');
}));
test('missing project packages never trigger Bun auto-install or write a package cache', async () => fixture(async root => {
  await writeFile(join(root, 'e2e.config.ts'), 'export default { agents: { default: { model: { doGenerate() {} } } } };');
  expect(cli(root, modelHelper).code).toBe(1);
  const { readdir } = await import('node:fs/promises');
  let cache: string[] = [];
  try { cache = await readdir(join(root, '.bun', 'install', 'cache')); } catch {}
  expect(cache).toEqual([]);
}));
test('SIGTERM aborts a pending model request and closes the browser without payload output', async () => fixture(async root => {
  await modelProject(root, 'hang');
  const child = spawn(process.execPath, [modelHelper], { cwd: root, env: environment(root), stdio: ['ignore', 'pipe', 'pipe'] });
  let stdout = '', stderr = '';
  child.stdout.on('data', value => { stdout += value; });
  child.stderr.on('data', value => { stderr += value; });
  const exited = once(child, 'exit');
  try {
    const start = Date.now();
    while (true) {
      try { if ((await readFile(join(root, 'events'), 'utf8')).includes('vision')) break; } catch {}
      if (Date.now() - start > 5_000) throw new Error('Fixture did not reach model request');
      await delay(20);
    }
    child.kill('SIGTERM');
    expect((await exited)[0]).toBe(1);
    expect(JSON.parse(stdout).code).toBe('MODEL_INTERRUPTED');
    expect(stderr).toBe('');
    expect(stdout).not.toContain(fixtureSecret);
    expect(await readFile(join(root, 'events'), 'utf8')).toContain('closed');
  } finally { child.kill('SIGKILL'); }
}));

test('artifact audit counts plain and ZIP leaks without printing names or contents', async () => fixture(async root => {
  await mkdir(join(root, '.e2e'));
  await writeFile(join(root, '.e2e', 'clean.txt'), 'synthetic evidence');
  expect(JSON.parse(cli(root, auditHelper).output)).toEqual({ status: 'passed', scanned: 1, leaks: 0, unreadable: 0 });
  await writeFile(join(root, 'trace.txt'), 'https://fixture-private.example/compat/chat/completions');
  const zipped = spawnSync('/usr/bin/zip', ['-q', join(root, '.e2e', 'trace.zip'), 'trace.txt'], { cwd: root, env: environment(root) });
  expect(zipped.status).toBe(0);
  await writeFile(join(root, '.e2e', 'key.txt'), fixtureSecret);
  await writeFile(join(root, '.e2e', 'jwt.txt'), 'eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjE5OTk5OTk5OTl9.signature');
  await writeFile(join(root, '.e2e', 'age.txt'), 'AGE-SECRET-KEY-1SYNTHETIC');
  const result = cli(root, auditHelper, [], { FIXTURE_KEY: fixtureSecret, CF_AI_ACCESS_URL: 'https://fixture-private.example/other' });
  expect(result.code).toBe(1);
  expect(JSON.parse(result.output)).toEqual({ status: 'failed', scanned: 5, leaks: 4, unreadable: 0 });
  expect(result.output).not.toContain('fixture-private');
}));
test('artifact names, custom env, invalid ZIPs and symlinks fail closed', async () => {
  await fixture(async root => {
    await mkdir(join(root, '.e2e'));
    await writeFile(join(root, '.e2e', fixtureSecret), 'ok');
    expect(JSON.parse(cli(root, auditHelper, ['--secret-env', 'CUSTOM'], { CUSTOM: fixtureSecret }).output).leaks).toBe(1);
    expect(JSON.parse(cli(root, auditHelper, ['--secret-env', 'MISSING']).output).unreadable).toBe(1);
    await writeFile(join(root, '.e2e', 'broken.zip'), 'not a zip');
    expect(JSON.parse(cli(root, auditHelper).output).unreadable).toBe(1);
  });
  await fixture(async root => {
    await mkdir(join(root, '.e2e'));
    await symlink('/does-not-exist', join(root, '.e2e', 'link'));
    expect(JSON.parse(cli(root, auditHelper).output).unreadable).toBe(1);
    await symlink(join(root, '.e2e'), join(root, 'linked'));
    expect(JSON.parse(cli(root, auditHelper, ['--dir', 'linked']).output).unreadable).toBe(1);
    expect(JSON.parse(cli(root, auditHelper, ['--dir', 'missing']).output).unreadable).toBe(1);
  });
});
