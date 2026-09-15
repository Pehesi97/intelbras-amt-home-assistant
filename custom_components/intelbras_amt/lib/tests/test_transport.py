"""Receiver transactions from ISECnet R14, using streams without real hardware."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.intelbras_amt.lib.protocol.commands import (
    ActivationCommand,
    DeactivationCommand,
    PGMCommand,
    SirenCommand,
    PartialStatusRequestCommand,
    StatusRequestCommand,
)
from custom_components.intelbras_amt.lib.protocol.isecnet import ISECNetFrame, ISECNetFrameReader
from custom_components.intelbras_amt.lib.server import AMTServer, AMTServerConfig
from custom_components.intelbras_amt.lib.server.connection_manager import AMTConnection


# SDK R14 sections 6.1.1, 6.3.1 and 6.4.1; literal wire examples, not our builder.
IDENTIFICATION = bytes.fromhex("07 94 45 12 34 30 00 01 3e")
EVENT = bytes.fromhex("11 b0 11 01 02 03 04 01 08 01 04 06 01 0a 0a 0a 0a 01 41")
DATED_EVENT = bytes.fromhex(
    "1d b4 11 01 02 03 04 01 08 01 04 06 01 0a 0a 0a 0a 01 "
    "0f 06 11 0c 03 18 0f 06 11 0c 03 18 49"
)


def writer_for(reader):
    writer = Mock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.is_closing.return_value = False
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    writer.close.side_effect = reader.feed_eof
    return writer


@pytest.mark.parametrize("packet", [IDENTIFICATION, b"\xf7", EVENT, DATED_EVENT])
async def test_receiver_ack_is_one_byte(packet):
    server = AMTServer()
    reader = asyncio.StreamReader()
    writer = writer_for(reader)
    reader.feed_data(packet)
    reader.feed_eof()
    await server._handle_client(reader, writer)
    assert [call.args[0] for call in writer.write.call_args_list] == [b"\xfe"]


@pytest.mark.parametrize("command,size", [(PartialStatusRequestCommand, 43), (StatusRequestCommand, 54)])
async def test_heartbeat_refresh_reads_reply_and_preserves_interleaved_events(command, size):
    server = AMTServer(AMTServerConfig(response_timeout=0.2))
    reader = asyncio.StreamReader()
    writer = writer_for(reader)
    received = []
    completed = asyncio.Event()
    failures = []
    payload = bytes(size)

    def respond(data):
        if data == command("1234").build():
            # An unsolicited event and a late mobile ACK must not consume the query.
            reader.feed_data(EVENT[:7])
            reader.feed_data(EVENT[7:] + b"\xf7\xf7" + bytes.fromhex("02 e9 fe ea"))
            reader.feed_data(ISECNetFrame.create_mobile_frame(payload).build())

    writer.write.side_effect = respond

    @server.on_heartbeat
    async def refresh(conn):
        try:
            result = await server.send_command(conn.id, command("1234").build_net_frame())
            assert result.raw_frame.content == payload
        except Exception as err:
            failures.append(err)
        finally:
            completed.set()

    @server.on_frame
    async def on_frame(conn, frame):
        received.append(frame)

    reader.feed_data(b"\xf7")
    handler = asyncio.create_task(server._handle_client(reader, writer))
    try:
        await asyncio.wait_for(completed.wait(), 1)
        assert not failures
        assert ISECNetFrame.parse(EVENT) in received
        writes = [call.args[0] for call in writer.write.call_args_list]
        assert writes.count(command("1234").build()) == 1
        assert writes.count(b"\xfe") == 4  # Three heartbeats and the event.
    finally:
        reader.feed_eof()
        await asyncio.wait_for(handler, 1)


@pytest.mark.parametrize("packet", [
    EVENT[:-1] + bytes([EVENT[-1] ^ 1]),  # Invalid checksum.
    ISECNetFrame(0xB0, b"\x11").build(),  # Wrong event length.
    ISECNetFrame(0xAA, bytes(16)).build(),  # Unknown command.
])
async def test_invalid_or_unknown_event_is_not_acknowledged(packet):
    server = AMTServer()
    reader = asyncio.StreamReader()
    writer = writer_for(reader)
    reader.feed_data(packet)
    reader.feed_eof()
    await server._handle_client(reader, writer)
    writer.write.assert_not_called()


def test_mobile_ack_keeps_its_envelope():
    assert ISECNetFrame.create_ack_response().build() == bytes.fromhex("02 e9 fe ea")


def test_short_ack_does_not_swallow_next_frame():
    reader = ISECNetFrameReader()
    assert reader.feed(b"\xfe" + EVENT) == [
        ISECNetFrame.create_simple_ack(), ISECNetFrame.parse(EVENT)
    ]
    assert ISECNetFrame.parse(b"\xfe").build() == b"\xfe"


async def test_reply_arriving_during_drain_is_not_lost():
    server = AMTServer(AMTServerConfig(response_timeout=0.2))
    reader = asyncio.StreamReader()
    writer = writer_for(reader)
    connected = asyncio.Event()
    consumed = asyncio.Event()
    command = PartialStatusRequestCommand("1234").build_net_frame()
    payload = bytes(43)

    @server.on_connect
    async def on_connect(conn):
        connected.set()

    @server.on_frame
    async def on_frame(conn, frame):
        consumed.set()

    # Reader resolves the future while StreamWriter.drain is still yielding.
    sentinel = ISECNetFrame(0xAA, b"sentinel").build()
    async def drain_with_sentinel():
        reader.feed_data(ISECNetFrame.create_mobile_frame(payload).build() + sentinel)
        await consumed.wait()
    writer.drain.side_effect = drain_with_sentinel
    handler = asyncio.create_task(server._handle_client(reader, writer))
    try:
        await asyncio.wait_for(connected.wait(), 1)
        result = await server.send_command("127.0.0.1:12345", command)
        assert result.raw_frame.content == payload
    finally:
        reader.feed_eof()
        await asyncio.wait_for(handler, 1)


@pytest.mark.parametrize("ending", ["disconnect", "cancel", "write_error", "timeout"])
async def test_pending_query_cleanup(ending):
    server = AMTServer(AMTServerConfig(response_timeout=0.05))
    reader = asyncio.StreamReader()
    writer = writer_for(reader)
    connected = asyncio.Event()
    sent = asyncio.Event()
    pending = []

    def on_write(data):
        pending.append(server.connections.get("127.0.0.1:12345").pending_response)
        sent.set()

    writer.write.side_effect = on_write

    @server.on_connect
    async def on_connect(conn):
        connected.set()

    handler = asyncio.create_task(server._handle_client(reader, writer))
    query = None
    try:
        await asyncio.wait_for(connected.wait(), 1)
        conn = server.connections.get("127.0.0.1:12345")
        if ending == "write_error":
            writer.drain.side_effect = ConnectionError("simulated write failure")
        query = asyncio.create_task(server.send_command(conn.id, PartialStatusRequestCommand("1234").build_net_frame()))
        await asyncio.wait_for(sent.wait(), 1)
        if ending == "disconnect":
            reader.feed_eof()
        if ending == "cancel":
            query.cancel()
        expected = {
            "disconnect": ConnectionError, "cancel": asyncio.CancelledError,
            "write_error": ConnectionError, "timeout": TimeoutError,
        }[ending]
        with pytest.raises(expected):
            await asyncio.wait_for(query, 1)
        assert conn.pending_response is None
        assert conn.pending_response_kind is None
        assert pending[0].done()
        assert not conn._command_lock.locked()
    finally:
        if query is not None:
            query.cancel()
            await asyncio.gather(query, return_exceptions=True)
        reader.feed_eof()
        await asyncio.wait_for(handler, 1)


async def test_disconnect_cancels_heartbeat_refresh():
    server = AMTServer()
    reader = asyncio.StreamReader()
    writer = writer_for(reader)
    started = asyncio.Event()
    cancelled = asyncio.Event()
    connections = []

    @server.on_heartbeat
    async def refresh(conn):
        connections.append(conn)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    reader.feed_data(b"\xf7")
    handler = asyncio.create_task(server._handle_client(reader, writer))
    try:
        await asyncio.wait_for(started.wait(), 1)
    finally:
        reader.feed_eof()
        await asyncio.wait_for(handler, 1)
    assert cancelled.is_set()
    assert connections[0]._heartbeat_task is None
    assert server.connections.count == 0


@pytest.mark.parametrize("command,expected", [
    (ActivationCommand.arm_all("1234"), "08 e9 21 31 32 33 34 41 21 5b"),
    (DeactivationCommand.disarm_all("1234"), "08 e9 21 31 32 33 34 44 21 5e"),
    (PGMCommand.turn_on("1234", 1), "0a e9 21 31 32 33 34 50 4c 31 21 35"),
    (SirenCommand.turn_on_siren("1234"), "08 e9 21 31 32 33 34 43 21 59"),
    (SirenCommand.turn_off_siren("1234"), "08 e9 21 31 32 33 34 63 21 79"),
])
async def test_outgoing_commands_keep_documented_wire_format(command, expected):
    server = AMTServer()
    reader = asyncio.StreamReader()
    writer = writer_for(reader)
    conn = AMTConnection("test", ("127.0.0.1", 12345), reader, writer)
    server.connections.add(conn)
    assert await server.send_command(conn.id, command.build_net_frame(), wait_response=False) is None
    writer.write.assert_called_once_with(bytes.fromhex(expected))
    assert conn.pending_response is None


@pytest.mark.parametrize("password", ["1234", "12345", "123456"])
def test_only_mobile_replies_can_complete_status_queries(password):
    server = AMTServer()
    conn = Mock(pending_response_kind="status_partial")
    command = PartialStatusRequestCommand(password).build_net_frame()
    assert server._expected_response_kind(command) == "status_partial"
    assert not server._matches_pending_response(conn, ISECNetFrame(0x95, bytes(43)))
    assert not server._matches_pending_response(conn, ISECNetFrame.create_ack_response())
    assert server._matches_pending_response(conn, ISECNetFrame.create_mobile_frame(b"\xe1"))
    assert server._matches_pending_response(conn, ISECNetFrame.create_mobile_frame(bytes(43)))


def test_fragmented_event_is_only_emitted_after_its_checksum():
    reader = ISECNetFrameReader()
    for byte in EVENT[:-1]:
        assert reader.feed(bytes([byte])) == []
    assert reader.feed(EVENT[-1:]) == [ISECNetFrame.parse(EVENT)]
    assert reader.pending_bytes == 0


@pytest.mark.parametrize("command,size", [(PartialStatusRequestCommand, 43), (StatusRequestCommand, 54)])
async def test_tcp_receiver_transaction(command, size):
    """Exercise real asyncio TCP streams against a local simulated central."""
    server = AMTServer(AMTServerConfig(host="127.0.0.1", port=0, response_timeout=1))
    events = []
    completed = asyncio.get_running_loop().create_future()
    disconnected = asyncio.Event()
    payload = bytes(size)

    @server.on_heartbeat
    async def refresh(conn):
        try:
            result = await server.send_command(conn.id, command("1234").build_net_frame())
            completed.set_result(result.raw_frame.content)
        except Exception as err:
            completed.set_exception(err)

    @server.on_frame
    async def receive(conn, frame):
        events.append(frame.command)

    @server.on_disconnect
    async def disconnect(conn):
        disconnected.set()

    writer = None
    await server.start()
    try:
        port = server._server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        async with asyncio.timeout(3):
            writer.write(IDENTIFICATION)
            await writer.drain()
            assert await reader.readexactly(1) == b"\xfe"
            writer.write(b"\xf7")
            await writer.drain()
            request = command("1234").build()
            assert await reader.readexactly(1 + len(request)) == b"\xfe" + request
            writer.write(EVENT + DATED_EVENT + ISECNetFrame.create_mobile_frame(payload).build())
            await writer.drain()
            assert await reader.readexactly(2) == b"\xfe\xfe"
            assert await completed == payload
            # New events continue being confirmed after the initial transaction.
            writer.write(EVENT)
            await writer.drain()
            assert await reader.readexactly(1) == b"\xfe"
            assert events == [0xB0, 0xB4, 0xB0]
    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()
            await asyncio.wait_for(disconnected.wait(), 1)
        await server.stop()


@pytest.mark.parametrize("short_reply", [False, True])
async def test_clear_memory_preserves_events_and_ignores_unrelated_responses(short_reply):
    from custom_components.intelbras_amt.lib.protocol.commands.clear_alarm import ClearAlarmMemoryCommand

    command = ClearAlarmMemoryCommand()
    assert command.build_net_frame().build() == bytes.fromhex("05 e7 01 1c 06 48 4e")
    expected = bytes.fromhex("03 e7 00 00 1b" if short_reply else "05 e7 01 9c 85 4b 4e")
    server = AMTServer(AMTServerConfig(response_timeout=0.2))
    reader = asyncio.StreamReader()
    writer = writer_for(reader)
    done = asyncio.Event()
    received = []
    responses = []
    failures = []

    def respond(data):
        if data == command.build_net_frame().build():
            reader.feed_data(EVENT + b"\xf7" + bytes.fromhex("02 e9 fe ea"))
            reader.feed_data(ISECNetFrame.create_mobile_frame(bytes(43)).build())
            # Correct outer checksum, incorrect inner CRC must not complete clear.
            reader.feed_data(ISECNetFrame(command=0xE7, content=b"\x01\x9c\x00\x00").build())
            reader.feed_data(expected)

    writer.write.side_effect = respond

    @server.on_heartbeat
    async def clear(conn):
        try:
            responses.append(await server.send_command(conn.id, command.build_net_frame()))
        except Exception as err:
            failures.append(err)
        finally:
            done.set()

    @server.on_frame
    async def on_frame(conn, frame):
        received.append(frame)

    reader.feed_data(b"\xf7")
    handler = asyncio.create_task(server._handle_client(reader, writer))
    try:
        await asyncio.wait_for(done.wait(), 1)
        assert not failures
        assert command.is_response(responses[0].raw_frame) is not short_reply
        assert command.is_unconfirmed_response(responses[0].raw_frame) is short_reply
        assert responses[0].raw_frame.build() == expected
        assert ISECNetFrame.parse(EVENT) in received
        assert bytes.fromhex("fe") in [call.args[0] for call in writer.write.call_args_list]
    finally:
        reader.feed_eof()
        await handler
