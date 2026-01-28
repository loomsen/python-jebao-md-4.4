# Release Notes - v0.1.0

## 🎉 Initial Release

We're excited to announce the first official release of the **Jebao Python Library** - a modern, async Python library for controlling Jebao MD 4.4 dosing pumps via TCP/IP!

This library fills a gap in the Python ecosystem by providing a native implementation for Jebao pump control (previously only Node.js implementations existed).

## ✨ Features

### Device Control
- **Async/await API** - Built on Python's asyncio for non-blocking I/O
- **Full pump control** - Start and stop individual pumps (1-4)
- **Device status monitoring** - Query device data and sensor readings
- **Context manager support** - Clean resource management with `async with`
- **Automatic reconnection** - Resilient connection handling with configurable retry logic
- **Keep-alive mechanism** - Ping-pong protocol to maintain connections

### Device Discovery
- **UDP broadcast discovery** - Automatically find Jebao devices on your network
- **Device information parsing** - Extract IP, device ID, MAC address, firmware version
- **Duplicate detection** - Smart deduplication of multiple responses
- **Configurable timeout** - Adjust discovery duration to your network

### Developer Experience
- **Type-safe** - Full type hints with mypy validation
- **Well-tested** - 78% code coverage with 35 comprehensive test cases
- **Modern tooling** - Uses `uv` for fast dependency management
- **Code quality** - Linted with ruff and formatted with black
- **Excellent documentation** - Comprehensive README with examples and API reference

## 📦 Installation

```bash
pip install jebao-md44
```

Or with uv for development:
```bash
git clone https://github.com/loomsen/python-jebao-md-4.4.git
cd python-jebao-md-4.4
uv sync --group dev
```

## 🚀 Quick Start

```python
import asyncio
from jebao_md44 import JebaoDevice

async def main():
    async with JebaoDevice(ip="192.168.1.100") as device:
        # Retrieve device data
        data = await device.retrieve_data()

        # Start pump 1 for 2 seconds
        await device.start_pump(1)
        await asyncio.sleep(2)
        await device.stop_pump(1)

asyncio.run(main())
```

## 📋 What's Included

- **Core library** (`jebao/`) - Device control and discovery
- **Comprehensive tests** (`tests/`) - 35 test cases covering edge cases
- **Usage examples** (`examples/`) - 4 examples showing different usage patterns
- **Complete documentation** - README with API reference, troubleshooting guide
- **CI/CD pipeline** - GitHub Actions for automated testing and PyPI publishing

## 🔧 Technical Details

- **Python**: Requires Python 3.11+
- **Dependencies**: Zero runtime dependencies (only stdlib asyncio)
- **Protocol**: Implements complete Jebao TCP/IP protocol (ports 12414/12416)
- **Architecture**: Clean separation of concerns (device control, discovery, examples)
- **Quality**: Passes ruff, black, and mypy with strict settings

## 📊 Test Coverage

```
jebao/__init__.py      100%
jebao/device.py         73%
jebao/discovery.py      89%
────────────────────────────
TOTAL                   78%
```

All 35 tests passing ✅

## 🙏 Acknowledgments

This project is heavily inspired by and builds upon the excellent work from:
- [tancou/jebao-dosing-pump-md-4.4](https://github.com/tancou/jebao-dosing-pump-md-4.4) - Original protocol reverse engineering

## 📝 Notes

- This is an initial release - feedback and contributions are welcome!
- Tested with Jebao PH803W dosing pumps
- Protocol reverse-engineered through network analysis
- No affiliation with Jebao/Jecod

## 🐛 Known Issues

None at this time! If you encounter any issues, please [report them on GitHub](https://github.com/loomsen/python-jebao-md-4.4/issues).

## 🔮 Future Plans

- Additional pump models support
- Enhanced error recovery
- More detailed device status parsing
- Integration examples (Home Assistant, etc.)

---

**Full Changelog**: https://github.com/loomsen/python-jebao-md-4.4/commits/v0.1.0
