"""Run with HA installed: python -m custom_components.intelbras_amt.lib.tests.ha_native_check.

Uses a temporary HA configuration and synthetic status only; never contacts a panel.
On the HA 2026.8.1 / Python 3.14.6 image, run with PYTHONMALLOC=malloc
to avoid an interpreter GC crash during this isolated harness shutdown.
"""
import asyncio
from datetime import datetime, timezone
import json
import tempfile
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

import custom_components.intelbras_amt as integration
from custom_components.intelbras_amt.lib.protocol.isecnet import ISECNetFrame
from custom_components.intelbras_amt.binary_sensor import AMTZoneBinarySensor, AMTZoneProblemBinarySensor
from custom_components.intelbras_amt.config_flow import IntelbrasAMTConfigFlow, IntelbrasAMTOptionsFlow
from custom_components.intelbras_amt.coordinator import AMTCoordinator
from custom_components.intelbras_amt.diagnostics import async_get_config_entry_diagnostics
from custom_components.intelbras_amt.entity_selection import async_apply_entity_selection
from custom_components.intelbras_amt.lib.protocol.commands import PartialCentralStatus


def entry(port=9009):
    return config_entries.ConfigEntry(
        version=1, minor_version=1, domain="intelbras_amt", title="Test",
        data={"port": port, "password": "123456", "update_interval": 2}, options={},
        source="user", unique_id=f"intelbras_amt_{port}", discovery_keys=MappingProxyType({}),
        subentries_data=[],
    )


