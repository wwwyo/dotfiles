import { createRequire } from 'node:module';
import { access } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawn } from 'node:child_process';
import { once } from 'node:events';

const args = process.argv.slice(2);
if (args.length === 1 && args[0] === '--help') {
  console.log('Usage: mise exec -- bun <skill>/tools/check-model.ts [--config path]\nRun from the target project. Uses its installed ai/playwright and agents.default.model.\nDefault config: e2e.config.ts or e2e.config.mts (exactly one). Performs 3 synthetic image requests.\nNo SDK payloads are printed. Exit 0: passed; 1: failed; 2: invalid arguments.');
  process.exit(0);
}
if (args.length && (args.length !== 2 || args[0] !== '--config' || !args[1] || args[1].startsWith('-'))) {
  console.log(JSON.stringify({ status: 'failed', code: 'INVALID_ARGUMENT' }));
  process.exit(2);
}

process.env.E2E_TELEMETRY_DISABLED = '1';
// Bun otherwise fetches packages when node_modules is absent, including during config import.
if (!process.execArgv.includes('--no-install')) {
  const child = spawn(process.execPath, ['--no-install', import.meta.path, ...args], { stdio: 'inherit' });
  const forwardInt = () => { child.kill('SIGINT'); };
  const forwardTerm = () => { child.kill('SIGTERM'); };
  process.on('SIGINT', forwardInt);
  process.on('SIGTERM', forwardTerm);
  try {
    const [exitCode] = await once(child, 'exit');
    process.exitCode = exitCode ?? 1;
  } catch {
    console.log(JSON.stringify({ status: 'failed', stage: 'configuration', code: 'RUNTIME_FAILED' }));
    process.exitCode = 1;
  } finally {
    process.off('SIGINT', forwardInt);
    process.off('SIGTERM', forwardTerm);
  }
  process.exit(process.exitCode);
}
const write = process.stdout.write.bind(process.stdout);
// Config imports and SDK warnings may contain credentials; only our fixed verdict crosses stdout.
for (const method of ['log', 'info', 'warn', 'error', 'debug', 'trace', 'dir', 'table'] as const) console[method] = () => {};
let stage = 'configuration';
let code = 'MODEL_CAPABILITY_FAILED';
let reported = false;
function report(value: object, exitCode: number) {
  if (reported) return;
  reported = true;
  write(`${JSON.stringify(value)}\n`);
  process.exitCode = exitCode;
}
const controller = new AbortController();
function interrupt() { controller.abort(); }
process.on('SIGINT', interrupt);
process.on('SIGTERM', interrupt);
let browser: { close(): Promise<void> } | undefined;
// Also bounds config imports and providers that ignore abortSignal.
const deadline = setTimeout(() => {
  controller.abort();
  report({ status: 'failed', stage, code: 'MODEL_TIMEOUT' }, 1);
  void browser?.close().catch(() => {});
  setTimeout(() => process.exit(1), 5_000);
}, 210_000);
const interrupted = new Promise<never>((_, reject) => {
  controller.signal.addEventListener('abort', () => reject(new Error('interrupted')), { once: true });
});

async function check() {
  let configPath = args[1];
  if (!configPath) {
    const candidates = [];
    for (const name of ['e2e.config.ts', 'e2e.config.mts']) {
      try { await access(resolve(name)); candidates.push(name); } catch { /* Missing candidate. */ }
    }
    if (candidates.length !== 1) { code = 'CONFIG_NOT_UNIQUE'; throw new Error(); }
    configPath = candidates[0]!;
  }
  const config = (await import(pathToFileURL(resolve(configPath)).href)).default;
  const model = config?.agents?.default?.model;
  if (!model || typeof model === 'string' || typeof model.doGenerate !== 'function') {
    code = 'MODEL_NOT_CONFIGURED'; throw new Error();
  }
  const projectRequire = createRequire(resolve('package.json'));
  const { generateText, Output, jsonSchema, tool } = await import(pathToFileURL(projectRequire.resolve('ai')).href);
  const { chromium } = await import(pathToFileURL(projectRequire.resolve('playwright')).href);
  controller.signal.throwIfAborted();
  stage = 'browser';
  const launched = await chromium.launch({ timeout: 30_000, env: { PATH: process.env.PATH ?? '', HOME: process.env.HOME ?? '' } });
  browser = launched;
  controller.signal.throwIfAborted();
  const page = await launched.newPage({ viewport: { width: 200, height: 100 } });
  page.setDefaultTimeout(10_000);
  const schema = jsonSchema({ type: 'object', properties: { color: { type: 'string', enum: ['red', 'blue', 'green'] } }, required: ['color'], additionalProperties: false });
  let image: Buffer | undefined;
  const requestOptions = () => ({ model, maxRetries: 0, maxOutputTokens: 512,
    abortSignal: AbortSignal.any([controller.signal, AbortSignal.timeout(60_000)]),
    experimental_telemetry: { isEnabled: false },
  });
  for (const color of ['red', 'blue']) {
    controller.signal.throwIfAborted();
    stage = `vision-${color}`;
    await page.setContent(`<body style="margin:0;background:${color}"></body>`);
    image = await page.screenshot({ timeout: 10_000 });
    const result = await generateText({ ...requestOptions(),
      messages: [{ role: 'user', content: [{ type: 'text', text: 'What color fills this image? Return the color in JSON.' }, { type: 'file', data: image, mediaType: 'image/png' }] }],
      output: Output.object({ schema }),
    });
    if (result.output?.color !== color) { code = 'MODEL_VISION_INVALID'; throw new Error(); }
  }
  controller.signal.throwIfAborted();
  stage = 'tool-call';
  const result = await generateText({ ...requestOptions(),
    messages: [{ role: 'user', content: [{ type: 'text', text: 'Call record_color with the color filling this image.' }, { type: 'file', data: image!, mediaType: 'image/png' }] }],
    tools: { record_color: tool({ description: 'Record the image color', inputSchema: schema }) },
    toolChoice: { type: 'tool', toolName: 'record_color' },
  });
  if (result.toolCalls.length !== 1 || result.toolCalls[0]?.toolName !== 'record_color' || result.toolCalls[0].input?.color !== 'blue') {
    code = 'MODEL_TOOLS_INVALID'; throw new Error();
  }
}

let passed = false;
try {
  await Promise.race([check(), interrupted]);
  passed = true;
} catch {
  report({ status: 'failed', stage, code: controller.signal.aborted ? 'MODEL_INTERRUPTED' : code }, 1);
} finally {
  controller.abort();
  const cleanupDeadline = setTimeout(() => {
    report({ status: 'failed', stage: 'cleanup', code: 'BROWSER_CLEANUP_FAILED' }, 1);
    process.exit(1);
  }, 5_000);
  try { await browser?.close(); } catch {
    passed = false;
    report({ status: 'failed', stage: 'cleanup', code: 'BROWSER_CLEANUP_FAILED' }, 1);
  }
  clearTimeout(cleanupDeadline);
  clearTimeout(deadline);
  process.off('SIGINT', interrupt);
  process.off('SIGTERM', interrupt);
  // An interrupted import/provider may still be running despite the cancelled race.
  if (process.exitCode) process.exit(1);
  if (passed) report({ status: 'passed', checks: ['vision-red', 'vision-blue', 'json-schema', 'tool-call'], requests: 3 }, 0);
}
