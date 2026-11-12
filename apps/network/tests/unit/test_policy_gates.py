"""Startup scan of UNIFI_POLICY_* names against the gates this server's manifest registers."""

import os
import re
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clear_policy_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("UNIFI_POLICY_"):
            monkeypatch.delenv(key)


_PERMISSIONS_DOC = Path(__file__).resolve().parents[2] / "docs" / "permissions.md"
_ROW = re.compile(r"^\| `(?P<category>[a-z_]+)` \| (?P<create>[^|]+) \| (?P<update>[^|]+) \| (?P<delete>[^|]+) \|$")


def _documented_gates() -> set[tuple[str, str]]:
    gates = set()
    for line in _PERMISSIONS_DOC.read_text().splitlines():
        row = _ROW.match(line.strip())
        if not row:
            continue
        for action in ("create", "update", "delete"):
            cell = row.group(action).strip()
            if cell != "—":
                expected = f"`UNIFI_POLICY_NETWORK_{row.group('category').upper()}_{action.upper()}`"
                assert cell == expected, f"{row.group('category')} {action}: {cell} should be {expected}"
                gates.add((row.group("category"), action))
    return gates
