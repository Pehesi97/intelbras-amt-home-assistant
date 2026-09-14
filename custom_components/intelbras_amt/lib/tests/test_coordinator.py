"""Unit tests of model routing, independent of Home Assistant's scheduler."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import pytest

from custom_components.intelbras_amt.lib.const import CentralModel
from custom_components.intelbras_amt.lib.protocol.commands import CentralStatus, PartialCentralStatus
from custom_components.intelbras_amt.lib.protocol.isecnet import ISECNetFrame
from custom_components.intelbras_amt.lib.protocol.responses import Response


@pytest.fixture
def coordinator_class(monkeypatch):
    # Only the base class/types are substituted; exercise the actual coordinator
    # methods. This does not test HA setup, entities, or DataUpdateCoordinator.
    core = ModuleType("homeassistant.core")
    core.HomeAssistant = object
    update = ModuleType("homeassistant.helpers.update_coordinator")
    update.DataUpdateCoordinator = type("DataUpdateCoordinator", (), {
        "__class_getitem__": classmethod(lambda cls, item: cls),
    })
    update.UpdateFailed = type("UpdateFailed", (Exception,), {})
    monkeypatch.setitem(sys.modules, core.__name__, core)
    monkeypatch.setitem(sys.modules, update.__name__, update)
    path = Path(__file__).parents[2] / "coordinator.py"
    spec = importlib.util.spec_from_file_location("custom_components.intelbras_amt._routing_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AMTCoordinator


@pytest.mark.parametrize("model,size,name", [
    (0x1E, 43, "AMT 2018 E/EG"),
    (0x34, 43, "AMT 2018 E SMART"),
    (0x36, 43, "AMT 1000 Smart"),
    (0x41, 54, "AMT 4010"),
    (0xFF, 43, "0xFF"),
])
async def test_detect_then_poll_model(coordinator_class, caplog, model, size, name):
    coordinator = object.__new__(coordinator_class)
    coordinator.connection_id = "test"
    coordinator.password = "1234"
    coordinator._detected_model = None
    coordinator.server = AsyncMock()

    async def respond(connection_id, frame, wait_response):
        assert connection_id == "test" and wait_response
        full = frame.content[-2] == 0x5B
        data = bytearray(54 if full else 43)
        data[24 if full else 18] = model
        return Response.from_isecnet_frame(ISECNetFrame.create_mobile_frame(bytes(data)))

    coordinator.server.send_command.side_effect = respond
    await coordinator._async_update_data()
    status = await coordinator._async_update_data()
    assert coordinator._detected_model == model
    assert isinstance(status, CentralStatus if size == 54 else PartialCentralStatus)
    assert CentralModel.get_name(status.model) == name
    assert ("Modelo desconhecido" in caplog.text) == (model == 0xFF)
    frame = coordinator.server.send_command.call_args.args[1]
    assert frame.content[-2] == (0x5B if size == 54 else 0x5A)


async def test_4010_falls_back_when_partial_status_is_unavailable(coordinator_class):
    coordinator = object.__new__(coordinator_class)
    coordinator.connection_id = "test"
    coordinator._detected_model = None
    coordinator._fetch_partial_status = AsyncMock(side_effect=TimeoutError)
    status = CentralStatus(model=CentralModel.AMT_4010)
    coordinator._fetch_full_status = AsyncMock(return_value=status)
    assert await coordinator._async_update_data() is status
    assert await coordinator._async_update_data() is status
    coordinator._fetch_partial_status.assert_awaited_once()
    assert coordinator._fetch_full_status.await_count == 2
