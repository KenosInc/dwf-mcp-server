"""Device session lifecycle tools for Digilent WaveForms."""

from typing import Any

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


_AWG_CHANNELS = (0, 1)


def _status_name(status: Any) -> str:
    name = getattr(status, "name", None)
    return name.lower() if isinstance(name, str) else str(status)


def _awg_state(device: Any) -> dict:
    out: dict = {}
    for ch_idx in _AWG_CHANNELS:
        key = f"ch{ch_idx + 1}"
        try:
            status = device.analog_output[ch_idx].read_status()
            out[key] = {"status": _status_name(status)}
        except Exception as exc:  # noqa: BLE001
            out[key] = {"error": str(exc)}
    return out


def _scope_state(device: Any) -> dict:
    try:
        status = device.analog_input.read_status(read_data=False)
        return {"status": _status_name(status)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _la_state(device: Any) -> dict:
    try:
        status = device.digital_input.read_status(read_data=False)
        return {"status": _status_name(status)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _power_state(device: Any) -> dict:
    try:
        return {"master_enable": bool(device.analog_io.master_enable)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def device_state(device_index: int = 0) -> dict:
    """Return the current operational state of every sub-instrument on the device.

    Use this to confirm whether AWG outputs, scope captures, or LA captures started
    via generate_waveform(action="start"), analog_capture(action="start"), or
    digital_capture(action="start") are still running across multiple tool
    invocations.

    If the session is closed, returns only `session_open: false` without re-opening
    the device.

    Args:
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with per-sub-instrument status. Each `status` value is one of
        `ready`, `armed`, `done`, `running`, `config`, `prefill`, `wait`.
    """
    try:
        manager = get_manager()
        if not manager.is_open(device_index):
            return {"device_index": device_index, "session_open": False}

        device = manager.acquire(device_index)
        return {
            "device_index": device_index,
            "session_open": True,
            "awg": _awg_state(device),
            "scope": _scope_state(device),
            "logic_analyzer": _la_state(device),
            "power_supply": _power_state(device),
        }
    except Exception as exc:  # noqa: BLE001
        get_manager().release(device_index)
        return {"device_index": device_index, "error": str(exc)}


def register(mcp: FastMCP) -> None:
    """Register session tools with the MCP server."""
    mcp.tool(close_device)
    mcp.tool(device_session_status)
    mcp.tool(device_state)
