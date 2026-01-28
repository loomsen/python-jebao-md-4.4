"""Test suite for Jebao device control."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jebao_md44 import JebaoAction, JebaoDevice


@pytest.fixture
def mock_connection():
    """Create mock reader and writer."""
    reader = AsyncMock()
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return reader, writer


@pytest.mark.asyncio
async def test_device_init():
    """Test device initialization."""
    device = JebaoDevice(ip="192.168.1.100")
    assert device.ip == "192.168.1.100"
    assert device.auto_reconnect is True
    assert device.ping_interval == 4.0
    assert device.connected is False


@pytest.mark.asyncio
async def test_connect_success(mock_connection):
    """Test successful connection."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")

    with patch("asyncio.open_connection", return_value=(reader, writer)):
        result = await device.connect()

    assert result is True
    assert device.connected is True
    assert device.reader == reader
    assert device.writer == writer


@pytest.mark.asyncio
async def test_connect_failure():
    """Test connection failure."""
    device = JebaoDevice(ip="192.168.1.100")

    with patch("asyncio.open_connection", side_effect=ConnectionError("Failed")):
        result = await device.connect()

    assert result is False
    assert device.connected is False


@pytest.mark.asyncio
async def test_login_success(mock_connection):
    """Test successful login."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    # Mock passcode response
    passcode_response = bytearray([0, 0, 0, 3, 10, 0, 0, 0x07] + [0xFF] * 2 + [0xAA] * 10)
    # Mock login response
    login_response = bytearray([0, 0, 0, 3, 5, 0, 0, 0x09, 0x00])

    reader.read = AsyncMock(side_effect=[passcode_response, login_response])

    result = await device.login()

    assert result is True
    assert device.passcode is not None


@pytest.mark.asyncio
async def test_login_not_connected():
    """Test login when not connected."""
    device = JebaoDevice(ip="192.168.1.100")

    with pytest.raises(RuntimeError, match="Not connected"):
        await device.login()


@pytest.mark.asyncio
async def test_retrieve_data_success(mock_connection):
    """Test successful data retrieval."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    # Mock data response with type 0x91 at byte 7
    data_response = bytearray([0, 0, 0, 3, 10, 0, 0, 0x91] + [0xFF] * 20)
    reader.read = AsyncMock(return_value=data_response)

    result = await device.retrieve_data()

    assert result is not None
    assert "raw" in result
    assert "length" in result
    assert result["length"] == len(data_response)


@pytest.mark.asyncio
async def test_start_pump(mock_connection):
    """Test starting a pump."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    # Mock action response
    action_response = bytearray([0, 0, 0, 3, 5, 0, 0, 0x94])
    reader.read = AsyncMock(return_value=action_response)

    result = await device.start_pump(1)

    assert result is True
    assert writer.write.called


@pytest.mark.asyncio
async def test_start_pump_invalid_number(mock_connection):
    """Test starting pump with invalid number."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    with pytest.raises(ValueError, match="Invalid pump number"):
        await device.start_pump(5)


@pytest.mark.asyncio
async def test_stop_pump(mock_connection):
    """Test stopping a pump."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    # Mock action response
    action_response = bytearray([0, 0, 0, 3, 5, 0, 0, 0x94])
    reader.read = AsyncMock(return_value=action_response)

    result = await device.stop_pump(2)

    assert result is True
    assert writer.write.called


@pytest.mark.asyncio
async def test_disconnect(mock_connection):
    """Test disconnection."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    await device.disconnect()

    assert device.connected is False
    assert writer.close.called


@pytest.mark.asyncio
async def test_context_manager(mock_connection):
    """Test context manager usage."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")

    # Mock responses
    passcode_response = bytearray([0, 0, 0, 3, 10, 0, 0, 0x07] + [0xFF] * 2 + [0xAA] * 10)
    login_response = bytearray([0, 0, 0, 3, 5, 0, 0, 0x09, 0x00])
    reader.read = AsyncMock(side_effect=[passcode_response, login_response])

    with patch("asyncio.open_connection", return_value=(reader, writer)):
        async with device as d:
            assert d.connected is True

    assert device.connected is False
    assert writer.close.called


def test_jebao_action_enum():
    """Test JebaoAction enum values."""
    assert JebaoAction.PUMP1_START is not None
    assert JebaoAction.PUMP1_STOP is not None
    assert JebaoAction.PUMP2_START is not None
    assert JebaoAction.PUMP2_STOP is not None


@pytest.mark.asyncio
async def test_login_writer_not_initialized():
    """Test login when writer is not initialized."""
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.writer = None

    with pytest.raises(RuntimeError, match="Writer or reader not initialized"):
        await device.login()


@pytest.mark.asyncio
async def test_retrieve_data_not_connected():
    """Test retrieve_data when not connected."""
    device = JebaoDevice(ip="192.168.1.100")

    with pytest.raises(RuntimeError, match="Not connected"):
        await device.retrieve_data()


@pytest.mark.asyncio
async def test_retrieve_data_short_response(mock_connection):
    """Test retrieve_data with too short response."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    # Mock short response (less than 8 bytes)
    short_response = bytearray([0, 0, 0])
    reader.read = AsyncMock(return_value=short_response)

    result = await device.retrieve_data()

    assert result is None


