"""Static digital I/O (GPIO) tools for Digilent WaveForms."""

import dwfpy as dwf
from fastmcp import FastMCP

_MIN_PIN = 1
_MAX_PIN = 16  # AD2/AD3 have 16 DIO pins


def gpio_read(pin: int, device_index: int = 0) -> dict:
    """Read the logic level of a digital I/O pin.

    The pin is automatically configured as an input before reading.

    Args:
        pin: DIO pin number (1-16). Converted to 0-based internally.
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with 'pin' (1-based) and 'value' (true = HIGH, false = LOW).
    """
    if not (_MIN_PIN <= pin <= _MAX_PIN):
        return {"error": f"Pin {pin} out of range (must be {_MIN_PIN}-{_MAX_PIN})."}

    pin_idx = pin - 1

    try:
        with dwf.Device(device_id=device_index) as device:
            dio = device.digital_io
            dio[pin_idx].setup(enabled=False, configure=True)
            dio.read_status()
            value = dio[pin_idx].input_state

        return {"pin": pin, "value": value}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def gpio_write(pin: int, value: bool, device_index: int = 0) -> dict:
    """Set the logic level of a digital I/O pin.

    The pin is automatically configured as an output before writing.

    Args:
        pin: DIO pin number (1-16). Converted to 0-based internally.
        value: Logic level to set (true = HIGH, false = LOW).
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with 'pin' (1-based) and 'value' (the level that was set).
    """
    if not (_MIN_PIN <= pin <= _MAX_PIN):
        return {"error": f"Pin {pin} out of range (must be {_MIN_PIN}-{_MAX_PIN})."}

    pin_idx = pin - 1

    try:
        with dwf.Device(device_id=device_index) as device:
            dio = device.digital_io
            dio[pin_idx].setup(enabled=True, state=value, configure=True)

        return {"pin": pin, "value": value}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def register(mcp: FastMCP) -> None:
    """Register GPIO tools with the MCP server."""
    mcp.tool(gpio_read)
    mcp.tool(gpio_write)
