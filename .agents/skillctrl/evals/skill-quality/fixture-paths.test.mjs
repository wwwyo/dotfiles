import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, rmSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { rejection } from './fixture-paths.mjs';

const root = mkdtempSync(join(tmpdir(), 'skill-eval-'));
try {
  const fixture = join(root, 'fixture');
  const skills = join(root, 'skills');
  mkdirSync(fixture); mkdirSync(skills);
  symlinkSync(skills, join(fixture, 'escape'));
  const check = (tool, path) => rejection(tool, path, fixture, skills);
  assert.equal(check('write', 'nested/new.md'), null);
  assert.equal(check('read', join(skills, 'SKILL.md')), null);
  for (const path of ['../outside', fixture + '-other/file', '~/outside', '@../outside', 'file:///outside']) {
    assert.ok(check('read', path), path);
    assert.ok(check('write', path), path);
  }
  assert.ok(check('write', 'escape/new.md'));
  assert.ok(check('write', join(skills, 'SKILL.md')));
  assert.ok(check('bash', '.'));
} finally {
  rmSync(root, { recursive: true, force: true });
}
console.log('Fixture path boundaries passed.');