async def main():
    with tempfile.TemporaryDirectory(prefix="amt-native-") as config_dir:
        hass = HomeAssistant(config_dir)
        hass.config_entries = config_entries.ConfigEntries(hass, {})
        await hass.config_entries.async_initialize()
        main_entry, other_entry = entry(), entry(9010)
        with patch.object(hass.config_entries, "async_setup", AsyncMock(return_value=True)):
            await hass.config_entries.async_add(main_entry)
            await hass.config_entries.async_add(other_entry)
        coordinator = AMTCoordinator(hass, AsyncMock(), "synthetic", "123456", main_entry.entry_id)
        coordinator._detected_model = 0x1E
        hass.data["intelbras_amt"] = {main_entry.entry_id: {"coordinator": coordinator}}

        # Real CoordinatorEntity availability, disconnected polling, and recovery.
        opening = AMTZoneBinarySensor(coordinator, main_entry, 25)
        problem = AMTZoneProblemBinarySensor(coordinator, main_entry, 25)
        raw = bytearray(43)
        raw[3] = raw[41] = 1
        status = PartialCentralStatus.parse(raw)
        coordinator.async_set_updated_data(status)
        assert opening.available and opening.is_on and problem.is_on
        coordinator.connection_id = None
        coordinator.async_set_update_error(UpdateFailed("Disconnected"))
        assert not opening.available and not problem.available
        try:
            await coordinator._async_update_data()
            raise AssertionError("Disconnected poll succeeded")
        except UpdateFailed:
            pass
        coordinator.connection_id = "reconnected"
        coordinator._fetch_partial_status = AsyncMock(return_value=status)
        coordinator.async_set_updated_data(await coordinator._async_update_data())
        assert opening.available and problem.available
        assert coordinator.successful_polls == 1

        # Reconfiguration preserves entry identity and password; checks duplicates.
        flow = IntelbrasAMTConfigFlow()
        flow.hass = hass
        flow.context = {"source": "reconfigure", "entry_id": main_entry.entry_id}
        result = await flow.async_step_reconfigure()
        assert "123456" not in repr(result)
        assert (await flow.async_step_reconfigure({"port": 9010}))["errors"] == {"port": "port_in_use"}
        assert (await flow.async_step_reconfigure({"port": 9009, "password": "12ab"}))["errors"]["password"] == "invalid_password"
        with patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)) as reload:
            result = await flow.async_step_reconfigure({"port": 9011, "password": ""})
            await hass.async_block_till_done()
            assert result["type"] == "abort"
            assert main_entry.data["password"] == "123456"
            assert main_entry.data["port"] == 9011 and main_entry.unique_id == "intelbras_amt_9011"
            reload.assert_awaited_once_with(main_entry.entry_id)

        # Separate status password is validated, preserved when blank, never prefilled.
        initial = IntelbrasAMTConfigFlow()
        initial.hass = hass
        initial.context = {"source": "user"}
        for invalid in ("12ab", "１２３４", "123", "1234567", None):
            values = {"port": 9020, "password": "123456", "status_password": invalid}
            assert (await initial.async_step_user(values))["errors"]["status_password"] == "invalid_password"
        for optional in ({}, {"status_password": ""}, {"status_password": "654321"}):
            result = await initial.async_step_user({"port": 9020, "password": "123456", **optional})
            assert result["type"] == "create_entry"
        with patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)):
            await flow.async_step_reconfigure({"port": 9011, "status_password": "654321"})
            await hass.async_block_till_done()
            await flow.async_step_reconfigure({"port": 9011, "password": "", "status_password": ""})
            await hass.async_block_till_done()
        assert main_entry.data["password"] == "123456" and main_entry.data["status_password"] == "654321"
        result = await flow.async_step_reconfigure()
        assert all(secret not in repr(result) for secret in ("123456", "654321"))

        # Options validate choices, normalize strings, allow empty selections.
        options = IntelbrasAMTOptionsFlow()
        options.hass = hass
        options.handler = main_entry.entry_id
        result = await options.async_step_init({"update_interval": 4, "zones": ["25"], "pgms": []})
        assert result["data"] == {"update_interval": 4, "zones": [25], "pgms": []}
        for bad in (
            {"update_interval": 0, "zones": ["25"], "pgms": []},
            {"update_interval": 4, "zones": ["49"], "pgms": []},
            {"update_interval": 4, "zones": ["25"], "pgms": ["20"]},
        ):
            assert (await options.async_step_init(bad))["errors"]
        assert (await options.async_step_init({"update_interval": 4, "zones": [], "pgms": []}))["data"]["zones"] == []

        # Real entity registry: disable/re-enable with stable IDs, preserve USER.
        dr.async_setup(hass)
        await dr.async_load(hass)
        registry = er.async_get(hass)
        await registry.async_load()
        rows = {}
        for suffix, domain in (("zona_25_aberta", "binary_sensor"), ("zona_25_problema", "binary_sensor"),
                               ("zona_26_aberta", "binary_sensor"), ("pgm_01", "switch"), ("problema_energia", "binary_sensor")):
            rows[suffix] = registry.async_get_or_create(
                domain, "intelbras_amt", f"{main_entry.entry_id}_{suffix}", config_entry=main_entry,
            )
        registry.async_update_entity(rows["zona_26_aberta"].entity_id, disabled_by=er.RegistryEntryDisabler.USER, name="Custom")
        hass.config_entries.async_update_entry(main_entry, options={"zones": [], "pgms": []})
        async_apply_entity_selection(hass, main_entry)
        for suffix in ("zona_25_aberta", "zona_25_problema", "pgm_01"):
            assert registry.async_get(rows[suffix].entity_id).disabled_by == er.RegistryEntryDisabler.INTEGRATION
        assert registry.async_get(rows["problema_energia"].entity_id).disabled_by is None
        hass.config_entries.async_update_entry(main_entry, options={"zones": [25,26], "pgms": [1]})
        async_apply_entity_selection(hass, main_entry)
        for suffix in ("zona_25_aberta", "zona_25_problema", "pgm_01"):
            assert registry.async_get(rows[suffix].entity_id).disabled_by is None
        manual = registry.async_get(rows["zona_26_aberta"].entity_id)
        assert manual.disabled_by == er.RegistryEntryDisabler.USER and manual.name == "Custom"

        # A busy port leaves a retryable entry rather than a half-loaded runtime.
        with patch.object(integration.AMTServer, "start", AsyncMock(side_effect=OSError("busy"))):
            try:
                await integration.async_setup_entry(hass, main_entry)
                raise AssertionError("Busy port was accepted")
            except ConfigEntryNotReady:
                assert main_entry.entry_id not in hass.data["intelbras_amt"]

        # Actual integration callbacks, with only network start/platform loading mocked.
        with patch.object(integration.AMTServer, "start", AsyncMock()), patch.object(
            hass.config_entries, "async_forward_entry_setups", AsyncMock(),
        ):
            assert await integration.async_setup_entry(hass, main_entry)
        runtime = hass.data["intelbras_amt"][main_entry.entry_id]
        live = runtime["coordinator"]
        assert live.password == "654321" and runtime["password"] == "123456"
        server = runtime["server"]
        live._detected_model = 0x1E
        live._fetch_partial_status = AsyncMock(return_value=status)
        probe = AMTZoneBinarySensor(live, main_entry, 25)
        assert not probe.available
        await server._connect_callbacks[0](SimpleNamespace(id="first"))
        await hass.async_block_till_done()
        assert probe.available
        await server._connect_callbacks[0](SimpleNamespace(id="second"))
        await server._disconnect_callbacks[0](SimpleNamespace(id="first"))
        assert live.connection_id == "second" and runtime["connected"]
        await live.async_refresh()
        assert probe.available
        await server._disconnect_callbacks[0](SimpleNamespace(id="second"))
        assert not probe.available
        await server._frame_callbacks[0](SimpleNamespace(id="first"), ISECNetFrame.create_mobile_frame(bytes(43)))
        assert not probe.available
        await live.async_shutdown()
        hass.data["intelbras_amt"][main_entry.entry_id] = {"coordinator": coordinator}

        # Diagnostics use a whitelist, including no sensitive error messages.
        coordinator.last_error_type = "TimeoutError"
        coordinator.last_exception = RuntimeError("password=123456 192.0.2.55")
        coordinator.connection_id = "192.0.2.55:1234"
        diagnostics = await async_get_config_entry_diagnostics(hass, main_entry)
        serialized = json.dumps(diagnostics)
        assert all(secret not in serialized for secret in ("123456", "654321", "192.0.2.55", main_entry.entry_id, "raw_data"))
        assert diagnostics["successful_polls"] == 1 and diagnostics["last_successful_poll"]
        await coordinator.async_shutdown()

        # Existing entries keep using their command password for polling.
        with patch.object(integration.AMTServer, "start", AsyncMock()), patch.object(
            hass.config_entries, "async_forward_entry_setups", AsyncMock(),
        ):
            assert await integration.async_setup_entry(hass, other_entry)
        legacy = hass.data["intelbras_amt"][other_entry.entry_id]
        assert legacy["coordinator"].password == legacy["password"] == "123456"
        await legacy["coordinator"].async_shutdown()
        await hass.async_stop(force=True)
        print("HA native checks passed: availability, reconfiguration, selection, diagnostics")


if __name__ == "__main__":
    asyncio.run(main())
