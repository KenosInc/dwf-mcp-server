"""Digital logic analyzer tools for Digilent WaveForms."""

import time
from typing import Literal

import dwfpy as dwf
from fastmcp import FastMCP

from dwf_mcp_server.session import get_manager


def digital_capture(
    channels: list[int] | None = None,
    sample_rate: float = 1_000_000.0,
    duration: float = 0.001,
    buffer_size: int | None = None,
    action: Literal["single", "start", "read", "stop"] = "single",
    device_index: int = 0,
) -> dict:
    """Capture digital logic signals using the logic analyzer.

    The `action` parameter selects the capture lifecycle:

    - `"single"` (default): one-shot blocking capture for `duration` seconds.
    - `"start"`: begin a continuous SCAN_SHIFT capture into a circular buffer
      (`buffer_size` samples, default 8192) that persists across tool calls.
    - `"read"`: fetch the latest samples from a running continuous capture. Can be
      called repeatedly.
    - `"stop"`: stop the continuous capture.

    Use start/read/stop when observing the LA while another instrument (AWG, scope)
    is running concurrently — e.g. W1 → DIO loopback verification.

    Bit N of each sample corresponds to DIO pin N.

    Args:
        channels: Channel indices to include in the result (0-based, DIO0-DIO15).
            None = all 16 channels.
        sample_rate: Sampling rate in Hz (default: 1 MHz). Used by `single`/`start`.
        duration: Single-shot capture duration in seconds (default: 1 ms).
            Determines buffer size for `single` if `buffer_size` is unset.
        buffer_size: Circular buffer size for continuous capture (default: 8192).
        action: Capture lifecycle action (default: "single").
        device_index: Device index (default: 0, the first device).

    Returns:
        For `single`/`read`: dict with `samples` (list of ints) and metadata.
        For `start`/`stop`: dict with `status` and configuration metadata.
    """
    try:
        device = get_manager().acquire(device_index)
        la = device.digital_input

        if action == "stop":
            la.configure(start=False)
            return {"action": "stop", "status": "stopped"}

        if action == "read":
            la.read_status(read_data=True)
            raw: list[int] = la.get_data().tolist()
            if channels is not None:
                mask = sum(1 << ch for ch in channels)
                samples = [s & mask for s in raw]
                channels_out = channels
            else:
                samples = raw
                channels_out = list(range(16))
            return {
                "channels": channels_out,
                "action": "read",
                "sample_count": len(samples),
                "samples": samples,
            }

        if action == "start":
            buf = buffer_size if buffer_size is not None else 8192
            la.setup_acquisition(
                mode=dwf.AcquisitionMode.SCAN_SHIFT,
                sample_rate=sample_rate,
                buffer_size=buf,
                configure=True,
                start=True,
            )
            return {
                "action": "start",
                "status": "running",
                "channels": channels if channels is not None else list(range(16)),
                "sample_rate": sample_rate,
                "buffer_size": buf,
            }

        # action == "single"
        buf = buffer_size if buffer_size is not None else int(sample_rate * duration)
        la.setup_acquisition(sample_rate=sample_rate, buffer_size=buf, start=True)

        timeout = max(duration * 10, 5.0)
        deadline = time.monotonic() + timeout
        while la.read_status(read_data=True) != dwf.Status.DONE:
            if time.monotonic() > deadline:
                return {"error": "Capture timed out."}
            time.sleep(0.001)

        raw = la.get_data().tolist()

        if channels is not None:
            mask = sum(1 << ch for ch in channels)
            filtered = [s & mask for s in raw]
        else:
            filtered = raw
            channels = list(range(16))

        return {
            "channels": channels,
            "sample_rate": sample_rate,
            "duration": duration,
            "sample_count": len(filtered),
            "samples": filtered,
        }
    except Exception as exc:  # noqa: BLE001
        get_manager().release(device_index)
        return {"error": str(exc)}


def register(mcp: FastMCP) -> None:
    """Register digital tools with the MCP server."""
    mcp.tool(digital_capture)
