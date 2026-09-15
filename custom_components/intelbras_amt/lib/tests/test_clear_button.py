"""Manual clear gates and readback; no connection to real hardware."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.intelbras_amt.lib.protocol.commands import PartialCentralStatus
from custom_components.intelbras_amt.lib.protocol.responses import Response


@pytest.fixture
def button(monkeypatch):
    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @property
        def available(self):
            return self.coordinator.last_update_success

    for name, attrs in {
        "homeassistant.components.button": {"ButtonEntity": type("ButtonEntity", (), {})},
        "homeassistant.exceptions": {"HomeAssistantError": type("HomeAssistantError", (Exception,), {})},
        "homeassistant.helpers.update_coordinator": {"CoordinatorEntity": CoordinatorEntity},
    }.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("custom_components.intelbras_amt._button_test", Path(__file__).parents[2] / "button.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = bytearray(43)
    raw[18] = 0x1E
    status = PartialCentralStatus.parse(raw)
    status.triggered = True
    status.zones.violated_zones = {26}
    coordinator = SimpleNamespace(data=status, connection_id="current", last_update_success=True,
                                  async_refresh=AsyncMock(), server=AsyncMock(),
                                  programming_lock=asyncio.Lock(), programming_host=lambda: "192.0.2.55")
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False
    factory = lambda *args: session
    monkeypatch.setattr(module, "ProgrammingSession", factory)
    entity = module.AMTClearAlarmButton(coordinator, SimpleNamespace(entry_id="test", data={"computer_password":"123456"}))
    entity._test_session = session
    return entity



@pytest.mark.parametrize("blocked", ["armed", "partition", "siren", "unavailable", "disconnected", "model", "replaced", "credential"])
async def test_clear_requires_fresh_disarmed_supported_connection(button, blocked):
    coordinator = button.coordinator

    async def refresh():
        if blocked == "armed": coordinator.data.armed = True
        if blocked == "partition": coordinator.data.partitions.partition_b_armed = True
        if blocked == "siren": coordinator.data.siren_on = True
        if blocked == "unavailable": coordinator.last_update_success = False
        if blocked == "disconnected": coordinator.connection_id = None
        if blocked == "model": coordinator.data.model = 0xFF
        if blocked == "replaced": coordinator.connection_id = "new"
        if blocked == "credential": button._entry.data.clear()
    coordinator.async_refresh.side_effect = refresh
    with pytest.raises(Exception, match="Limpeza exige"):
        await button.async_press()
    button._test_session.__aenter__.assert_not_awaited()
    assert not button._pressing


@pytest.mark.parametrize("model", [0x1E, 0x34, 0x36, 0x41])
async def test_clear_success_comes_from_readback(button, model, caplog):
    caplog.set_level("INFO")
    coordinator = button.coordinator
    coordinator.data.model = model

    async def refresh():
        if button._test_session.clear_alarm_memory.await_count:
            coordinator.data.triggered = False
            coordinator.data.zones.violated_zones.clear()
    coordinator.async_refresh.side_effect = refresh
    await button.async_press()
    assert coordinator.async_refresh.await_count == 2
    assert button._test_session.clear_alarm_memory.await_count == 1
    assert "Limpeza da memória de disparos confirmada" in caplog.text


@pytest.mark.parametrize("failure", ["memory_retained", "timeout", "connection_lost", "wrong_ack", "short_reply", "readback_unavailable", "reconnected"])
async def test_clear_failure_never_fakes_success_or_retries(button, failure, caplog):
    caplog.set_level("INFO")
    coordinator = button.coordinator
    if failure == "timeout": button._test_session.clear_alarm_memory.side_effect = TimeoutError
    if failure == "connection_lost": button._test_session.clear_alarm_memory.side_effect = ConnectionError("Disconnected")
    if failure == "wrong_ack": button._test_session.clear_alarm_memory.side_effect = ValueError("A central não confirmou a limpeza")
    if failure == "short_reply": button._test_session.clear_alarm_memory.side_effect = ValueError("A central não confirmou a operação de programação")

    async def refresh():
        if button._test_session.clear_alarm_memory.await_count:
            if failure == "readback_unavailable": coordinator.last_update_success = False
            if failure == "reconnected": coordinator.connection_id = "new"
    coordinator.async_refresh.side_effect = refresh
    with pytest.raises(Exception) as error:
        await button.async_press()
    if failure == "short_reply":
        assert "não confirmou" in str(error.value)
        assert "Timeout" not in str(error.value)
    assert button._test_session.clear_alarm_memory.await_count == 1
    assert coordinator.data.zones.violated_zones == {26}
    assert "Limpeza da memória de disparos confirmada" not in caplog.text
    assert not button._pressing


async def test_rejected_computer_password_never_clears(button):
    button._test_session.__aenter__.side_effect = PermissionError()
    with pytest.raises(Exception, match="senha do computador"):
        await button.async_press()
    button._test_session.clear_alarm_memory.assert_not_awaited()
    assert not button._pressing
