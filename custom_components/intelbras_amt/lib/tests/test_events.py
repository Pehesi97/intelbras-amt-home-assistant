"""Contact-ID wire payloads, independent of HA and real alarm hardware."""

from datetime import datetime

from custom_components.intelbras_amt.lib.protocol.events import ArmEvent
from custom_components.intelbras_amt.lib.protocol.isecnet import ISECNetFrame


def test_arm_events_and_invalid_payloads():
    # 3/401: armed by user 007 in partition 02. Contact-ID zero is 0x0A.
    payload = bytes.fromhex("11 01 02 03 04 01 08 03 04 0a 01 0a 02 0a 0a 07")
    assert ArmEvent.from_frame(ISECNetFrame(0xB0, payload)) == ArmEvent("Armado", 401, 2, 7, None)
    disarm = payload[:7] + b"\x01" + payload[8:]
    calendar = bytes.fromhex("0f 06 11 0c 03 18 0f 06 11 0c 03 18")
    assert ArmEvent.from_frame(ISECNetFrame(0xB4, disarm + calendar)) == ArmEvent(
        "Desarmado", 401, 2, 7, datetime(2017, 6, 15, 12, 3, 24),
    )
    master = payload[:13] + b"\x0a\x0a\x0a"
    assert ArmEvent.from_frame(ISECNetFrame(0xB0, master)).user_number == 0
    for code in (403, 407, 408, 456):
        encoded = bytes(int(digit) or 10 for digit in str(code))
        event = ArmEvent.from_frame(ISECNetFrame(0xB0, payload[:8] + encoded + payload[11:]))
        assert event.code == code and event.action == "Armado"
        assert event.user_number == (7 if code == 456 else None)
    for command, data in (
        (0xE9, payload), (0xB0, payload[:-1]), (0xB4, payload),
        (0xB0, b"\xff" + payload[1:]),
        (0xB0, payload[:5] + b"\x01\x09" + payload[7:]),
        (0xB0, payload[:7] + b"\x06" + payload[8:]),
        (0xB0, payload[:13] + b"\xff\x0a\x07"),
        (0xB0, payload[:8] + b"\x01\x03\x0a" + payload[11:]),  # Zone alarm.
        (0xB4, payload + b"\x00" * 12),  # Invalid calendar.
    ):
        assert ArmEvent.from_frame(ISECNetFrame(command, data)) is None
