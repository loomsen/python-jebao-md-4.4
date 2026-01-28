"""Example of controlling multiple pumps in sequence."""

import asyncio
import logging

from jebao import JebaoDevice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def dose_sequence(device: JebaoDevice, doses: list[tuple[int, float]]):
    """Run a sequence of pump doses.

    Args:
        device: Connected JebaoDevice instance
        doses: List of (pump_number, duration_seconds) tuples
    """
    for pump_number, duration in doses:
        print(f"Starting pump {pump_number} for {duration} seconds...")
        await device.start_pump(pump_number)
        await asyncio.sleep(duration)
        await device.stop_pump(pump_number)
        print(f"Pump {pump_number} stopped")
        # Small delay between pumps
        await asyncio.sleep(0.5)


async def main():
    """Multiple pump control example."""
    device_ip = "192.168.1.100"

    async with JebaoDevice(ip=device_ip) as device:
        print("Connected!")

        # Initialize device
        await device.retrieve_data()

        # Define dosing sequence: (pump_number, duration_seconds)
        dosing_plan = [
            (1, 2.0),  # Pump 1 for 2 seconds
            (2, 3.0),  # Pump 2 for 3 seconds
            (3, 1.5),  # Pump 3 for 1.5 seconds
            (4, 2.5),  # Pump 4 for 2.5 seconds
        ]

        print("Starting dosing sequence...")
        await dose_sequence(device, dosing_plan)
        print("Dosing sequence complete!")


if __name__ == "__main__":
    asyncio.run(main())
