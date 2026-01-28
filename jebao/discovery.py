"""Jebao dosing pump discovery via UDP broadcast.

This module provides functionality to discover PH803W devices in the local network.
"""

import asyncio
import logging
import socket
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class JebaoDeviceInfo:
    """Information about a discovered Jebao device."""

    ip: str
    device_id: str
    data1: str
    data2: str
    data3: str
    api_server: str
    version: str


class JebaoDiscovery:
    """Discover Jebao PH803W devices via UDP broadcast."""

    UDP_PORT = 12414
    PROBE_MESSAGE = bytes.fromhex("0000000303000003")

    def __init__(self, listen_address: str = "0.0.0.0", timeout: float = 5.0):
        """Initialize discovery client.

        Args:
            listen_address: Address to bind UDP socket to
            timeout: Discovery timeout in seconds
        """
        self.listen_address = listen_address
        self.timeout = timeout
        self.transport: asyncio.DatagramTransport | None = None

    async def discover(self) -> list[JebaoDeviceInfo]:
        """Discover Jebao devices on the network.

        Returns:
            List of discovered devices (deduplicated by device_id)
        """
        devices: list[JebaoDeviceInfo] = []
        seen_devices: set[str] = set()  # Track device_id to avoid duplicates

        # Create UDP socket
        loop = asyncio.get_event_loop()

        class DiscoveryProtocol(asyncio.DatagramProtocol):
            def __init__(self, parent: "JebaoDiscovery") -> None:
                self.parent = parent
                self.devices = devices
                self.seen_devices = seen_devices

            def connection_made(self, transport: asyncio.DatagramTransport) -> None:  # type: ignore[override]
                self.transport = transport
                sock = transport.get_extra_info("socket")
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                log.debug("Sending UDP broadcast probe message")
                transport.sendto(
                    self.parent.PROBE_MESSAGE, ("255.255.255.255", self.parent.UDP_PORT)
                )

            def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:  # type: ignore[override]
                log.debug(f"Received {len(data)} bytes from {addr}: {data.hex()}")
                try:
                    device_info = self._parse_response(data, addr)
                    if device_info:
                        # Check if we've already seen this device
                        if device_info.device_id not in self.seen_devices:
                            log.info(
                                f"Discovered Jebao device {device_info.device_id} at {device_info.ip}"
                            )
                            self.seen_devices.add(device_info.device_id)
                            self.devices.append(device_info)
                        else:
                            log.debug(
                                f"Ignoring duplicate response from {device_info.device_id} at {device_info.ip}"
                            )
                except Exception as e:
                    log.error(f"Error parsing discovery response from {addr}: {e}")

            def _parse_response(self, data: bytes, addr: tuple[str, int]) -> JebaoDeviceInfo | None:
                """Parse device discovery response."""
                if len(data) < 8:
                    return None

                # Check if it's a valid response (message type 0x04)
                if data[7] != 0x04:
                    return None

                try:
                    # Extract device information from response
                    # Protocol format after 8-byte header:
                    # [length_byte][string_bytes...] repeated for each field
                    offset = 9  # Skip 8-byte header + 1 padding byte

                    # Read device ID (length-prefixed string)
                    device_id_len = data[offset]
                    offset += 1
                    device_id = data[offset : offset + device_id_len].decode("ascii")
                    offset += device_id_len

                    # Skip padding
                    offset += 1

                    # Read data1 (MAC address, length-prefixed)
                    data1_len = data[offset]
                    offset += 1
                    data1 = data[offset : offset + data1_len].hex()
                    offset += data1_len

                    # Skip padding
                    offset += 1

                    # Read data2 (length-prefixed hex string)
                    data2_len = data[offset]
                    offset += 1
                    data2 = data[offset : offset + data2_len].hex()
                    offset += data2_len

                    # Skip padding
                    offset += 1

                    # Read data3 (device key, length-prefixed)
                    data3_len = data[offset]
                    offset += 1
                    data3 = data[offset : offset + data3_len].hex()
                    offset += data3_len

                    # Find all null-terminated strings from this point
                    # Look for API server and version
                    remaining = data[offset:]
                    strings = []
                    current_pos = 0
                    while current_pos < len(remaining):
                        # Find next null byte
                        null_pos = remaining.find(b"\x00", current_pos)
                        if null_pos == -1:
                            # No more nulls, take rest as string if it's ASCII
                            try:
                                s = remaining[current_pos:].decode("ascii")
                                if s:
                                    strings.append(s)
                            except UnicodeDecodeError:
                                pass
                            break

                        # Extract string before null
                        try:
                            s = remaining[current_pos:null_pos].decode("ascii")
                            if s:  # Non-empty string
                                strings.append(s)
                        except UnicodeDecodeError:
                            pass

                        current_pos = null_pos + 1

                    # Extract API server and version from found strings
                    api_server = ""
                    version = ""
                    for s in strings:
                        if ":" in s and "." in s:  # Likely API server (has : and .)
                            api_server = s
                        elif s[0].isdigit() or (s.count(".") >= 2):  # Likely version
                            version = s

                    # Fallback: if we didn't find them, use first two non-empty strings
                    if not api_server and len(strings) > 0:
                        api_server = strings[0]
                    if not version and len(strings) > 1:
                        version = strings[1]

                    return JebaoDeviceInfo(
                        ip=addr[0],
                        device_id=device_id,
                        data1=data1,
                        data2=data2,
                        data3=data3,
                        api_server=api_server,
                        version=version,
                    )
                except Exception as e:
                    log.error(f"Error parsing device data: {e}")
                    log.debug(f"Data hex: {data.hex()}")
                    import traceback

                    log.debug(traceback.format_exc())
                    return None

        protocol = DiscoveryProtocol(self)
        transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol,
            local_addr=(self.listen_address, self.UDP_PORT),
        )

        self.transport = transport

        # Wait for responses
        await asyncio.sleep(self.timeout)

        # Close socket
        transport.close()

        return devices


async def discover_jebao_devices(timeout: float = 5.0) -> list[JebaoDeviceInfo]:
    """Convenience function to discover Jebao devices.

    Args:
        timeout: Discovery timeout in seconds

    Returns:
        List of discovered devices
    """
    discovery = JebaoDiscovery(timeout=timeout)
    return await discovery.discover()
