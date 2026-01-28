"""Tests for Jebao device discovery."""

from unittest.mock import MagicMock, patch

import pytest

from jebao.discovery import JebaoDeviceInfo, JebaoDiscovery, discover_jebao_devices


@pytest.mark.asyncio
async def test_discover_jebao_devices():
    """Test convenience function for discovery."""
    with patch.object(JebaoDiscovery, "discover") as mock_discover:
        mock_discover.return_value = [
            JebaoDeviceInfo(
                ip="192.168.1.100",
                device_id="TEST123",
                data1="aabbccddeeff",
                data2="11223344",
                data3="55667788",
                api_server="api.example.com:8080",
                version="1.0.0",
            )
        ]

        devices = await discover_jebao_devices(timeout=1.0)

        assert len(devices) == 1
        assert devices[0].ip == "192.168.1.100"
        assert devices[0].device_id == "TEST123"


@pytest.mark.asyncio
async def test_jebao_discovery_init():
    """Test JebaoDiscovery initialization."""
    discovery = JebaoDiscovery(listen_address="0.0.0.0", timeout=5.0)
    assert discovery.listen_address == "0.0.0.0"
    assert discovery.timeout == 5.0


@pytest.mark.asyncio
async def test_jebao_discovery_no_devices():
    """Test discovery when no devices respond."""
    discovery = JebaoDiscovery(timeout=0.1)

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_transport = MagicMock()
        mock_transport.close = MagicMock()

        async def mock_create_endpoint(protocol_factory, **kwargs):
            protocol = protocol_factory()
            return mock_transport, protocol

        mock_loop.return_value.create_datagram_endpoint = mock_create_endpoint

        devices = await discovery.discover()

        assert devices == []
        mock_transport.close.assert_called_once()


@pytest.mark.asyncio
async def test_jebao_device_info_dataclass():
    """Test JebaoDeviceInfo dataclass."""
    device_info = JebaoDeviceInfo(
        ip="192.168.1.100",
        device_id="JEBAO001",
        data1="aabbccddeeff",
        data2="11223344",
        data3="55667788",
        api_server="api.jebao.com:443",
        version="2.1.0",
    )

    assert device_info.ip == "192.168.1.100"
    assert device_info.device_id == "JEBAO001"
    assert device_info.data1 == "aabbccddeeff"
    assert device_info.version == "2.1.0"


@pytest.mark.asyncio
async def test_discovery_protocol_connection_made():
    """Test that discovery protocol sends broadcast on connection."""
    discovery = JebaoDiscovery(timeout=1.0)

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_transport = MagicMock()
        mock_socket = MagicMock()
        mock_transport.get_extra_info = MagicMock(return_value=mock_socket)
        mock_transport.sendto = MagicMock()
        mock_transport.close = MagicMock()

        captured_protocol = None

        async def mock_create_endpoint(protocol_factory, **kwargs):
            nonlocal captured_protocol
            captured_protocol = protocol_factory()
            captured_protocol.connection_made(mock_transport)
            return mock_transport, captured_protocol

        mock_loop.return_value.create_datagram_endpoint = mock_create_endpoint

        await discovery.discover()

        # Verify broadcast socket option was set
        mock_socket.setsockopt.assert_called()

        # Verify probe message was sent
        mock_transport.sendto.assert_called_once()
        call_args = mock_transport.sendto.call_args
        assert call_args[0][0] == discovery.PROBE_MESSAGE
        assert call_args[0][1] == ("255.255.255.255", discovery.UDP_PORT)


@pytest.mark.asyncio
async def test_discovery_parse_invalid_response():
    """Test parsing invalid discovery response."""
    discovery = JebaoDiscovery(timeout=0.1)

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_transport = MagicMock()
        mock_transport.close = MagicMock()

        captured_protocol = None

        async def mock_create_endpoint(protocol_factory, **kwargs):
            nonlocal captured_protocol
            captured_protocol = protocol_factory()
            # Simulate receiving invalid data (too short)
            captured_protocol.datagram_received(b"\x00\x00", ("192.168.1.100", 12414))
            # Simulate receiving data with wrong type
            wrong_type = bytearray([0, 0, 0, 0, 0, 0, 0, 0x99])
            captured_protocol.datagram_received(wrong_type, ("192.168.1.101", 12414))
            return mock_transport, captured_protocol

        mock_loop.return_value.create_datagram_endpoint = mock_create_endpoint

        devices = await discovery.discover()

        assert devices == []


