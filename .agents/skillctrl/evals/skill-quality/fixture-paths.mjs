import { existsSync, realpathSync } from 'node:fs';
import { dirname, relative, resolve, sep } from 'node:path';

function canonical(path) {
  if (existsSync(path)) return realpathSync(path);
  return resolve(canonical(dirname(path)), relative(dirname(path), path));
}

function within(path, root) {
  return path === root || path.startsWith(root + sep);
}

export function rejection(tool, inputPath, cwd, skillRoot) {
  // Pi expands these aliases before filesystem access. Requiring ordinary
  // paths avoids approving a different target from the one its tools open.
  if (/^(~|@|file:)/.test(inputPath)) return 'Use an ordinary absolute or relative fixture path.';
  const path = canonical(resolve(cwd, inputPath));
  const fixture = canonical(cwd);
  const skills = canonical(skillRoot);
  if (tool === 'write' || tool === 'edit') {
    if (!within(path, fixture)) return 'Eval writes are limited to the fixture.';
  } else if (['read', 'grep', 'find', 'ls'].includes(tool)) {
    if (!within(path, fixture) && !within(path, skills)) {
      return 'Eval reads are limited to the fixture and tested skill snapshot.';
    }
  } else {
    return 'This fixture evaluation only enables file tools.';
  }
  return null;
}
