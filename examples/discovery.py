"""Example: Discover Jebao devices on your network."""

import asyncio
import logging

from jebao import discover_jebao_devices

# Enable debug logging to see discovery process
logging.basicConfig(level=logging.INFO)


async def main():
    """Discover all Jebao devices on the local network."""
    print("Discovering Jebao devices...")
    print("Waiting 5 seconds for responses...\n")

    devices = await discover_jebao_devices(timeout=5.0)

    if not devices:
        print("No devices found.")
        return

    print(f"Found {len(devices)} device(s):\n")

    for i, device in enumerate(devices, 1):
        print(f"Device {i}:")
        print(f"  Device ID: {device.device_id}")
        print(f"  IP Address: {device.ip}")
        print(f"  Version: {device.version}")
        print(f"  API Server: {device.api_server}")
        print(f"  Data1 (MAC): {device.data1}")
        print(f"  Data2: {device.data2}")
        print(f"  Data3 (Key): {device.data3}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
