"""Tests for Jebao device discovery."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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
