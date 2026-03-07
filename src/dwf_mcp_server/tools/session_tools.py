"""Device session lifecycle tools for Digilent WaveForms."""

from fastmcp import FastMCP

from dwf_mcp_server.session import get_manager


def close_device(device_index: int = 0) -> dict:
    """Close a device session, stopping all outputs (AWG, GPIO, power supply).

    Call this when you are done using the device, or when you want to stop
    all active outputs. The next tool call will automatically re-open the device.

    Args:
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with 'closed' (true if a session was open) and 'device_index'.
    """
    closed = get_manager().release(device_index)
    return {"device_index": device_index, "closed": closed}


def device_session_status(device_index: int = 0) -> dict:
    """Check whether a device session is currently open.

    Args:
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with 'device_index' and 'session_open' (true/false).
    """
    return {
        "device_index": device_index,
        "session_open": get_manager().is_open(device_index),
    }


def register(mcp: FastMCP) -> None:
    """Register session tools with the MCP server."""
    mcp.tool(close_device)
    mcp.tool(device_session_status)
