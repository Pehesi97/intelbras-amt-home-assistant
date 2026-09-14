"""Tests for AMT status parsing."""

from datetime import datetime

import pytest

from custom_components.intelbras_amt.lib.protocol.commands.status import (
    CentralStatus,
    PartialCentralStatus,
)


def test_partial_status_ignores_non_alarm_function_bit() -> None:
    """Bit 0x40 is not the alarm-triggered flag."""
    data = bytearray(43)
    data[22] = 0x40

    status = PartialCentralStatus.parse(data)

    assert not status.triggered


def test_full_status_ignores_non_alarm_function_bit() -> None:
    """Bit 0x40 is not the alarm-triggered flag."""
    data = bytearray(54)
    data[29] = 0x40

    status = CentralStatus.parse(data)

    assert not status.triggered


def test_partial_status_parses_alarm_triggered_bit() -> None:
    """Bit 0x04 is the alarm-triggered flag."""
    data = bytearray(43)
    data[22] = 0x04

    status = PartialCentralStatus.parse(data)

    assert status.triggered


def test_full_status_parses_alarm_triggered_bit() -> None:
    """Bit 0x04 is the alarm-triggered flag."""
    data = bytearray(54)
    data[29] = 0x04

    status = CentralStatus.parse(data)

    assert status.triggered


@pytest.mark.parametrize("raw,armed,siren", [
    ("01 00 00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 1e 85 01 03 4c 0f 0a 01 09 1a 00 00 0f 00 00 00 00 00 00 24 00 00 00 00 00", True, True),
    ("00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 1e 85 01 03 4c 0f 13 01 09 1a 00 00 0f 00 00 00 00 00 00 20 00 00 00 00 00", True, False),
    ("00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 1e 85 01 00 55 12 29 01 09 1a 00 00 0f 00 08 00 00 00 00 24 00 00 00 00 00", False, True),
])
def test_issue_11_status_samples_preserve_raw_flags(raw, armed, siren):
    data = bytes.fromhex(raw)
    status = PartialCentralStatus.parse(data)
    assert status.armed is armed
    assert status.siren_on is siren
    assert status.triggered
    assert status.zones.violated_zones == {1}
    # These captures include 0x1A (year) and 0x0A (minute): not valid BCD.
    assert status.central_datetime == datetime(2026, 9, 1, data[23], data[24])
    assert status.raw_data == data


@pytest.mark.parametrize("raw,triggered,violated", [
    ("00 00 00 00 00 00 00 00 00 03 00 00 00 00 00 00 00 00 1e 85 00 00 44 10 39 0e 09 1a 00 00 0f 00 00 00 00 00 00 40 00 00 00 00 00", True, {25, 26}),
    ("00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 1e 85 00 00 00 10 3b 0e 09 1a 00 00 0f 00 00 00 00 00 00 40 00 00 00 00 00", False, set()),
])
def test_disarmed_alarm_memory_before_and_after_keypad_clear(raw, triggered, violated):
    """AMT2018 firmware 8.5 captures around Apagar on 2026-09-14."""
    status = PartialCentralStatus.parse(bytes.fromhex(raw))
    assert not status.armed
    assert not status.siren_on
    assert status.triggered is triggered
    assert status.zones.violated_zones == violated


@pytest.mark.parametrize("raw,armed,open_zones", [
    ("00 00 00 01 00 00 00 00 00 01 00 00 00 00 00 00 00 00 1e 85 00 03 4c 11 0d 0e 09 1a 00 00 0f 00 00 00 00 00 00 40 00 00 00 00 00", True, {25}),
    ("00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 1e 85 00 03 4c 11 0d 0e 09 1a 00 00 0f 00 00 00 00 00 00 40 00 00 00 00 00", True, set()),
    ("00 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 1e 85 00 00 44 11 0e 0e 09 1a 00 00 0f 00 00 00 00 00 00 40 00 00 00 00 00", False, set()),
])
def test_silent_alarm_persists_after_open_flag_clears_and_disarm(raw, armed, open_zones):
    """Zone 25 sends opening only; a cleared flag is not confirmed closure."""
    status = PartialCentralStatus.parse(bytes.fromhex(raw))
    assert status.armed is armed
    assert status.triggered
    assert not status.siren_on
    assert status.zones.open_zones == open_zones
    assert status.zones.violated_zones == {25}


def test_partial_tamper_and_short_second_bytes_start_at_zone_11():
    """ISECMobile R15 Status34-37: zones 1-8 and 11-18, no 9/10."""
    raw = bytearray(43)
    raw[33:37] = bytes([0x81, 0x81, 0x42, 0x42])
    status = PartialCentralStatus.parse(raw)
    assert status.zones.tamper_zones == {1, 8, 11, 18}
    assert status.zones.short_circuit_zones == {2, 7, 12, 17}
