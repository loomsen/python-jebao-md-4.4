"""Basic example of using the Jebao library."""

import asyncio
import logging

from jebao_md44 import JebaoDevice

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main():
    """Basic usage example."""
    # Replace with your device's IP address
    device_ip = "192.168.1.100"

    # Create device instance
    device = JebaoDevice(ip=device_ip)

    try:
        # Connect to the device
        print(f"Connecting to device at {device_ip}...")
        if not await device.connect():
            print("Failed to connect!")
            return

        # Login to the device
        print("Logging in...")
        if not await device.login():
            print("Failed to login!")
            return

        # Retrieve device data (required before sending commands)
        print("Retrieving device data...")
        data = await device.retrieve_data()
        if data:
            print(f"Device data: {data}")
        else:
            print("Failed to retrieve device data!")
            return

        # Start pump 1
        print("Starting pump 1...")
        if await device.start_pump(1):
            print("Pump 1 started successfully!")
        else:
            print("Failed to start pump 1!")

        # Wait for 2 seconds
        print("Waiting 2 seconds...")
        await asyncio.sleep(2)

        # Stop pump 1
        print("Stopping pump 1...")
        if await device.stop_pump(1):
            print("Pump 1 stopped successfully!")
        else:
            print("Failed to stop pump 1!")

    finally:
        # Always disconnect when done
        print("Disconnecting...")
        await device.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
