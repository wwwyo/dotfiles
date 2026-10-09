import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const cli = fileURLToPath(new URL("./am.mjs", import.meta.url));
const draft = "---\ntitle: 制作の流れ\nlang: ja\n---\n## 流れ\n```flow LR\n原稿 -> 図解: 描画\n```\n> 原稿から図解を作ります。\n";

function runCase(check) {
  const home = mkdtempSync(join(tmpdir(), "learn-fish-test-"));
  const input = join(home, "draft.md");
  const output = join(home, "video.html");
  writeFileSync(input, draft);
  const env = { ...process.env, AM_HOME: home, AM_NO_UPDATE_CHECK: "1" };
  delete env.FISH_API_KEY;
  delete env.FISH_VOICE_ID;
  delete env.FISH_TTS_READINGS_FILE;
  const run = (args, extra = {}) => spawnSync(process.execPath, [cli, ...args], {
    env: { ...env, ...extra }, encoding: "utf8", timeout: 10000
  });
  try {
    check({ run, input, output });
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
}

test("default, fish and auto stop without a Fish key even when ElevenLabs is configured", () => {
  for (const flags of [[], ["--voice", "fish"], ["--voice", "auto"]]) {
    runCase(({ run, input, output }) => {
      const result = run(["video", input, ...flags, "--no-open", "--out", output], {
        ELEVENLABS_API_KEY: "must-not-be-used"
      });
      assert.equal(result.status, 1, result.stderr);
      assert.match(result.stderr, /FISH_API_KEY/);
      assert.equal(existsSync(output), false);
    });
  }
});

test("an invalid Fish voice ID is rejected before sending a request", () => {
  runCase(({ run, input, output }) => {
    const result = run(["video", input, "--voice", "fish", "--no-open", "--out", output], {
      FISH_API_KEY: "must-not-be-used", FISH_VOICE_ID: "invalid"
    });
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /FISH_VOICE_ID must be/);
    assert.equal(existsSync(output), false);
  });
});

test("explicit off makes a silent player without a Fish key", () => {
  runCase(({ run, input, output }) => {
    const result = run(["video", input, "--voice", "off", "--no-open", "--out", output]);
    assert.equal(result.status, 0, result.stderr);
    const html = readFileSync(output, "utf8");
    assert.ok(html.includes('id="amv-data"'));
    assert.equal(html.includes('id="amv-audio"'), false);
  });
});

test("configuration and help expose Fish as the default", () => {
  runCase(({ run }) => {
    const config = run(["config"]);
    assert.equal(config.status, 0, config.stderr);
    assert.match(config.stdout, /voice\s+fish\s/);
    const help = run(["help", "video"]);
    assert.equal(help.status, 0, help.stderr);
    assert.match(help.stdout, /--voice fish \(default: Fish Audio/);
    assert.match(help.stdout, /s2\.1-pro-free/);
    assert.match(help.stdout, /Shiori, a female narrator \(5da7f24e9e274f91b2b677669c818ce9\)/);
  });
});

test("invalid or incomplete spoken-text mappings stop before contacting Fish", () => {
  for (const content of ["not JSON", "[]", '{"line": ""}', "{}"] ) {
    runCase(({ run, input, output }) => {
      const readings = `${output}.readings.json`;
      writeFileSync(readings, content);
      const result = run(["video", input, "--voice", "fish", "--no-open", "--out", output], {
        FISH_API_KEY: "must-not-be-used", FISH_TTS_READINGS_FILE: readings
      });
      assert.equal(result.status, 1, result.stderr);
      assert.match(result.stderr, /readings|FISH_TTS_READINGS_FILE/);
      assert.equal(existsSync(output), false);
    });
  }
});

test("a map missing a later narration line fails before sending the first line", () => {
  runCase(({ run, input, output }) => {
    writeFileSync(input, draft + "> 二つめの説明です。\n");
    const readings = `${output}.readings.json`;
    writeFileSync(readings, JSON.stringify({ "原稿から図解を作ります。": "げんこうからずかいをつくります。" }));
    const result = run(["video", input, "--voice", "fish", "--no-open", "--out", output], {
      FISH_API_KEY: "must-not-be-used", FISH_TTS_READINGS_FILE: readings
    });
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, /A narration line has no spoken text/);
    assert.equal(existsSync(output), false);
  });
});
