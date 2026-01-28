"""Jebao dosing pump device control via TCP.

This module provides functionality to control PH803W dosing pumps.
"""

import asyncio
import logging
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


class JebaoAction(Enum):
    """Available actions for Jebao dosing pumps."""

    # Pump 1 (index 0)
    PUMP1_START = bytes.fromhex("000000039a030000930000000001000002000200" + "00" * 396)
    PUMP1_STOP = bytes.fromhex("000000039a030000930000000001000002000000" + "00" * 396)

    # Pump 2 (index 1)
    PUMP2_START = bytes.fromhex("000000039a030000930000000001000004000400" + "00" * 396)
    PUMP2_STOP = bytes.fromhex("000000039a030000930000000001000004000000" + "00" * 396)

    # Pump 3 (index 2)
    PUMP3_START = bytes.fromhex("000000039a030000930000000001000008000800" + "00" * 396)
    PUMP3_STOP = bytes.fromhex("000000039a030000930000000001000008000000" + "00" * 396)

    # Pump 4 (index 3)
    PUMP4_START = bytes.fromhex("000000039a030000930000000001000010001000" + "00" * 396)
    PUMP4_STOP = bytes.fromhex("000000039a030000930000000001000010000000" + "00" * 396)


class JebaoDevice:
    """Control Jebao PH803W dosing pump via TCP."""

    TCP_PORT = 12416
    PASSCODE_REQUEST = bytes.fromhex("0000000303000006")
    PING_MESSAGE = bytes.fromhex("0000000303000015")
    DATA_REQUEST = bytes.fromhex("000000030400009002")

    def __init__(
        self,
        ip: str,
        auto_reconnect: bool = True,
        ping_interval: float = 4.0,
    ):
        """Initialize Jebao device connection.

        Args:
            ip: IP address of the device
            auto_reconnect: Whether to automatically reconnect on connection loss
            ping_interval: Interval for ping-pong keep-alive in seconds (0 to disable)
        """
        self.ip = ip
        self.auto_reconnect = auto_reconnect
        self.ping_interval = ping_interval

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.passcode: Optional[bytes] = None
        self.connected = False
        self.ping_task: Optional[asyncio.Task] = None
        self.read_lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Connect to the device.

        Returns:
            True if connection successful
        """
        try:
            log.info(f"Connecting to Jebao device at {self.ip}:{self.TCP_PORT}")
            self.reader, self.writer = await asyncio.open_connection(
                self.ip,
                self.TCP_PORT,
            )
            self.connected = True
            log.info(f"Connected to Jebao device at {self.ip}")
            return True
        except Exception as e:
            log.error(f"Failed to connect to Jebao device at {self.ip}: {e}")
            return False

    async def login(self) -> bool:
        """Authenticate with the device.

        Returns:
            True if login successful
        """
        if not self.connected:
            raise RuntimeError("Not connected to device")

        if not self.writer or not self.reader:
            raise RuntimeError("Writer or reader not initialized")

        try:
            # Request passcode
            log.debug("Requesting device passcode")
            self.writer.write(self.PASSCODE_REQUEST)
            await self.writer.drain()

            # Read passcode response (type 0x07)
            async with self.read_lock:
                response = await self.reader.read(1024)
            if len(response) < 8 or response[7] != 0x07:
                log.error("Invalid passcode response")
                return False

            # Extract passcode (10 bytes starting at offset 10)
            self.passcode = response[10:20]
            log.debug(f"Received passcode: {self.passcode.hex()}")

            # Send login request (type 0x08)
            login_request = bytes.fromhex("00000003 0f 000008 000a") + self.passcode
            login_request = login_request.replace(b" ", b"")  # Remove spaces
            self.writer.write(login_request)
            await self.writer.drain()

            # Read login response (type 0x09)
            async with self.read_lock:
                response = await self.reader.read(1024)
            if len(response) < 9 or response[7] != 0x09:
                log.error("Invalid login response")
                return False

            # Check if login successful (last byte should be 0x00)
            if response[8] == 0x00:
                log.info("Login successful")
                # Start ping-pong keep-alive (if interval > 0)
                if self.ping_interval > 0:
                    self.ping_task = asyncio.create_task(self._ping_loop())
                return True
            else:
                log.error("Login failed")
                return False

        except Exception as e:
            log.error(f"Login failed: {e}")
            return False

    async def retrieve_data(self) -> Optional[dict]:
        """Retrieve device data (sensor readings, pump status, etc.).

        This method must be called before sending pump commands to initialize
        the device communication.

        Returns:
            Dictionary with device data or None on error
        """
        if not self.connected:
            raise RuntimeError("Not connected to device")

        if not self.writer or not self.reader:
            raise RuntimeError("Writer or reader not initialized")

        try:
            # Send data request (type 0x90)
            log.debug(
                f"Sending retrieve_data request, writer={self.writer}, connected={self.connected}"
            )
            self.writer.write(self.DATA_REQUEST)
            await self.writer.drain()
            log.debug("Data request sent, waiting for response...")

            # Give device time to prepare response
            await asyncio.sleep(0.2)

            # Read data response (type 0x91)
            async with self.read_lock:
                log.debug("Attempting to read response...")
                response = await self.reader.read(1024)
                log.debug(f"Read completed, got {len(response)} bytes")

            log.info(f"Data response received: length={len(response)}, hex={response[:50].hex()}")

            # Response format: Message type 0x91 can be at byte 7 or 8 depending on response length
            # Short responses: 00 00 00 03 LL 00 00 91 ... (type at byte 7)
            # Long responses:  00 00 00 03 LL ?? 00 00 91 ... (type at byte 8)
            if len(response) < 8:
                log.error(
                    f"Response too short: {len(response)} bytes, expected at least 8. Hex: {response.hex()}"
                )
                return None

            # Check both byte 7 and 8 for message type 0x91
            msg_type_pos = None
            if response[7] == 0x91:
                msg_type_pos = 7
            elif len(response) > 8 and response[8] == 0x91:
                msg_type_pos = 8

            if msg_type_pos is None:
                log.error(
                    f"Invalid data response: expected type 0x91 at byte 7 or 8, got {hex(response[7])} at byte 7, {hex(response[8]) if len(response) > 8 else 'N/A'} at byte 8. Full response: {response[:20].hex()}"
                )
                return None

            # Parse data response
            # This contains sensor readings and pump status
            # Format depends on device configuration
            data = {
                "raw": response.hex(),
                "length": len(response),
            }

            log.debug(f"Received device data: {data}")
            return data

        except Exception as e:
            log.error(f"Failed to retrieve data: {e}")
            return None

    async def send_action(self, action: JebaoAction) -> bool:
        """Send an action command to the device (start/stop pump).

        Args:
            action: Action to perform

        Returns:
            True if action sent successfully
        """
        if not self.connected:
            raise RuntimeError("Not connected to device")

        if not self.writer or not self.reader:
            raise RuntimeError("Writer or reader not initialized")

        try:
            log.info(f"Sending action: {action.name}")
            self.writer.write(action.value)
            await self.writer.drain()
            log.debug("Action sent, waiting for response...")

            # Give device time to prepare response
            await asyncio.sleep(0.2)

            # Wait for acknowledgment (0x94 response type)
            async with self.read_lock:
                log.debug("Attempting to read action response...")
                response = await self.reader.read(1024)
                log.debug(f"Read completed, got {len(response)} bytes")

            # Check if action was acknowledged (response type 0x94 can be at byte 7 or 8)
            if len(response) >= 8:
                # Message type can be at byte 7 or 8 depending on response format
                msg_type = (
                    response[7]
                    if response[7] == 0x94
                    else (response[8] if len(response) > 8 else None)
                )
                if msg_type == 0x94:
                    log.info(f"Action acknowledged (0x94), length={len(response)}")
                elif response[7] == 0x91 or (len(response) > 8 and response[8] == 0x91):
                    # Device sent data update (0x91) instead of action ack - this is normal
                    log.debug(f"Received data update (0x91) after action, length={len(response)}")
                else:
                    log.warning(
                        f"Unexpected response: byte7={hex(response[7])}, byte8={hex(response[8]) if len(response) > 8 else 'N/A'}"
                    )
            else:
                log.warning(f"Response too short: {len(response)} bytes")
            return True

        except asyncio.TimeoutError:
            log.warning("Action acknowledgment timeout, but action may have succeeded")
            return True
        except (ConnectionError, BrokenPipeError, OSError) as e:
            log.warning(f"Connection error during action: {e}. Attempting to reconnect...")
            # Mark as disconnected and try to reconnect
            self.connected = False
            if self.writer:
                try:
                    self.writer.close()
                    await self.writer.wait_closed()
                except Exception:
                    pass  # Ignore errors during cleanup

            if self.auto_reconnect:
                try:
                    await asyncio.sleep(1)  # Brief delay before reconnect
                    log.info("Attempting to reconnect to device...")
                    if await self.connect():
                        log.info("Connection re-established, performing login...")
                        if await self.login():
                            log.info("Reconnected and logged in successfully, retrying action")
                            # Retry the action once after reconnecting
                            if self.writer and self.reader:
                                self.writer.write(action.value)
                                await self.writer.drain()
                                async with self.read_lock:
                                    response = await asyncio.wait_for(
                                        self.reader.read(1024), timeout=1.0
                                    )
                                log.info("Action sent successfully after reconnection")
                                return True
                        else:
                            log.error("Failed to login after reconnection")
                    else:
                        log.error("Failed to reconnect to device")
                except Exception as reconnect_error:
                    log.error(f"Failed to reconnect and retry action: {reconnect_error}")
            return False
        except Exception as e:
            log.error(f"Failed to send action: {e}")
            return False

    async def start_pump(self, pump_number: int) -> bool:
        """Start a specific pump.

        Args:
            pump_number: Pump number (1-4)

        Returns:
            True if successful

        Raises:
            ValueError: If pump_number is not 1-4
        """
        log.info(f"start_pump called for pump {pump_number}")
        action_map = {
            1: JebaoAction.PUMP1_START,
            2: JebaoAction.PUMP2_START,
            3: JebaoAction.PUMP3_START,
            4: JebaoAction.PUMP4_START,
        }

        action = action_map.get(pump_number)
        if not action:
            raise ValueError(f"Invalid pump number: {pump_number}. Must be 1-4.")

        return await self.send_action(action)

    async def stop_pump(self, pump_number: int) -> bool:
        """Stop a specific pump.

        Args:
            pump_number: Pump number (1-4)

        Returns:
            True if successful

        Raises:
            ValueError: If pump_number is not 1-4
        """
        action_map = {
            1: JebaoAction.PUMP1_STOP,
            2: JebaoAction.PUMP2_STOP,
            3: JebaoAction.PUMP3_STOP,
            4: JebaoAction.PUMP4_STOP,
        }

        action = action_map.get(pump_number)
        if not action:
            raise ValueError(f"Invalid pump number: {pump_number}. Must be 1-4.")

        return await self.send_action(action)

    async def _ping_loop(self) -> None:
        """Background task to send ping-pong keep-alive messages."""
        try:
            while self.connected:
                await asyncio.sleep(self.ping_interval)

                if not self.connected:
                    break

                if not self.writer or not self.reader:
                    break

                try:
                    log.debug("Sending ping")
                    self.writer.write(self.PING_MESSAGE)
                    await self.writer.drain()

                    # Read pong response (type 0x16)
                    async with self.read_lock:
                        response = await asyncio.wait_for(
                            self.reader.read(1024),
                            timeout=2.0,
                        )
                    if len(response) >= 8 and response[7] == 0x16:
                        log.debug("Received pong")
                    else:
                        log.warning("Invalid pong response")

                except asyncio.TimeoutError:
                    log.warning("Ping timeout")
                except Exception as e:
                    log.error(f"Ping error: {e}")
                    if self.auto_reconnect:
                        await self._reconnect()
                    break
        except asyncio.CancelledError:
            log.debug("Ping loop cancelled")

    async def _reconnect(self) -> None:
        """Attempt to reconnect to the device."""
        log.info("Attempting to reconnect...")
        self.connected = False

        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

        await asyncio.sleep(5)

        if await self.connect():
            if await self.login():
                log.info("Reconnected successfully")
            else:
                log.error("Failed to login after reconnect")

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        log.info("Disconnecting from device")
        self.connected = False

        if self.ping_task:
            self.ping_task.cancel()
            try:
                await self.ping_task
            except asyncio.CancelledError:
                pass

        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

    async def __aenter__(self) -> "JebaoDevice":
        """Async context manager entry."""
        await self.connect()
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()
