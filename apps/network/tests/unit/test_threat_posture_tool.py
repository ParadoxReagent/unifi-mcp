"""Registration and Core delegation for the Network threat posture read tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from unifi_core.network.managers.system_manager import SystemManager
from unifi_core.network.models.threat_posture import threat_posture_from_controller


def test_tool_registered_with_read_only_session_metadata():
    from unifi_network_mcp.runtime import server
    from unifi_network_mcp.tools import system  # noqa: F401 - decorator registration

    tool = server._tool_manager._tools["unifi_get_threat_posture"]
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.open_world_hint is False


@pytest.mark.asyncio
async def test_tool_returns_only_projected_fields(monkeypatch):
    from unifi_network_mcp.tools import system

    manager = MagicMock()
    manager._connection.site = "default"
    manager.get_threat_posture = AsyncMock(return_value=threat_posture_from_controller("DAY", {"threats": 2}, []))
    monkeypatch.setattr(system, "system_manager", manager)
    result = await system.get_threat_posture()
    assert result["success"] is True
    assert result["site"] == "default"
    assert result["threat_posture"]["period"] == "DAY"
    assert result["threat_posture"]["threats"] == 2
    manager.get_threat_posture.assert_awaited_once_with(period="DAY")


@pytest.mark.asyncio
async def test_invalid_period_uses_core_validation_before_io(monkeypatch):
    from unifi_network_mcp.tools import system

    connection = MagicMock()
    connection.ensure_session_connected = AsyncMock()
    connection.request = AsyncMock()
    monkeypatch.setattr(system, "system_manager", SystemManager(connection))
    result = await system.get_threat_posture("YEAR")
    assert result == {
        "success": False,
        "error": "Failed to get threat posture: period must be HOUR, DAY, WEEK, or MONTH",
    }
    connection.ensure_session_connected.assert_not_awaited()
    connection.request.assert_not_awaited()


@pytest.mark.asyncio
async def test_controller_value_error_stays_private(monkeypatch, caplog):
    from unifi_network_mcp.tools import system

    connection = MagicMock()
    connection.ensure_session_connected = AsyncMock(return_value=True)
    connection.request = AsyncMock(side_effect=ValueError("controller-only-secret"))
    monkeypatch.setattr(system, "system_manager", SystemManager(connection))
    result = await system.get_threat_posture("DAY")
    assert result == {"success": False, "error": "Failed to get threat posture"}
    assert "controller-only-secret" not in caplog.text
