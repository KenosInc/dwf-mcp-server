"""Power supply control tools for Digilent WaveForms devices."""

import dwfpy as dwf
from fastmcp import FastMCP


def power_supply(
    positive_voltage: float = 5.0,
    negative_voltage: float = -5.0,
    enabled: bool = True,
    device_index: int = 0,
) -> dict:
    """Control the programmable power supply (V+ / V-) on a WaveForms device.

    Args:
        positive_voltage: V+ output voltage in Volts, 0.5 to 5.0 (default: 5.0).
        negative_voltage: V- output voltage in Volts, -5.0 to -0.5 (default: -5.0).
        enabled: Enable (True) or disable (False) the power supply (default: True).
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with the applied settings or an error message.
    """
    if enabled:
        if not (0.5 <= positive_voltage <= 5.0):
            return {"error": f"positive_voltage {positive_voltage} out of range [0.5, 5.0]."}
        if not (-5.0 <= negative_voltage <= -0.5):
            return {"error": f"negative_voltage {negative_voltage} out of range [-5.0, -0.5]."}

    try:
        with dwf.Device(device_id=device_index) as device:
            aio = device.analog_io

            if enabled:
                # Channel 0 = V+: node 0 = enable, node 1 = voltage
                aio[0][1].value = positive_voltage
                aio[0][0].value = True
                # Channel 1 = V-: node 0 = enable, node 1 = voltage
                aio[1][1].value = negative_voltage
                aio[1][0].value = True
            else:
                aio[0][0].value = False
                aio[1][0].value = False

            aio.master_enable = enabled

        result: dict = {"enabled": enabled}
        if enabled:
            result["positive_voltage"] = positive_voltage
            result["negative_voltage"] = negative_voltage
        return result
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def register(mcp: FastMCP) -> None:
    """Register power supply tools with the MCP server."""
    mcp.tool(power_supply)
