"""Binary Sensors para zonas e problemas da central."""

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import async_get, async_entries_for_config_entry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AMTCoordinator
from .const import DOMAIN
from .entity_selection import selected_numbers
from .lib.const import CentralModel

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura os binary sensors."""
    coordinator: AMTCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Migração da major: remove apenas os IDs auxiliares conhecidos desta entrada.
    registry = async_get(hass)
    legacy_ids = {
        f"{entry.entry_id}_zona_{zone:02d}_{kind}"
        for zone in range(1, 65)
        for kind in ("violada", "bypass", "bateria_baixa", "tamper", "curto_circuito")
    }
    for entity in async_entries_for_config_entry(registry, entry.entry_id):
        if (entity.domain == "binary_sensor" and entity.platform == DOMAIN
                and entity.unique_id in legacy_ids):
            registry.async_remove(entity.entity_id)

    # Sensores de problemas do sistema são independentes do modelo — adiciona imediatamente
    async_add_entities([
        AMTProblemBinarySensor(coordinator, entry, "energia", "Falta de Energia"),
        AMTProblemBinarySensor(coordinator, entry, "bateria_baixa", "Bateria Baixa"),
        AMTProblemBinarySensor(coordinator, entry, "bateria_ausente", "Bateria Ausente"),
        AMTProblemBinarySensor(coordinator, entry, "bateria_curto", "Bateria em Curto"),
        AMTProblemBinarySensor(coordinator, entry, "sobrecarga_aux", "Sobrecarga Auxiliar"),
        AMTProblemBinarySensor(coordinator, entry, "sirene_cortada", "Fio Sirene Cortado"),
        AMTProblemBinarySensor(coordinator, entry, "sirene_curto", "Curto Sirene"),
        AMTProblemBinarySensor(coordinator, entry, "telefone_cortado", "Linha Telefônica Cortada"),
        AMTProblemBinarySensor(coordinator, entry, "falha_comunicacao", "Falha Comunicação"),
    ])

    # Entidades de zona dependem do modelo — registra após detecção automática
    _zones_registered = False

    @callback
    def _async_add_zone_entities() -> None:
        nonlocal _zones_registered
        if _zones_registered or coordinator._detected_model is None:
            return
        _zones_registered = True

        max_zones = 64 if coordinator._detected_model == CentralModel.AMT_4010 else 48
        zone_entities = [
            entity_class(coordinator, entry, zone_num)
            for zone_num in selected_numbers(entry, "zones", max_zones)
            for entity_class in (AMTZoneBinarySensor, AMTZoneProblemBinarySensor)
        ]

        _LOGGER.info(
            "Modelo %s detectado: registrando %d zonas selecionadas",
            CentralModel.get_name(coordinator._detected_model),
            len(zone_entities) // 2,
        )
        async_add_entities(zone_entities)

    # Tenta adicionar imediatamente caso o modelo já seja conhecido (ex: reinício do HA)
    _async_add_zone_entities()

    # Caso contrário, aguarda a primeira atualização do coordinator
    if not _zones_registered:
        entry.async_on_unload(coordinator.async_add_listener(_async_add_zone_entities))


class AMTZoneBinarySensor(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Binary sensor para uma zona específica."""
    
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        zone_number: int,
    ) -> None:
        """Mantém o identificador do sensor de abertura já cadastrado."""
        super().__init__(coordinator)
        self.zone_number = zone_number
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_zona_{zone_number:02d}_aberta"
        self._attr_name = f"Zona {zone_number:02d}"

    @property
    def device_info(self):
        """Informações do dispositivo."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Intelbras AMT 2018 / 4010",
            "manufacturer": "Intelbras",
            "model": "AMT 2018 / 4010",
        }
    
    @property
    def is_on(self) -> bool:
        """Retorna se a zona está ativa."""
        if not self.coordinator.data:
            return False
        
        return self.zone_number in self.coordinator.data.zones.open_zones

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Detalhes reportados pela central para esta zona."""
        attrs = {
            "zone_number": self.zone_number,
            "zone_type": "aberta",
        }

        attrs.update(
            violada=None, bypass=None, bateria_baixa=None,
            tamper=None, curto_circuito=None,
        )
        status = self.coordinator.data
        if status is None:
            return attrs

        size = len(status.raw_data)
        if size not in (43, 54):
            return attrs

        zone = self.zone_number
        zones = status.zones
        if 1 <= zone <= (48 if size == 43 else 64):
            attrs["violada"] = zone in zones.violated_zones
            attrs["bypass"] = zone in zones.bypassed_zones
        if (size == 43 and 1 <= zone <= 40) or (size == 54 and 17 <= zone <= 64):
            attrs["bateria_baixa"] = zone in zones.low_battery_zones
        if 1 <= zone <= 8 or (size == 43 and 11 <= zone <= 18):
            attrs["tamper"] = zone in zones.tamper_zones
            attrs["curto_circuito"] = zone in zones.short_circuit_zones
        return attrs


class AMTZoneProblemBinarySensor(AMTZoneBinarySensor):
    """Agrupa falhas da zona sem confundir abertura ou memória com defeito."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self, coordinator: AMTCoordinator, entry: ConfigEntry, zone_number: int,
    ) -> None:
        super().__init__(coordinator, entry, zone_number)
        self._attr_unique_id = f"{entry.entry_id}_zona_{zone_number:02d}_problema"
        self._attr_name = f"Zona {zone_number:02d} - Problema"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {**super().extra_state_attributes, "zone_type": "problema"}

    @property
    def is_on(self) -> bool | None:
        """Sem diagnóstico reportado, o estado é desconhecido; não presume OK."""
        attrs = self.extra_state_attributes
        reported = [
            attrs[key] for key in ("bateria_baixa", "tamper", "curto_circuito")
            if attrs[key] is not None
        ]
        return any(reported) if reported else None


class AMTProblemBinarySensor(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Binary sensor para problemas do sistema."""
    
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    
    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        problem_type: str,
        problem_name: str,
    ) -> None:
        """Inicializa o binary sensor de problema.
        
        Args:
            coordinator: Coordinator do status.
            entry: Config entry.
            problem_type: Tipo do problema.
            problem_name: Nome amigável do problema.
        """
        super().__init__(coordinator)
        self.problem_type = problem_type
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_problema_{problem_type}"
        self._attr_name = problem_name
    
    @property
    def device_info(self):
        """Informações do dispositivo."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Intelbras AMT 2018 / 4010",
            "manufacturer": "Intelbras",
            "model": "AMT 2018 / 4010",
        }
    
    @property
    def is_on(self) -> bool:
        """Retorna se o problema está ativo."""
        if not self.coordinator.data:
            return False
        
        problems = self.coordinator.data.problems
        
        if self.problem_type == "energia":
            return problems.ac_failure
        elif self.problem_type == "bateria_baixa":
            return problems.low_battery
        elif self.problem_type == "bateria_ausente":
            return problems.battery_absent
        elif self.problem_type == "bateria_curto":
            return problems.battery_short
        elif self.problem_type == "sobrecarga_aux":
            return problems.aux_overload
        elif self.problem_type == "sirene_cortada":
            return problems.siren_wire_cut
        elif self.problem_type == "sirene_curto":
            return problems.siren_short
        elif self.problem_type == "telefone_cortado":
            return problems.phone_line_cut
        elif self.problem_type == "falha_comunicacao":
            return problems.event_comm_failure
        
        return False
