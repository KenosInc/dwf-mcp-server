"""Static digital I/O (GPIO) tools for Digilent WaveForms."""

import dwfpy as dwf
from fastmcp import FastMCP

_MIN_PIN = 0
_MAX_PIN = 15  # AD2/AD3 have 16 DIO pins (DIO0-DIO15)


def gpio_read(pin: int, device_index: int = 0) -> dict:
    """Read the logic level of a digital I/O pin.

    The pin is automatically configured as an input before reading.

    Args:
        pin: DIO pin number (0-15), matching hardware labels DIO0-DIO15.
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with 'pin' and 'value' (true = HIGH, false = LOW).
    """
    if not (_MIN_PIN <= pin <= _MAX_PIN):
        return {"error": f"Pin {pin} out of range (must be {_MIN_PIN}-{_MAX_PIN})."}

    try:
        with dwf.Device(device_id=device_index) as device:
            dio = device.digital_io
            dio[pin].setup(enabled=False, configure=True)
            dio.read_status()
            value = dio[pin].input_state

        return {"pin": pin, "value": value}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def gpio_write(pin: int, value: bool, device_index: int = 0) -> dict:
    """Set the logic level of a digital I/O pin.

    The pin is automatically configured as an output before writing.

    Args:
        pin: DIO pin number (0-15), matching hardware labels DIO0-DIO15.
        value: Logic level to set (true = HIGH, false = LOW).
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with 'pin' and 'value' (the level that was set).
    """
    if not (_MIN_PIN <= pin <= _MAX_PIN):
        return {"error": f"Pin {pin} out of range (must be {_MIN_PIN}-{_MAX_PIN})."}

    try:
        with dwf.Device(device_id=device_index) as device:
            dio = device.digital_io
            dio[pin].setup(enabled=True, state=value, configure=True)

        return {"pin": pin, "value": value}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def register(mcp: FastMCP) -> None:
    """Register GPIO tools with the MCP server."""
    mcp.tool(gpio_read)
    mcp.tool(gpio_write)
