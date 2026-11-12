"""This build of the Network server is read-only by construction.

Mutating tools are never registered, the lazy loader never advertises them, and
the policy gate denies every non-read action whatever the environment says.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

MANIFEST = Path(__file__).resolve().parents[2] / "src" / "unifi_network_mcp" / "tools_manifest.json"
META_DISPATCHERS = {"unifi_execute", "unifi_batch", "unifi_load_tools"}


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_lists_only_read_tools():
    tools = _manifest()["tools"]
    assert tools
    assert [t["name"] for t in tools if t.get("permission_action") not in (None, "read")] == []
    not_read_only = {t["name"] for t in tools if not t.get("annotations", {}).get("readOnlyHint")}
    assert not_read_only <= META_DISPATCHERS


def test_module_map_only_loads_manifest_tools():
    from unifi_network_mcp.categories import TOOL_MODULE_MAP

    names = {t["name"] for t in _manifest()["tools"]}
    assert set(TOOL_MODULE_MAP) <= names
    assert "unifi_update_wlan" not in TOOL_MODULE_MAP
    assert "unifi_reboot_device" not in TOOL_MODULE_MAP


@pytest.mark.parametrize("action", ["create", "update", "delete", "CREATE", "", None])
def test_gate_denies_non_read_whatever_the_environment_says(monkeypatch, action):
    from unifi_network_mcp.categories import NETWORK_CATEGORY_MAP
    from unifi_network_mcp.main import ReadOnlyPolicyGateChecker

    for var in ("UNIFI_POLICY_CREATE", "UNIFI_POLICY_UPDATE", "UNIFI_POLICY_DELETE"):
        monkeypatch.setenv(var, "true")
    monkeypatch.setenv("UNIFI_POLICY_NETWORK_WLANS_UPDATE", "true")
    monkeypatch.setenv("UNIFI_READ_ONLY", "false")
    monkeypatch.setenv("UNIFI_NETWORK_READ_ONLY", "false")

    checker = ReadOnlyPolicyGateChecker(server_prefix="network", category_map=NETWORK_CATEGORY_MAP)
    assert checker.check("wlan", action) is False
    assert "read-only" in checker.denial_message("wlan", action)


def test_decorator_drops_mutating_tools_and_keeps_reads():
    from unifi_network_mcp.main import read_only_tool_decorator

    registered = []

    def fake_permissioned_tool(*args, **kwargs):
        registered.append(kwargs.get("name"))
        return lambda func: func

    tool = read_only_tool_decorator(fake_permissioned_tool)
    tool(name="unifi_delete_thing", permission_category="thing", permission_action="delete")(lambda: None)
    tool(name="unifi_update_thing", permission_category="thing", permission_action="update")(lambda: None)
    tool(name="unifi_list_things", annotations={"readOnlyHint": True})(lambda: None)
    tool(name="unifi_read_thing", permission_category="thing", permission_action="read")(lambda: None)

    assert registered == ["unifi_list_things", "unifi_read_thing"]


_EAGER_PROBE = """
import asyncio
import unifi_network_mcp.main as m
from unifi_mcp_shared.tool_loader import auto_load_tools

auto_load_tools(base_package="unifi_network_mcp.tools")
names = {tool.name for tool in asyncio.run(m.server.list_tools())}
assert "unifi_list_wlans" in names, sorted(names)[:20]
blocked = sorted(n for n in names if n.split("_")[1] in {
    "create", "update", "delete", "remove", "block", "unblock", "reboot", "restart", "upgrade", "adopt",
    "forget", "kick", "authorize", "unauthorize", "archive", "toggle", "set", "trigger", "run", "locate",
    "power", "rename", "restore", "start", "revoke", "force", "cycle", "reorder", "provision",
})
assert blocked == [], blocked
print("read-only-eager-ok", len(names))
"""


def test_eager_registration_exposes_no_mutating_tool(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("UNIFI_")}
    env.update(
        {
            "UNIFI_TOOL_REGISTRATION_MODE": "eager",
            "UNIFI_POLICY_CREATE": "true",
            "UNIFI_POLICY_UPDATE": "true",
            "UNIFI_POLICY_DELETE": "true",
            "UNIFI_NETWORK_READ_ONLY": "false",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", _EAGER_PROBE],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    assert "read-only-eager-ok" in result.stdout


@pytest.mark.parametrize("value", ["false", "0", "no", "off"])
def test_redaction_cannot_be_turned_off(monkeypatch, value):
    from unifi_network_mcp.runtime import should_redact_sensitive_fields

    monkeypatch.setenv("UNIFI_REDACT_SENSITIVE_FIELDS", value)
    monkeypatch.setenv("UNIFI_NETWORK_REDACT_SENSITIVE_FIELDS", value)
    assert should_redact_sensitive_fields() is True


@pytest.mark.asyncio
async def test_every_registered_tool_result_is_redacted():
    import inspect

    from unifi_network_mcp.main import read_only_tool_decorator

    registered = {}

    def fake_permissioned_tool(*args, **kwargs):
        def register(func):
            registered[kwargs["name"]] = func
            return func

        return register

    tool = read_only_tool_decorator(fake_permissioned_tool)

    @tool(name="unifi_list_wlans_probe", annotations={"readOnlyHint": True})
    async def list_wlans(site: str = "default"):
        return {"success": True, "data": [{"name": "Home", "x_passphrase": "hunter2", "nested": {"psk": "abc"}}]}

    wrapped = registered["unifi_list_wlans_probe"]
    assert list(inspect.signature(wrapped).parameters) == ["site"]
    result = await wrapped()
    assert "hunter2" not in str(result) and "abc" not in str(result)
    assert result["data"][0]["name"] == "Home"
