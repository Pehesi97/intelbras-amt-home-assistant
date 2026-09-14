"""Diagnóstico com campos permitidos explícitos; nunca inclui senha ou frames."""

from .const import DOMAIN
from .lib.const import CentralModel


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
    if coordinator is None:
        return {"loaded": False}
    status = coordinator.data
    return {
        "loaded": True,
        "connected": coordinator.connection_id is not None,
        "status_available": coordinator.last_update_success,
        "model": CentralModel.get_name(coordinator._detected_model) if coordinator._detected_model is not None else None,
        "firmware": status.firmware_version if status else None,
        "status_bytes": len(status.raw_data) if status else None,
        "poll_interval_seconds": coordinator.update_interval.total_seconds(),
        "last_successful_poll": coordinator.last_successful_poll.isoformat() if coordinator.last_successful_poll else None,
        "successful_polls": coordinator.successful_polls,
        "failed_polls": coordinator.failed_polls,
        "last_error_type": coordinator.last_error_type,
        "selected_zones": entry.options.get("zones", "all"),
        "selected_pgms": entry.options.get("pgms", "all"),
    }