@pytest.mark.asyncio
async def test_retrieve_data_invalid_type(mock_connection):
    """Test retrieve_data with invalid message type."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    # Mock response with invalid type (not 0x91)
    invalid_response = bytearray([0, 0, 0, 3, 10, 0, 0, 0x99] + [0xFF] * 20)
    reader.read = AsyncMock(return_value=invalid_response)

    result = await device.retrieve_data()

    assert result is None


@pytest.mark.asyncio
async def test_retrieve_data_exception(mock_connection):
    """Test retrieve_data when exception occurs."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    reader.read = AsyncMock(side_effect=Exception("Read error"))

    result = await device.retrieve_data()

    assert result is None


@pytest.mark.asyncio
async def test_send_action_not_connected():
    """Test send_action when not connected."""
    device = JebaoDevice(ip="192.168.1.100")

    with pytest.raises(RuntimeError, match="Not connected"):
        await device.send_action(JebaoAction.PUMP1_START)


@pytest.mark.asyncio
async def test_send_action_writer_not_initialized():
    """Test send_action when writer is not initialized."""
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.writer = None

    with pytest.raises(RuntimeError, match="Writer or reader not initialized"):
        await device.send_action(JebaoAction.PUMP1_START)


@pytest.mark.asyncio
async def test_send_action_timeout(mock_connection):
    """Test send_action with timeout (should still return True)."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    reader.read = AsyncMock(side_effect=TimeoutError("Timeout"))

    result = await device.send_action(JebaoAction.PUMP1_START)

    assert result is True  # Timeout is considered acceptable


@pytest.mark.asyncio
async def test_send_action_connection_error_no_reconnect(mock_connection):
    """Test send_action with connection error and auto_reconnect disabled."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100", auto_reconnect=False)
    device.connected = True
    device.reader = reader
    device.writer = writer

    reader.read = AsyncMock(side_effect=ConnectionError("Connection lost"))

    result = await device.send_action(JebaoAction.PUMP1_START)

    assert result is False
    assert device.connected is False


@pytest.mark.asyncio
async def test_send_action_exception(mock_connection):
    """Test send_action with general exception."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    writer.drain = AsyncMock(side_effect=Exception("General error"))

    result = await device.send_action(JebaoAction.PUMP1_START)

    assert result is False


@pytest.mark.asyncio
async def test_stop_pump_invalid_number(mock_connection):
    """Test stopping pump with invalid number."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    with pytest.raises(ValueError, match="Invalid pump number"):
        await device.stop_pump(0)


@pytest.mark.asyncio
async def test_device_init_custom_params():
    """Test device initialization with custom parameters."""
    device = JebaoDevice(ip="192.168.1.50", auto_reconnect=False, ping_interval=10.0)
    assert device.ip == "192.168.1.50"
    assert device.auto_reconnect is False
    assert device.ping_interval == 10.0


@pytest.mark.asyncio
async def test_disconnect_when_not_connected():
    """Test disconnect when already disconnected."""
    device = JebaoDevice(ip="192.168.1.100")

    await device.disconnect()  # Should not raise any errors

    assert device.connected is False


@pytest.mark.asyncio
async def test_login_failure(mock_connection):
    """Test login failure with invalid response."""
    reader, writer = mock_connection
    device = JebaoDevice(ip="192.168.1.100")
    device.connected = True
    device.reader = reader
    device.writer = writer

    # Mock invalid login response (wrong type)
    passcode_response = bytearray([0, 0, 0, 3, 10, 0, 0, 0x07] + [0xFF] * 2 + [0xAA] * 10)
    invalid_login = bytearray([0, 0, 0, 3, 5, 0, 0, 0xFF, 0x01])  # Wrong type

    reader.read = AsyncMock(side_effect=[passcode_response, invalid_login])

    result = await device.login()

    assert result is False
    assert JebaoAction.PUMP3_START is not None
    assert JebaoAction.PUMP3_STOP is not None
    assert JebaoAction.PUMP4_START is not None
    assert JebaoAction.PUMP4_STOP is not None
