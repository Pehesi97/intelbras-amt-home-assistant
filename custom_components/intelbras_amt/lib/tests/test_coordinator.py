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
    coordinator.successful_polls = coordinator.failed_polls = 0
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
    coordinator.successful_polls = coordinator.failed_polls = 0
    coordinator._detected_model = None
    coordinator._fetch_partial_status = AsyncMock(side_effect=TimeoutError)
    status = CentralStatus(model=CentralModel.AMT_4010)
    coordinator._fetch_full_status = AsyncMock(return_value=status)
    assert await coordinator._async_update_data() is status
    assert await coordinator._async_update_data() is status
    coordinator._fetch_partial_status.assert_awaited_once()
    assert coordinator._fetch_full_status.await_count == 2


async def test_disconnected_poll_cannot_report_success(coordinator_class):
    coordinator = object.__new__(coordinator_class)
    coordinator.connection_id = None
    with pytest.raises(Exception, match="Central desconectada"):
        await coordinator._async_update_data()


async def test_timeout_and_connection_replacement_are_not_valid_status(coordinator_class):
    coordinator = object.__new__(coordinator_class)
    coordinator.connection_id = "old"
    coordinator._detected_model = CentralModel.AMT_2018_E
    coordinator.successful_polls = coordinator.failed_polls = 0
    coordinator._fetch_partial_status = AsyncMock(side_effect=TimeoutError)
    with pytest.raises(Exception, match="Timeout"):
        await coordinator._async_update_data()
    assert coordinator.failed_polls == 1 and coordinator.last_error_type == "TimeoutError"

    async def stale_response():
        coordinator.connection_id = "new"
        return PartialCentralStatus.parse(bytes(43))
    coordinator._fetch_partial_status = stale_response
    with pytest.raises(Exception, match="substituída"):
        await coordinator._async_update_data()
    assert coordinator.successful_polls == 0


async def test_issue8_computer_password_and_captured_4010_status(coordinator_class):
    # Public AMT 4010 Smart firmware 3.9 capture, issue #8, comment 5328597331.
    full = Response.parse(bytes.fromhex(
        "37 e9 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 41 39 01 00 00 11 0a 0c 12 08 1a 00 00 00 00 00 0f 00 08 00 00 00 00 00 00 00 00 00 00 00 48"
    ))
    coordinator = object.__new__(coordinator_class)
    coordinator.connection_id = "test"
    coordinator.password = "654321"
    coordinator.successful_polls = coordinator.failed_polls = 0
    coordinator._detected_model = None
    coordinator.server = AsyncMock()
    coordinator.server.send_command.side_effect = [
        Response.from_isecnet_frame(ISECNetFrame.create_mobile_frame(bytes([0xE5]))), full, full,
    ]
    await coordinator._async_update_data()
    status = await coordinator._async_update_data()
    assert status.model == CentralModel.AMT_4010 and status.firmware_version == "3.9"
    assert status.partitions.partitions_enabled and not status.armed
    frames = [call.args[1].content for call in coordinator.server.send_command.call_args_list]
    assert frames == [b"!654321\x5a!", b"!654321\x5b!", b"!654321\x5b!"]


@pytest.mark.parametrize("method", ["_fetch_partial_status", "_fetch_full_status"])
@pytest.mark.parametrize("code,hint", [(0xE1, True), (0xE2, True), (0xE5, False)])
async def test_status_rejection_is_actionable_without_exposing_password(coordinator_class, method, code, hint):
    coordinator = object.__new__(coordinator_class)
    coordinator.connection_id = "test"
    coordinator.password = "654321"
    response = Response.from_isecnet_frame(ISECNetFrame.create_mobile_frame(bytes([code])))
    coordinator.server = AsyncMock()
    coordinator.server.send_command.return_value = response
    with pytest.raises(Exception) as error:
        await getattr(coordinator, method)()
    message = str(error.value)
    assert f"0x{code:02X}" in message and response.message in message
    assert ("senha do computador" in message) == hint
    assert "654321" not in message
