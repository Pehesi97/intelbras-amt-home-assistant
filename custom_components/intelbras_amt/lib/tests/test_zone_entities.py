"""Zone attributes and registration contracts; HA lifecycle is not simulated."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from custom_components.intelbras_amt.lib.protocol.commands import CentralStatus, PartialCentralStatus


@pytest.fixture
def zone_module(monkeypatch):
    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        @classmethod
        def __class_getitem__(cls, item):
            return cls

    modules = {
        "homeassistant.components.binary_sensor": {
            "BinarySensorEntity": type("BinarySensorEntity", (), {}),
            "BinarySensorDeviceClass": SimpleNamespace(DOOR="door", PROBLEM="problem"),
        },
        "homeassistant.config_entries": {"ConfigEntry": object},
        "homeassistant.core": {"HomeAssistant": object, "callback": lambda fn: fn},
        "homeassistant.helpers.entity_registry": {
            "async_get": lambda hass: hass.registry,
            "async_entries_for_config_entry": lambda registry, entry_id: [
                row for row in registry.entities.values() if row.config_entry_id == entry_id
            ],
        },
        "homeassistant.helpers.entity_platform": {"AddEntitiesCallback": object},
        "homeassistant.helpers.update_coordinator": {"CoordinatorEntity": CoordinatorEntity},
        "custom_components.intelbras_amt.coordinator": {"AMTCoordinator": object},
    }
    for name, attributes in modules.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)

    path = Path(__file__).parents[2] / "binary_sensor.py"
    spec = importlib.util.spec_from_file_location("custom_components.intelbras_amt._zone_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("size,battery_byte,violation_byte,bypass_byte", [
    (43, 41, 9, 15), (54, 47, 11, 19),
])
def test_zone_25_groups_flags_without_changing_open_state(
    zone_module, size, battery_byte, violation_byte, bypass_byte,
):
    parser = PartialCentralStatus if size == 43 else CentralStatus
    raw = bytearray(size)
    coordinator = SimpleNamespace(data=parser.parse(raw))
    entry = SimpleNamespace(entry_id="existing", options={})
    zone = zone_module.AMTZoneBinarySensor(coordinator, entry, 25)
    assert zone._attr_unique_id == "existing_zona_25_aberta"
    assert zone._attr_name == "Zona 25"
    assert zone.extra_state_attributes == {
        "zone_number": 25, "zone_type": "aberta", "violada": False,
        "bypass": False, "bateria_baixa": False, "tamper": None, "curto_circuito": None,
    }
    for index in (battery_byte, violation_byte, bypass_byte):
        raw[index] = 1
    coordinator.data = parser.parse(raw)
    assert not zone.is_on
    assert zone.extra_state_attributes["bateria_baixa"] is True
    assert zone.extra_state_attributes["violada"] is True
    assert zone.extra_state_attributes["bypass"] is True
    raw[3] = 1
    coordinator.data = parser.parse(raw)
    assert zone.is_on
    assert zone.extra_state_attributes["bateria_baixa"] is True
    coordinator.data = parser.parse(bytes(size))
    assert not zone.is_on
    assert zone.extra_state_attributes["bateria_baixa"] is False


@pytest.mark.parametrize("size,zone,battery,tamper", [
    (43, 8, False, False), (43, 9, False, None), (43, 10, False, None),
    (43, 11, False, False), (43, 18, False, False), (43, 19, False, None),
    (43, 40, False, None), (43, 41, None, None), (43, 48, None, None),
    (54, 8, None, False), (54, 9, None, None), (54, 16, None, None),
    (54, 17, False, None), (54, 64, False, None),
])
def test_unreported_diagnostics_are_unknown_not_normal(zone_module, size, zone, battery, tamper):
    parser = PartialCentralStatus if size == 43 else CentralStatus
    sensor = zone_module.AMTZoneBinarySensor(
        SimpleNamespace(data=parser.parse(bytes(size))), SimpleNamespace(entry_id="test"), zone,
    )
    attrs = sensor.extra_state_attributes
    assert attrs["bateria_baixa"] is battery
    assert attrs["tamper"] is tamper
    assert attrs["curto_circuito"] is tamper


def test_no_status_keeps_diagnostic_attributes_unknown(zone_module):
    sensor = zone_module.AMTZoneBinarySensor(
        SimpleNamespace(data=None), SimpleNamespace(entry_id="test"), 25,
    )
    assert sensor.extra_state_attributes == {
        "zone_number": 25, "zone_type": "aberta", "violada": None,
        "bypass": None, "bateria_baixa": None, "tamper": None, "curto_circuito": None,
    }


def test_partial_zone_18_attributes_report_tamper_and_short(zone_module):
    raw = bytearray(43)
    raw[34] = raw[36] = 0x80
    zone = zone_module.AMTZoneBinarySensor(
        SimpleNamespace(data=PartialCentralStatus.parse(raw)),
        SimpleNamespace(entry_id="existing", options={}), 18,
    )
    assert zone.extra_state_attributes["tamper"] is True
    assert zone.extra_state_attributes["curto_circuito"] is True


@pytest.mark.parametrize("model,zones", [(0x1E, 48), (0x41, 64)])
async def test_registration_removes_only_legacy_zone_entities(zone_module, model, zones):
    coordinator = SimpleNamespace(_detected_model=model)
    entry = SimpleNamespace(entry_id="existing", options={})
    registry = SimpleNamespace(entities={})
    registry.async_remove = lambda entity_id: registry.entities.pop(entity_id)
    def add(entity_id, unique_id, config_entry_id="existing", platform="intelbras_amt", domain="binary_sensor"):
        registry.entities[entity_id] = SimpleNamespace(
            entity_id=entity_id, unique_id=unique_id, config_entry_id=config_entry_id,
            platform=platform, domain=domain,
        )
    for zone in range(1, 65):
        for kind in ("violada", "bypass", "bateria_baixa", "tamper", "curto_circuito"):
            add(f"binary_sensor.renamed_{zone}_{kind}", f"existing_zona_{zone:02d}_{kind}")
    add("binary_sensor.main", "existing_zona_25_aberta")
    add("binary_sensor.problem", "existing_zona_25_problema")
    add("binary_sensor.global_battery", "existing_problema_bateria_baixa")
    add("binary_sensor.other_entry", "existing_zona_25_violada", config_entry_id="other")
    add("binary_sensor.other_platform", "existing_zona_25_violada", platform="other")
    add("sensor.other_domain", "existing_zona_25_violada", domain="sensor")
    add("binary_sensor.unknown", "existing_zona_25_custom")
    kept = {key: value for key, value in registry.entities.items() if "renamed" not in key}
    hass = SimpleNamespace(
        data={"intelbras_amt": {"existing": {"coordinator": coordinator}}}, registry=registry,
    )
    for _ in range(2):  # Idempotente em atualizações/reinícios posteriores.
        entities = []
        await zone_module.async_setup_entry(hass, entry, entities.extend)
        assert registry.entities == kept
        ids = {entity._attr_unique_id for entity in entities}
        assert len(ids) == len(entities) == zones * 2 + 9
        assert f"existing_zona_{zones:02d}_aberta" in ids
        assert "existing_problema_bateria_baixa" in ids
        assert sum(type(e) is zone_module.AMTZoneBinarySensor for e in entities) == zones

        assert sum(type(e) is zone_module.AMTZoneProblemBinarySensor for e in entities) == zones
        assert f"existing_zona_{zones:02d}_problema" in ids


@pytest.mark.parametrize("size,zone,diagnostic,byte,mask", [
    (43, 25, "bateria_baixa", 41, 1), (54, 25, "bateria_baixa", 47, 1),
    (43, 18, "tamper", 34, 128), (43, 18, "curto_circuito", 36, 128),
    (54, 1, "tamper", 43, 1), (54, 1, "curto_circuito", 44, 1),
])
def test_zone_problem_tracks_diagnostics_independently_of_opening(
    zone_module, size, zone, diagnostic, byte, mask,
):
    parser = PartialCentralStatus if size == 43 else CentralStatus
    raw = bytearray(size)
    coordinator = SimpleNamespace(data=parser.parse(raw))
    entry = SimpleNamespace(entry_id="existing", options={})
    opening = zone_module.AMTZoneBinarySensor(coordinator, entry, zone)
    problem = zone_module.AMTZoneProblemBinarySensor(coordinator, entry, zone)
    assert problem._attr_unique_id == f"existing_zona_{zone:02d}_problema"
    assert problem._attr_device_class == "problem"
    assert problem.is_on is False
    raw[byte] = mask
    coordinator.data = parser.parse(raw)
    assert problem.is_on is True
    assert opening.is_on is False
    assert problem.extra_state_attributes == {**opening.extra_state_attributes, "zone_type": "problema"}
    assert problem.extra_state_attributes[diagnostic] is True
    raw[(zone - 1) // 8] |= 1 << ((zone - 1) % 8)
    coordinator.data = parser.parse(raw)
    assert opening.is_on is True
    assert problem.is_on is True
    raw[byte] = 0
    coordinator.data = parser.parse(raw)
    assert problem.is_on is False
    assert opening.is_on is True


@pytest.mark.parametrize("size,violation_byte,bypass_byte", [(43, 9, 15), (54, 11, 19)])
def test_memory_and_bypass_do_not_indicate_zone_failure(zone_module, size, violation_byte, bypass_byte):
    raw = bytearray(size)
    raw[violation_byte] = raw[bypass_byte] = 1
    parser = PartialCentralStatus if size == 43 else CentralStatus
    problem = zone_module.AMTZoneProblemBinarySensor(
        SimpleNamespace(data=parser.parse(raw)), SimpleNamespace(entry_id="test"), 25,
    )
    assert problem.extra_state_attributes["violada"] is True
    assert problem.extra_state_attributes["bypass"] is True
    assert problem.is_on is False


@pytest.mark.parametrize("size,zone", [(43, 41), (54, 9), (None, 25)])
def test_zone_problem_is_unknown_without_any_reported_diagnostic(zone_module, size, zone):
    parser = PartialCentralStatus if size == 43 else CentralStatus
    data = parser.parse(bytes(size)) if size else None
    problem = zone_module.AMTZoneProblemBinarySensor(
        SimpleNamespace(data=data), SimpleNamespace(entry_id="test"), zone,
    )
    assert problem.is_on is None


@pytest.mark.parametrize("selected", [[25], []])
async def test_selection_creates_only_chosen_zone_pairs(zone_module, selected):
    entry = SimpleNamespace(entry_id="existing", options={"zones": selected})
    coordinator = SimpleNamespace(_detected_model=0x1E)
    hass = SimpleNamespace(
        data={"intelbras_amt": {"existing": {"coordinator": coordinator}}},
        registry=SimpleNamespace(entities={}),
    )
    entities = []
    await zone_module.async_setup_entry(hass, entry, entities.extend)
    zone_ids = {e._attr_unique_id for e in entities if isinstance(e, zone_module.AMTZoneBinarySensor)}
    assert zone_ids == {f"existing_zona_{n:02d}_{kind}" for n in selected for kind in ("aberta", "problema")}
    assert len(entities) == 9 + 2 * len(selected)
