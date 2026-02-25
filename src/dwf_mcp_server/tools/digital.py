"""Digital logic analyzer tools for Digilent WaveForms."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def digital_capture(
    channels: list[int] | None = None,
    sample_rate: float = 1_000_000.0,
    duration: float = 0.001,
    device_index: int = 0,
) -> dict:
    """Capture digital logic signals using the logic analyzer.

    Args:
        channels: List of channel indices to capture (0-based). None = all channels
            (default: None).
        sample_rate: Sampling rate in Hz (default: 1 MHz).
        duration: Capture duration in seconds (default: 1 ms → 1000 samples at 1 MHz).
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with 'samples' (list of ints, each bit = one channel) and metadata.
        Bit 0 of each sample corresponds to channel 0, bit 1 to channel 1, etc.
    """
    try:
        import dwfpy as dwf  # noqa: PLC0415

        buffer_size = int(sample_rate * duration)

        with dwf.Device(device_id=device_index) as device:
            la = device.logic_analyzer
            la.setup(sample_rate=sample_rate, buffer_size=buffer_size)
            la.single()

            timeout = max(duration * 10, 5.0)
            deadline = time.monotonic() + timeout
            while not la.is_done():
                if time.monotonic() > deadline:
                    return {"error": "Capture timed out."}
                time.sleep(0.001)

            raw: list[int] = la.get_data().tolist()

        # Filter to requested channels if specified
        if channels is not None:
            mask = sum(1 << ch for ch in channels)
            filtered = [s & mask for s in raw]
        else:
            filtered = raw
            channels = list(range(16))  # Analog Discovery 2 has 16 digital channels

        return {
            "channels": channels,
            "sample_rate": sample_rate,
            "duration": duration,
            "sample_count": len(filtered),
            "samples": filtered,
        }
    except OSError as exc:
        return {"error": f"Failed to load libdwf: {exc}. Mount libdwf.so from the host."}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def register(mcp: FastMCP) -> None:
    """Register digital tools with the MCP server."""
    mcp.tool(digital_capture)
