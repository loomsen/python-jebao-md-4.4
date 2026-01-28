"""Example using context manager for automatic connection management."""

import asyncio
import logging

from jebao import JebaoDevice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main():
    """Context manager usage example."""
    device_ip = "192.168.1.100"

    print(f"Connecting to device at {device_ip}...")

    # Use context manager - automatically connects, logs in, and disconnects
    async with JebaoDevice(ip=device_ip) as device:
        print("Connected and logged in!")

        # Retrieve device data
        print("Retrieving device data...")
        await device.retrieve_data()

        # Control pump 2
        print("Starting pump 2...")
        await device.start_pump(2)

        print("Waiting 5 seconds...")
        await asyncio.sleep(5)

        print("Stopping pump 2...")
        await device.stop_pump(2)

    # Device is automatically disconnected here
    print("Disconnected automatically!")


if __name__ == "__main__":
    asyncio.run(main())
