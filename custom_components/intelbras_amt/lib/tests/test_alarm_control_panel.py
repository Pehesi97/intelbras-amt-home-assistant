"""Exercise the real alarm entity with HA base classes replaced, not its lifecycle."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from custom_components.intelbras_amt.lib.protocol.commands import (
    CentralStatus,
    PartialCentralStatus,
)


@pytest.fixture
def alarm_module(monkeypatch):
    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @classmethod
        def __class_getitem__(cls, item):
            return cls

    modules = {
        "homeassistant.components.alarm_control_panel": {
            "AlarmControlPanelEntity": type("AlarmControlPanelEntity", (), {}),
            "AlarmControlPanelEntityFeature": SimpleNamespace(ARM_HOME=1, ARM_AWAY=2),
            "AlarmControlPanelState": type("AlarmControlPanelState", (), {
                "TRIGGERED": "triggered", "ARMED_AWAY": "armed_away", "DISARMED": "disarmed",
            }),
            "CodeFormat": SimpleNamespace(NUMBER="number"),
        },
        "homeassistant.config_entries": {"ConfigEntry": object},
        "homeassistant.core": {"HomeAssistant": object, "callback": lambda fn: fn},
        "homeassistant.helpers.entity_platform": {"AddEntitiesCallback": object},
        "homeassistant.helpers.update_coordinator": {"CoordinatorEntity": CoordinatorEntity},
        "custom_components.intelbras_amt.coordinator": {"AMTCoordinator": object},
    }
    for name, attributes in modules.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)

    path = Path(__file__).parents[2] / "alarm_control_panel.py"
    spec = importlib.util.spec_from_file_location("custom_components.intelbras_amt._alarm_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=[43, 54], ids=["partial", "full"])
def alarm(alarm_module, request):
    # Reproduce the reported fields: A disarmed, B armed, one open zone,
    # global triggered flag, no violated zone and no siren. No zone map is assumed.
    size = request.param
    raw = bytearray(size)
    partition_offset, function_offset = (20, 22) if size == 43 else (26, 29)
    raw[partition_offset] = 1
    raw[partition_offset + 1] = 2
    raw[function_offset] = 0x0C
    raw[0] = 1
    parser = PartialCentralStatus if size == 43 else CentralStatus
    coordinator = SimpleNamespace(data=parser.parse(raw))
    hass = SimpleNamespace(data={"intelbras_amt": {"test": {"connected": True}}})
    return alarm_module.IntelbrasAMTAlarm(hass, SimpleNamespace(entry_id="test"), coordinator)


def test_partitioned_global_flag_without_violation_stays_armed(alarm, caplog):
    assert not alarm.coordinator.data.partitions.partition_a_armed
    assert alarm.coordinator.data.partitions.partition_b_armed
    assert alarm.alarm_state == "armed_away"
    assert "sem zona violada" in caplog.text
    assert "central desarmada" not in caplog.text


def test_silent_zone_alarm_survives_open_flag_clearing_then_disarms(alarm):
    status = alarm.coordinator.data
    status.zones.violated_zones = {1}
    assert not status.siren_on
    assert alarm.alarm_state == "triggered"
    status.zones.open_zones.clear()
    assert alarm.alarm_state == "triggered"
    status.armed = False
    status.partitions.partition_b_armed = False
    assert alarm.alarm_state == "disarmed"
    assert status.triggered and status.zones.violated_zones == {1}


def test_nonpartitioned_global_flag_behavior_is_preserved(alarm):
    alarm.coordinator.data.partitions.partitions_enabled = False
    assert alarm.alarm_state == "triggered"


def test_triggered_with_siren_does_not_require_a_violated_zone(alarm):
    alarm.coordinator.data.siren_on = True
    assert alarm.alarm_state == "triggered"


def test_siren_bips_and_sustained_fallback_are_preserved(alarm, alarm_module, monkeypatch):
    status = alarm.coordinator.data
    status.triggered = False
    status.siren_on = True
    ticks = iter([0.0, 10.0, 12.0, 14.0])
    monkeypatch.setattr(alarm_module, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    alarm._update_siren_trigger_fallback()
    assert alarm.alarm_state == "armed_away"
    status.siren_on = False
    alarm._update_siren_trigger_fallback()
    status.armed = False
    status.siren_on = True
    alarm._update_siren_trigger_fallback()
    assert alarm.alarm_state == "disarmed"
    alarm._update_siren_trigger_fallback()
    assert alarm.alarm_state == "disarmed"
    alarm._update_siren_trigger_fallback()
    assert alarm.alarm_state == "triggered"
    status.siren_on = False
    alarm._update_siren_trigger_fallback()
    assert alarm.alarm_state == "disarmed"


def test_ignored_memory_log_ignores_clock_and_openings(alarm, caplog):
    status = alarm.coordinator.data
    status.armed = False
    status.zones.violated_zones = {26}
    assert alarm.alarm_state == "disarmed"
    count = len(caplog.records)
    status.raw_data = bytes([1]) * len(status.raw_data)
    status.zones.open_zones = {25}
    assert alarm.alarm_state == "disarmed"
    assert len(caplog.records) == count
    status.zones.violated_zones.add(27)
    assert alarm.alarm_state == "disarmed"
    assert len(caplog.records) == count + 1
    status.triggered = False
    assert alarm.alarm_state == "disarmed"
    status.triggered = True
    assert alarm.alarm_state == "disarmed"
    assert len(caplog.records) == count + 2
