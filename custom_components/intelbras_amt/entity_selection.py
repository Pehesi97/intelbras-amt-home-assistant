"""Seleção de entidades preservando o cadastro e escolhas manuais do usuário."""

from .const import DOMAIN


def selected_numbers(entry, key: str, maximum: int) -> list[int]:
    return [number for number in range(1, maximum + 1)
            if number in entry.options.get(key, range(1, maximum + 1))]


def async_apply_entity_selection(hass, entry) -> None:
    """Desabilita somente a seleção da integração; não reativa desabilitação manual."""
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    enabled = {}
    for key, maximum, prefix, suffixes, domain in (
        ("zones", 64, "zona", ("_aberta", "_problema"), "binary_sensor"),
        ("pgms", 19, "pgm", ("",), "switch"),
    ):
        if key not in entry.options:
            continue
        selected = selected_numbers(entry, key, maximum)
        for number in range(1, maximum + 1):
            for suffix in suffixes:
                enabled[(domain, f"{entry.entry_id}_{prefix}_{number:02d}{suffix}")] = number in selected
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        key = (entity.domain, entity.unique_id)
        if entity.platform != DOMAIN or key not in enabled:
            continue
        if not enabled[key] and entity.disabled_by is None:
            registry.async_update_entity(entity.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
        elif enabled[key] and entity.disabled_by == er.RegistryEntryDisabler.INTEGRATION:
            registry.async_update_entity(entity.entity_id, disabled_by=None)
