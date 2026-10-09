import { readdir, lstat, open } from 'node:fs/promises';
import { constants } from 'node:fs';
import { join, resolve, parse } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const args = process.argv.slice(2);
if (args.length === 1 && args[0] === '--help') {
  console.log('Usage: mise exec -- bun <skill>/tools/audit-artifacts.ts [--dir path] [--secret-env NAME ...]\nRun from the target project. Default directory: .e2e.\nScans files, names and ZIP contents for environment secrets/URL hosts, age private keys and JWTs.\nSecret env names match KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, URL or ENDPOINT; --secret-env adds a required value.\nOutputs counts only. Symlinks, unreadable/invalid ZIPs and files over 128 MiB fail closed.\nImage/video pixel inspection is separate. Exit 0: passed; 1: failed; 2: invalid arguments.');
  process.exit(0);
}
let directory = '.e2e';
const extraEnv: string[] = [];
let hasDirectory = false;
for (let i = 0; i < args.length; i += 2) {
  const option = args[i];
  const value = args[i + 1];
  if (!value || value.startsWith('-') || (option !== '--dir' && option !== '--secret-env')
    || (option === '--dir' && hasDirectory) || (option === '--secret-env' && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(value))) {
    console.log(JSON.stringify({ status: 'failed', code: 'INVALID_ARGUMENT' })); process.exit(2);
  }
  if (option === '--dir') { directory = value; hasDirectory = true; }
  else extraEnv.push(value);
}
const execFileAsync = promisify(execFile);
const limit = 128 * 1024 * 1024;
const controller = new AbortController();
const interrupt = () => controller.abort();
process.on('SIGINT', interrupt);
process.on('SIGTERM', interrupt);
const deadline = setTimeout(() => controller.abort(), 60_000);
let scanned = 0;
let leaks = 0;
let unreadable = 0;

try {
  const forbidden: Buffer[] = [];
  for (const name of extraEnv) if (!process.env[name]) throw new Error();
  for (const [name, value] of Object.entries(process.env)) {
    if (!value || (!extraEnv.includes(name) && !/(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|URL|ENDPOINT)/i.test(name))) continue;
    forbidden.push(Buffer.from(value));
    try { const host = new URL(value).host; if (host) forbidden.push(Buffer.from(host)); } catch { /* Non-URL secret. */ }
  }
  function containsSecret(content: Buffer) {
    return forbidden.some((value) => content.includes(value))
      || /eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+|AGE-SECRET-KEY-1[0-9A-Z]+|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----/.test(content.toString('latin1'));
  }
  const root = resolve(directory);
  let ancestor = parse(root).root;
  for (const part of root.slice(ancestor.length).split(/[\\/]/).filter(Boolean)) {
    ancestor = join(ancestor, part);
    if ((await lstat(ancestor)).isSymbolicLink()) throw new Error();
  }
  async function scan(path: string): Promise<void> {
    controller.signal.throwIfAborted();
    const stat = await lstat(path);
    if (stat.isSymbolicLink()) throw new Error();
    if (stat.isDirectory()) {
      if (containsSecret(Buffer.from(path.slice(root.length)))) leaks++;
      for (const entry of await readdir(path)) await scan(join(path, entry));
      return;
    }
    if (!stat.isFile() || stat.size > limit) throw new Error();
    const file = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
    let content: Buffer;
    try {
      const opened = await file.stat();
      if (!opened.isFile() || opened.size > limit) throw new Error();
      content = await file.readFile();
    } finally { await file.close(); }
    let leaked = containsSecret(content) || containsSecret(Buffer.from(path.slice(root.length)));
    if (/\.zip$/i.test(path) || content.subarray(0, 2).equals(Buffer.from('PK'))) {
      const options = { env: { PATH: process.env.PATH }, timeout: 10_000, maxBuffer: limit, encoding: 'buffer' as const, signal: controller.signal };
      // Name entries and compressed bytes alone do not cover Playwright trace bodies.
      const names = (await execFileAsync('unzip', ['-Z1', path], options)).stdout;
      const expanded = (await execFileAsync('unzip', ['-p', path], options)).stdout;
      leaked ||= containsSecret(names) || containsSecret(expanded);
    }
    scanned++;
    if (leaked) leaks++;
  }
  if (!(await lstat(root)).isDirectory()) throw new Error();
  await scan(root);
} catch { unreadable++; }
finally {
  clearTimeout(deadline);
  process.off('SIGINT', interrupt);
  process.off('SIGTERM', interrupt);
}
console.log(JSON.stringify({ status: leaks || unreadable ? 'failed' : 'passed', scanned, leaks, unreadable }));
process.exitCode = leaks || unreadable ? 1 : 0;