@pytest.mark.asyncio
async def test_discovery_parse_valid_response():
    """Test parsing valid discovery response."""
    discovery = JebaoDiscovery(timeout=0.1)

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_transport = MagicMock()
        mock_transport.close = MagicMock()

        captured_protocol = None

        async def mock_create_endpoint(protocol_factory, **kwargs):
            nonlocal captured_protocol
            captured_protocol = protocol_factory()

            # Create valid discovery response
            # Format: header(8) + padding(1) + device_id + data fields
            response = bytearray([0, 0, 0, 0, 0, 0, 0, 0x04])  # Header with type 0x04
            response.append(0)  # Padding

            # Device ID (length-prefixed)
            device_id = b"TEST_DEVICE"
            response.append(len(device_id))
            response.extend(device_id)
            response.append(0)  # Padding

            # MAC address (data1)
            mac = bytes.fromhex("aabbccddeeff")
            response.append(len(mac))
            response.extend(mac)
            response.append(0)  # Padding

            # Data2
            data2 = bytes.fromhex("11223344")
            response.append(len(data2))
            response.extend(data2)
            response.append(0)  # Padding

            # Device key (data3)
            key = bytes.fromhex("55667788")
            response.append(len(key))
            response.extend(key)

            # API server and version (null-terminated strings)
            response.extend(b"api.test.com:8080\x00")
            response.extend(b"1.2.3\x00")

            captured_protocol.datagram_received(bytes(response), ("192.168.1.100", 12414))
            return mock_transport, captured_protocol

        mock_loop.return_value.create_datagram_endpoint = mock_create_endpoint

        devices = await discovery.discover()

        assert len(devices) == 1
        assert devices[0].device_id == "TEST_DEVICE"
        assert devices[0].ip == "192.168.1.100"
        assert devices[0].data1 == "aabbccddeeff"
        assert devices[0].api_server == "api.test.com:8080"
        assert devices[0].version == "1.2.3"


@pytest.mark.asyncio
async def test_discovery_deduplicate_devices():
    """Test that duplicate device responses are deduplicated."""
    discovery = JebaoDiscovery(timeout=0.1)

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_transport = MagicMock()
        mock_transport.close = MagicMock()

        captured_protocol = None

        async def mock_create_endpoint(protocol_factory, **kwargs):
            nonlocal captured_protocol
            captured_protocol = protocol_factory()

            # Create valid discovery response
            response = bytearray([0, 0, 0, 0, 0, 0, 0, 0x04, 0])
            device_id = b"DUPLICATE"
            response.append(len(device_id))
            response.extend(device_id)
            response.append(0)
            mac = bytes.fromhex("aabbccddee11")
            response.append(len(mac))
            response.extend(mac)
            response.append(0)
            data2 = bytes.fromhex("11223344")
            response.append(len(data2))
            response.extend(data2)
            response.append(0)
            key = bytes.fromhex("55667788")
            response.append(len(key))
            response.extend(key)

            # Send same device twice
            captured_protocol.datagram_received(bytes(response), ("192.168.1.100", 12414))
            captured_protocol.datagram_received(bytes(response), ("192.168.1.100", 12414))
            return mock_transport, captured_protocol

        mock_loop.return_value.create_datagram_endpoint = mock_create_endpoint

        devices = await discovery.discover()

        # Should only have one device despite two responses
        assert len(devices) == 1
        assert devices[0].device_id == "DUPLICATE"


@pytest.mark.asyncio
async def test_discovery_parse_error_handling():
    """Test that parse errors are handled gracefully."""
    discovery = JebaoDiscovery(timeout=0.1)

    with patch("asyncio.get_event_loop") as mock_loop:
        mock_transport = MagicMock()
        mock_transport.close = MagicMock()

        captured_protocol = None

        async def mock_create_endpoint(protocol_factory, **kwargs):
            nonlocal captured_protocol
            captured_protocol = protocol_factory()

            # Create malformed response (valid header but corrupted data)
            response = bytearray([0, 0, 0, 0, 0, 0, 0, 0x04, 0])
            # Add length that exceeds actual data
            response.append(255)  # Claims 255 bytes follow
            response.extend(b"short")  # But only has 5 bytes

            captured_protocol.datagram_received(bytes(response), ("192.168.1.100", 12414))
            return mock_transport, captured_protocol

        mock_loop.return_value.create_datagram_endpoint = mock_create_endpoint

        devices = await discovery.discover()

        # Should handle error gracefully and return empty list
        assert devices == []
