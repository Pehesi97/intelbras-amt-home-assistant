"""Instalação, reconfiguração e seleção de entidades pela interface do HA."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    DOMAIN, CONF_PASSWORD, CONF_STATUS_PASSWORD, CONF_COMPUTER_PASSWORD, CONF_PORT, CONF_UPDATE_INTERVAL,
    DEFAULT_PORT, DEFAULT_UPDATE_INTERVAL,
)
from .lib.const import CentralModel
from .lib.protocol.programming import PROGRAMMING_MODELS, ProgrammingSession


def _password_selector():
    return selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))


def _connection_schema(defaults):
    return vol.Schema({
        vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
        vol.Required(CONF_PASSWORD): _password_selector(),
        vol.Optional(CONF_STATUS_PASSWORD): _password_selector(),
        vol.Required(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
    })


def _credential_schema(key, data, action="keep"):
    options = [{"value": "keep", "label": "Manter configuração atual"},
               {"value": "replace", "label": "Definir ou substituir senha"}]
    if key != CONF_PASSWORD:
        options.append({"value": "remove", "label": (
            "Usar a senha de usuário nas consultas" if key == CONF_STATUS_PASSWORD else "Desativar Limpar disparo"
        )})
    fields = {}
    if key == CONF_PASSWORD:
        fields[vol.Required(CONF_PORT, default=data.get(CONF_PORT, DEFAULT_PORT))] = int
    fields[vol.Required("action", default=action)] = selector.SelectSelector(
        selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.DROPDOWN),
    )
    fields[vol.Optional(key)] = _password_selector()
    return vol.Schema(fields)


def _connection_errors(data):
    errors = {}
    port = data.get(CONF_PORT)
    interval = data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    if type(port) is not int or not 1 <= port <= 65535:
        errors[CONF_PORT] = "invalid_port"
    for key in (CONF_PASSWORD, CONF_STATUS_PASSWORD, CONF_COMPUTER_PASSWORD):
        password = data.get(key, "")
        if key != CONF_PASSWORD and password == "":
            continue
        minimum = 6 if key == CONF_COMPUTER_PASSWORD else 4
        if not isinstance(password, str) or not (minimum <= len(password) <= 6 and password.isascii() and password.isdigit()):
            errors[key] = "invalid_computer_password_format" if key == CONF_COMPUTER_PASSWORD else "invalid_password"
    if type(interval) is not int or not 1 <= interval <= 60:
        errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
    return errors


class IntelbrasAMTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return IntelbrasAMTOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            errors = _connection_errors(user_input)
            if not errors:
                port = user_input[CONF_PORT]
                await self.async_set_unique_id(f"intelbras_amt_{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"AMT 2018 / 4010 (:{port})", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_connection_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        return self.async_show_menu(step_id="reconfigure", menu_options=["connection", "status_auth", "programming"])

    async def async_step_connection(self, user_input=None):
        return await self._credential_step("connection", CONF_PASSWORD, user_input)

    async def async_step_status_auth(self, user_input=None):
        return await self._credential_step("status_auth", CONF_STATUS_PASSWORD, user_input)

    async def async_step_programming(self, user_input=None):
        return await self._credential_step("programming", CONF_COMPUTER_PASSWORD, user_input)

    async def _credential_step(self, step_id, key, user_input):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            data = dict(entry.data)
            action = user_input.get("action", "keep")
            if action != "replace" and user_input.get(key):
                errors[key] = "choose_replace"
            if action == "replace":
                data[key] = user_input.get(key, "")
                if not data[key]:
                    errors[key] = "password_required"
            elif action == "remove" and key != CONF_PASSWORD:
                data.pop(key, None)
            elif action != "keep":
                errors["action"] = "invalid_action"
            if key == CONF_PASSWORD:
                data[CONF_PORT] = user_input.get(CONF_PORT)
            errors.update(_connection_errors(data))
            if any(other.entry_id != entry.entry_id and other.data.get(CONF_PORT) == data[CONF_PORT]
                   for other in self._async_current_entries()):
                errors[CONF_PORT] = "port_in_use"
            coordinator = self.hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
            old_status = entry.data.get(CONF_STATUS_PASSWORD) or entry.data[CONF_PASSWORD]
            new_status = data.get(CONF_STATUS_PASSWORD) or data[CONF_PASSWORD]
            validate_status = old_status != new_status or (action == "replace" and (
                key == CONF_STATUS_PASSWORD or (key == CONF_PASSWORD and not data.get(CONF_STATUS_PASSWORD))
            ))
            if not errors and (validate_status or (key == CONF_COMPUTER_PASSWORD and action == "replace")):
                if not coordinator or not coordinator.connection_id:
                    errors["base"] = "central_not_connected"
                elif key == CONF_COMPUTER_PASSWORD:
                    if coordinator._detected_model not in PROGRAMMING_MODELS:
                        errors["base"] = "unsupported_programming_model"
                    else:
                        try:
                            connection_id = coordinator.connection_id
                            async with coordinator.programming_lock:
                                async with ProgrammingSession(coordinator.programming_host(), data[key]) as session:
                                    await session.read_status()
                            if coordinator.connection_id != connection_id:
                                raise ConnectionError("Conexão alterada durante validação")
                        except PermissionError:
                            errors[key] = "invalid_computer_password"
                        except OSError:
                            errors["base"] = "cannot_connect_programming"
                        except ValueError:
                            errors["base"] = "programming_failed"
                else:
                    try:
                        await coordinator.async_validate_status_password(new_status)
                    except UpdateFailed:
                        errors["base"] = "status_validation_failed"
                    except (OSError, ValueError):
                        errors["base"] = "central_not_connected"
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data=data, unique_id=f"intelbras_amt_{data[CONF_PORT]}",
                    reload_even_if_entry_is_unchanged=False,
                )
        configured = bool(entry.data.get(key))
        current = "Senha configurada" if configured else (
            "Usando a senha de usuário" if key == CONF_STATUS_PASSWORD else "Limpar disparo desativado"
        )
        return self.async_show_form(
            step_id=step_id, data_schema=_credential_schema(
                key, {**entry.data, **({CONF_PORT: user_input[CONF_PORT]} if user_input and CONF_PORT in user_input else {})},
                user_input.get("action", "keep") if user_input else "keep",
            ), errors=errors,
            description_placeholders={"current": current},
        )


class IntelbrasAMTOptionsFlow(config_entries.OptionsFlowWithReload):
    async def async_step_init(self, user_input=None):
        entry = self.config_entry
        coordinator = self.hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("coordinator")
        model = coordinator._detected_model if coordinator else None
        maximum = 64 if model is None or model == CentralModel.AMT_4010 else 48
        fields = {
            vol.Required(CONF_UPDATE_INTERVAL, default=entry.options.get(
                CONF_UPDATE_INTERVAL, entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            )): vol.All(int, vol.Range(min=1, max=60)),
        }
        for key, limit, label in (("zones", maximum, "Zona"), ("pgms", 19, "PGM")):
            fields[vol.Required(key, default=[str(n) for n in entry.options.get(key, range(1, limit + 1)) if n <= limit])] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    multiple=True,
                    options=[{"value": str(n), "label": f"{label} {n:02d}"} for n in range(1, limit + 1)],
                ),
            )
        schema = vol.Schema(fields)
        errors = {}
        if user_input is not None:
            try:
                values = schema(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_options"
            else:
                return self.async_create_entry(data={
                    **entry.options, CONF_UPDATE_INTERVAL: values[CONF_UPDATE_INTERVAL],
                    "zones": sorted({int(n) for n in values["zones"]}),
                    "pgms": sorted({int(n) for n in values["pgms"]}),
                })
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
