#!/usr/bin/env python3
"""chezmoi の公開 CLI で、共通設定と PC 固有状態の分離を検証する。"""
import json
from pathlib import Path
import subprocess
import tempfile
import tomllib

REPO = Path(__file__).resolve().parents[1]

with tempfile.TemporaryDirectory(prefix="agent-config-") as temp:
    root = Path(temp)
    home = root / "another user's home"
    home.mkdir()
    targets = [home / ".codex/config.toml", home / ".pi/agent/sandbox.json",
               home / ".config/devin/config.json", home / ".pi/agent/settings.json"]
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
    cli = ["chezmoi", "--config", "/dev/null", "--config-format", "toml", "--source", str(REPO),
           "--destination", str(home), "--persistent-state", str(root / "state.db"),
           "--cache", str(root / "cache"), "--mode", "symlink", "--force",
           "--override-data", json.dumps({"chezmoi": {"homeDir": str(home)}})]

    def apply(*paths, success=True):
        result = subprocess.run(cli + ["apply", "--exclude", "scripts", *map(str, paths or targets)],
                                capture_output=True, text=True)
        assert (result.returncode == 0) == success, result.stderr
        return result

    apply()
    codex = tomllib.loads(targets[0].read_text())
    pi = json.loads(targets[1].read_text())
    devin = json.loads(targets[2].read_text())
    settings = json.loads(targets[3].read_text())
    pi_base = json.loads((REPO / "home/.chezmoitemplates/pi-settings-base.json").read_text())
    assert codex["model"] == "gpt-6.1-sol"
    assert not codex.get("projects") and not codex.get("hooks", {}).get("state")
    assert "perPath" not in codex["desktop"]["open-in-target-preferences"]
    assert "model_availability_nux" not in codex["tui"]
    assert pi["enabled"] is False and not pi["filesystem"].get("allowRead")
    assert devin["devin"]["org_id"] == "org_N6dZEjgnb5biUvFw"
    assert settings["defaultProvider"] == "opencode-go"
    assert settings["enabledModels"] == pi_base["enabledModels"]
    assert all(not target.is_symlink() for target in targets)
    assert all(target.stat().st_mode & 0o777 == 0o600 for target in targets)

    fresh = [target.read_bytes() for target in targets]
    apply()
    assert fresh == [target.read_bytes() for target in targets]

    project = str(home / "private-project")
    targets[0].write_text('model = "local-choice"\n' +
        '[sandbox_workspace_write]\nwritable_roots = ["/local-extra"]\n' +
        '[projects.' + json.dumps(project) + ']\ntrust_level = "trusted"\n' +
        '[hooks.state.fixture]\ntrusted_hash = "sha256:fixture"\n' +
        '[marketplaces.local-fixture]\nsource_type = "local"\nsource = "/local/plugins"\n' +
        '[desktop.open-in-target-preferences.perPath]\n' + json.dumps(project) + ' = "local-editor"\n' +
        '[tui.model_availability_nux]\nfixture = 3\n' +
        '[shell_environment_policy.set]\nNODE_REPL_TRUSTED_BROWSER_CLIENT_SHA256S = "local-hash"\n')
    pi["filesystem"]["allowRead"] = [str(home / "one-session/overview.html")]
    pi["filesystem"]["allowWrite"].append(str(home / "local-output"))
    pi["network"]["allowedDomains"].append("local-fixture.invalid")
    pi["network"]["allowUnixSockets"].append(str(home / "local-socket"))
    pi["localFixture"] = {"keep": True}
    targets[1].write_text(json.dumps(pi))
    devin["devin"]["org_id"] = "org_local_fixture"
    targets[2].write_text(json.dumps(devin))
    settings["defaultModel"] = "local-model"
    settings["theme"] = "dark"
    settings["lastChangelogVersion"] = "9.9.9"
    settings["enabledModels"] = ["local-only/model"]
    settings["localFixture"] = {"keep": True}
    targets[3].write_text(json.dumps(settings))
    apply()
    codex = tomllib.loads(targets[0].read_text())
    after = json.loads(targets[1].read_text())
    assert codex["model"] == "gpt-6.1-sol"
    assert codex["projects"][project]["trust_level"] == "trusted"
    assert codex["sandbox_workspace_write"]["writable_roots"] == ["/local-extra", "/tmp"]
    assert codex["hooks"]["state"]["fixture"]["trusted_hash"] == "sha256:fixture"
    assert codex["marketplaces"]["local-fixture"]["source"] == "/local/plugins"
    assert codex["desktop"]["open-in-target-preferences"]["perPath"][project] == "local-editor"
    assert codex["tui"]["model_availability_nux"]["fixture"] == 3
    assert codex["shell_environment_policy"]["set"]["NODE_REPL_TRUSTED_BROWSER_CLIENT_SHA256S"] == "local-hash"
    assert after["filesystem"]["allowRead"] == pi["filesystem"]["allowRead"]
    assert after["filesystem"]["allowWrite"] == pi["filesystem"]["allowWrite"]
    assert after["network"]["allowedDomains"] == pi["network"]["allowedDomains"]
    assert after["network"]["allowUnixSockets"] == pi["network"]["allowUnixSockets"]
    assert after["localFixture"] == {"keep": True}
    assert json.loads(targets[2].read_text())["devin"]["org_id"] == "org_local_fixture"
    after_settings = json.loads(targets[3].read_text())
    assert after_settings["defaultModel"] == "local-model"
    assert after_settings["theme"] == "dark"
    assert after_settings["lastChangelogVersion"] == "9.9.9"
    assert after_settings["enabledModels"] == pi_base["enabledModels"]
    assert after_settings["packages"] == pi_base["packages"]
    assert after_settings["localFixture"] == {"keep": True}
    saved = [target.read_bytes() for target in targets]
    apply()
    assert saved == [target.read_bytes() for target in targets]

    hook = home / ".orca/agent-hooks/devin-hook.sh"
    commands = []
    for groups in json.loads(targets[2].read_text())["hooks"].values():
        for group in groups:
            for entry in group["hooks"]:
                command = entry.get("command", "")
                if "devin-hook.sh" in command:
                    commands.append(command)
    assert len(commands) == 8
    for command in commands:
        result = subprocess.run(["sh", "-c", command], input="{}", text=True, capture_output=True)
        assert result.returncode == 0
    hook.parent.mkdir(parents=True)
    hook.write_text('#!/bin/sh\nprintf "portable-hook"\n')
    hook.chmod(0o700)
    for command in commands:
        result = subprocess.run(["sh", "-c", command], input="{}", text=True, capture_output=True)
        assert result.returncode == 0 and result.stdout == "portable-hook", result

    for target, broken in [(targets[0], 'model = [\n'), (targets[1], '{broken'), (targets[2], '{broken'),
                           (targets[3], '{broken')]:
        target.write_text(broken)
        apply(target, success=False)
        assert target.read_text() == broken

print("OK: fresh install, local state preservation, reapply, private files, portable hooks and malformed-file protection")
