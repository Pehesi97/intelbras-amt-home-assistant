"""Real local TCP simulator: login, gates, single clear, readback and logout."""
import asyncio

import pytest

from custom_components.intelbras_amt.lib.protocol import programming
from custom_components.intelbras_amt.lib.protocol.checksum import CRC16
from custom_components.intelbras_amt.lib.protocol.isecnet import ISECNetFrame, ISECNetFrameReader


def test_identify_zero_encoding_and_validation():
    frame = programming.identify_frame("102030")
    assert frame.content[:6] == bytes.fromhex("05 11 1a 2a 3a 34")
    assert CRC16.validate_packet(frame.content)
    assert ISECNetFrame.parse(frame.build()) == frame
    assert programming.command_frame(0x19, b"\x10").build() == bytes.fromhex("06 e7 02 19 10 d6 4b 88")
    for password in ("1234", "1234567", "１２３４５６", "abcdef", None):
        with pytest.raises(ValueError):
            programming.identify_frame(password)


@pytest.mark.parametrize("model", [0x1E, 0x34, 0x36, 0x41])
@pytest.mark.parametrize("case", ["success", "denied", "armed", "siren", "retained", "short_reply", "empty", "cancelled"])
async def test_programming_session_is_short_and_clear_is_never_retried(case, model, caplog):
    commands = []
    finished = asyncio.Event()
    memory = case != "empty"

    async def central(reader, writer):
        nonlocal memory
        frames = ISECNetFrameReader()
        try:
            while data := await reader.read(4096):
                for frame in frames.feed(data):
                    c = frame.content
                    assert frame.command == 0xE7 and CRC16.validate_packet(c)
                    code = c[1]
                    commands.append(code)
                    if code == 0x10:
                        body = b"\x01\x90"
                    elif code == 0x11:
                        assert c[2:-3] == bytes.fromhex("1a 2a 3a")
                        body = b"\x01\x53" if case == "denied" else b"\x01\x50"
                    elif code == 0x17:
                        body = bytearray(33 if model == 0x41 else 27)
                        body[:3] = bytes((len(body) - 1, 0x97, model))
                        body[4] = 2 if case == "armed" else 0
                        body[20 if model == 0x41 else 16] = 0x80 if memory else 0
                    elif code == 0x19:
                        assert c[2] == 0x10  # Read-only function, never siren/PGM control.
                        body = bytes((2, 0x99, 4 if case == "siren" else 0))
                    elif code == 0x1C:
                        assert len(c) == 4
                        if case == "short_reply":
                            writer.write(ISECNetFrame(0xE7, b"\x00\x00").build())
                            await writer.drain()
                            continue
                        body = b"\x01\x9c"
                        if case != "retained":
                            memory = False
                    elif code == 0x15:
                        body = b"\x02\x95\x00"
                    else:
                        raise AssertionError(f"Unexpected command {code:02x}")
                    reply = ISECNetFrame(0xE7, CRC16.append(body)).build()
                    writer.write(b"\x00\x00" + reply[:3])
                    await writer.drain()
                    writer.write(reply[3:])
                    await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            finished.set()

    server = await asyncio.start_server(central, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async def operation():
        async with programming.ProgrammingSession("127.0.0.1", "102030", port) as session:
            if case == "cancelled":
                raise asyncio.CancelledError()
            await session.clear_alarm_memory()
    try:
        if case in ("success", "empty"):
            await operation()
        elif case == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await operation()
        else:
            with pytest.raises((ValueError, PermissionError)):
                await operation()
        await asyncio.wait_for(finished.wait(), 2)
        assert commands.count(0x11) == 1
        assert commands.count(0x1C) == (1 if case in ("success", "retained", "short_reply") else 0)
        if case == "denied":
            assert commands == [0x10, 0x11]
        else:
            assert commands[-1] == 0x15
        assert "102030" not in caplog.text and "1a 2a 3a" not in caplog.text
    finally:
        server.close()
        await server.wait_closed()


def test_programming_status_checks_model_layout_crc_and_zone_boundaries():
    for model, size, last_zone in ((0x1E, 29, 48), (0x34, 29, 48), (0x36, 29, 48), (0x41, 35, 64)):
        body = bytearray(size - 2)
        body[:3] = bytes((size - 3, 0x97, model))
        body[4] = 8
        body[6] = 1
        body[6 + 2 * (last_zone // 8 - 1)] = 0x80
        packet = CRC16.append(body)
        assert programming.parse_status(packet) == {"model": model, "partitions": 8, "violated": {1, last_zone}}
        with pytest.raises(ValueError):
            programming.parse_status(packet[:-1])
        with pytest.raises(ValueError):
            programming.parse_status(packet[:-1] + bytes((packet[-1] ^ 1,)))
        body[2] = 0xFF
        with pytest.raises(ValueError, match="Modelo"):
            programming.parse_status(CRC16.append(body))
        body[2] = 0x1E if model == 0x41 else 0x41
        with pytest.raises(ValueError, match="Formato"):
            programming.parse_status(CRC16.append(body))
    for packet in (b"", b"\x00", CRC16.append(b"\x01\x97")):
        with pytest.raises(ValueError):
            programming.parse_status(packet)
