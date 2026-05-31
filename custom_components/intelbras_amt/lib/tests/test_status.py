"""Tests for AMT status parsing."""

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
