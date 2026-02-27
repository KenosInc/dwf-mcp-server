"""Device discovery and information tools for Digilent WaveForms."""

import dwfpy as dwf
from fastmcp import FastMCP


def list_devices() -> list[dict]:
    """List all connected Digilent WaveForms devices.

    Returns a list of device descriptors, each containing:
    - index: device index for use with other tools
    - name: device name (e.g. "Analog Discovery 2")
    - serial: device serial number
    - is_open: whether the device is currently opened by another process
    """
    try:
        return [
            {
                "index": i,
                "name": info.name,
                "serial": info.serial_number,
                "is_open": info.is_open,
            }
            for i, info in enumerate(dwf.Device.enumerate())
        ]
    except Exception as exc:  # noqa: BLE001
        return [{"error": str(exc)}]


def device_info(device_index: int = 0) -> dict:
    """Get detailed information about a specific Digilent WaveForms device.

    Args:
        device_index: Index of the device to query (default: 0, the first device).
    """
    try:
        device_list = list(dwf.Device.enumerate())
        if not device_list:
            return {"error": "No Digilent WaveForms devices found."}
        if device_index < 0 or device_index >= len(device_list):
            return {
                "error": (
                    f"Device index {device_index} out of range "
                    f"(found {len(device_list)} device(s))."
                )
            }
        info = device_list[device_index]
        return {
            "index": device_index,
            "name": info.name,
            "serial": info.serial_number,
            "is_open": info.is_open,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def register(mcp: FastMCP) -> None:
    """Register device tools with the MCP server."""
    mcp.tool(list_devices)
    mcp.tool(device_info)
