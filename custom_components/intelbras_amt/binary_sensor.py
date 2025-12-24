"""Binary Sensors para zonas e problemas da central."""

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import AMTCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configura os binary sensors."""
    coordinator: AMTCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    entities: list[BinarySensorEntity] = []
    
    # Cria entidades para todas as zonas (sempre cria todas, mesmo que não estejam ativas)
    # Zonas abertas, violadas e bypass (1-48)
    for zone_num in range(1, 49):
        entities.append(AMTZoneBinarySensor(coordinator, entry, zone_num, "aberta"))
        entities.append(AMTZoneBinarySensor(coordinator, entry, zone_num, "violada"))
        entities.append(AMTZoneBinarySensor(coordinator, entry, zone_num, "bypass"))
    
    # Zonas com tamper e curto-circuito (1-18)
    for zone_num in range(1, 19):
        entities.append(AMTZoneBinarySensor(coordinator, entry, zone_num, "tamper"))
        entities.append(AMTZoneBinarySensor(coordinator, entry, zone_num, "curto_circuito"))
    
    # Bateria baixa em sensores sem fio (1-40)
    for zone_num in range(1, 41):
        entities.append(AMTZoneBinarySensor(coordinator, entry, zone_num, "bateria_baixa"))
    
    # Cria entidades de problemas do sistema
    entities.append(AMTProblemBinarySensor(coordinator, entry, "energia", "Falta de Energia"))
    entities.append(AMTProblemBinarySensor(coordinator, entry, "bateria_baixa", "Bateria Baixa"))
    entities.append(AMTProblemBinarySensor(coordinator, entry, "bateria_ausente", "Bateria Ausente"))
    entities.append(AMTProblemBinarySensor(coordinator, entry, "bateria_curto", "Bateria em Curto"))
    entities.append(AMTProblemBinarySensor(coordinator, entry, "sobrecarga_aux", "Sobrecarga Auxiliar"))
    entities.append(AMTProblemBinarySensor(coordinator, entry, "sirene_cortada", "Fio Sirene Cortado"))
    entities.append(AMTProblemBinarySensor(coordinator, entry, "sirene_curto", "Curto Sirene"))
    entities.append(AMTProblemBinarySensor(coordinator, entry, "telefone_cortado", "Linha Telefônica Cortada"))
    entities.append(AMTProblemBinarySensor(coordinator, entry, "falha_comunicacao", "Falha Comunicação"))
    
    async_add_entities(entities)


class AMTZoneBinarySensor(CoordinatorEntity[AMTCoordinator], BinarySensorEntity):
    """Binary sensor para uma zona específica."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: AMTCoordinator,
        entry: ConfigEntry,
        zone_number: int,
        zone_type: str,
    ) -> None:
        """Inicializa o binary sensor de zona.
        
        Args:
            coordinator: Coordinator do status.
            entry: Config entry.
            zone_number: Número da zona (1-48).
            zone_type: Tipo de status ('aberta', 'violada', 'bypass', 'tamper', 'curto_circuito', 'bateria_baixa').
        """
        super().__init__(coordinator)
        self.zone_number = zone_number
        self.zone_type = zone_type
        self._entry = entry
        
        # Define unique_id e name
        self._attr_unique_id = f"{entry.entry_id}_zona_{zone_number:02d}_{zone_type}"
        
        # Nome baseado no tipo
        type_names = {
            "aberta": "Aberta",
            "violada": "Violada",
            "bypass": "Em Bypass",
            "tamper": "Tamper",
            "curto_circuito": "Curto-Circuito",
            "bateria_baixa": "Bateria Baixa",
        }
        self._attr_name = f"Zona {zone_number:02d} - {type_names.get(zone_type, zone_type.title())}"
        
        # Device class apropriado
        if zone_type == "aberta":
            self._attr_device_class = BinarySensorDeviceClass.DOOR
        elif zone_type == "violada":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        elif zone_type in ("tamper", "curto_circuito", "bateria_baixa"):
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        else:
            self._attr_device_class = None
    
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
        
        status = self.coordinator.data
        
        if self.zone_type == "aberta":
            return self.zone_number in status.zones.open_zones
        elif self.zone_type == "violada":
            return self.zone_number in status.zones.violated_zones
        elif self.zone_type == "bypass":
            return self.zone_number in status.zones.bypassed_zones
        elif self.zone_type == "tamper":
            return self.zone_number in status.zones.tamper_zones
        elif self.zone_type == "curto_circuito":
            return self.zone_number in status.zones.short_circuit_zones
        elif self.zone_type == "bateria_baixa":
            return self.zone_number in status.zones.low_battery_zones
        
        return False
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Atributos extras."""
        return {
            "zone_number": self.zone_number,
            "zone_type": self.zone_type,
        }


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

