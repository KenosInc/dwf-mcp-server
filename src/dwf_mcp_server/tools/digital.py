"""Digital logic analyzer tools for Digilent WaveForms."""

import time
from typing import Literal

import dwfpy as dwf
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from fastmcp.utilities.types import Image

from dwf_mcp_server import rendering
from dwf_mcp_server.session import get_manager


def _image_tool_result(response: dict, png: bytes) -> ToolResult:
    """Wrap a tool response dict + PNG into a ToolResult.

    See the matching helper in tools/analog.py for the rationale (preserves
    `structured_content` on the wire — the `(dict, Image)` tuple form does not).
    """
    image_content = Image(data=png, format="png").to_image_content()
    return ToolResult(content=[image_content], structured_content=response)


# Tracks the channel subset most recently requested by digital_capture(action="start"),
# keyed by device_index. None / missing entries mean "all 16 channels". Used to fill
# in `channels` for a follow-up `read` call when the caller omits it; cleared on stop.
_active_la_channels: dict[int, list[int]] = {}


def digital_capture(
    channels: list[int] | None = None,
    sample_rate: float = 1_000_000.0,
    duration: float = 0.001,
    buffer_size: int | None = None,
    action: Literal["single", "start", "read", "stop"] = "single",
    device_index: int = 0,
    render_image: bool = False,
) -> dict | ToolResult:
    """Capture digital logic signals using the logic analyzer.

    The `action` parameter selects the capture lifecycle:

    - `"single"` (default): one-shot blocking capture for `duration` seconds.
    - `"start"`: begin a continuous SCAN_SHIFT capture into a circular buffer
      (`buffer_size` samples, default 8192) that persists across tool calls.
    - `"read"`: fetch the latest samples from a running continuous capture. Can be
      called repeatedly. If `channels` is omitted, the channel subset from the
      matching `start` call on this device is reused.
    - `"stop"`: stop the continuous capture.

    Use start/read/stop when observing the LA while another instrument (AWG, scope)
    is running concurrently — e.g. W1 → DIO loopback verification.

    Bit N of each sample corresponds to DIO pin N.

    Args:
        channels: Channel indices to include in the result (0-based, DIO0-DIO15).
            None = all 16 channels for `single`/`start`. For `read`, None falls
            back to the channel subset from the preceding `start` (or all 16 if
            no `start` has happened on this device).
        sample_rate: Sampling rate in Hz (default: 1 MHz). Used by `single`/`start`.
        duration: Single-shot capture duration in seconds (default: 1 ms).
            Determines buffer size for `single` if `buffer_size` is unset.
        buffer_size: Circular buffer size for continuous capture (default: 8192).
        action: Capture lifecycle action (default: "single").
        device_index: Device index (default: 0, the first device).
        render_image: When True, also return a logic-analyzer style PNG plot
            of the captured samples (default: False). Only meaningful for
            `single`/`read`; ignored for `start`/`stop`. Errors and start/stop
            responses always return a plain dict.

    Returns:
        Plain dict by default. When `render_image=True` and samples were
        captured, a `ToolResult` carrying both the dict (as structured content)
        and the PNG image.
    """
    try:
        device = get_manager().acquire(device_index)
        la = device.digital_input

        if action == "stop":
            la.configure(start=False)
            _active_la_channels.pop(device_index, None)
            return {"action": "stop", "status": "stopped"}

        if action == "read":
            la.read_status(read_data=True)
            raw: list[int] = la.get_data().tolist()
            if channels is not None:
                effective = channels
            else:
                effective = _active_la_channels.get(device_index, list(range(16)))
            mask = sum(1 << ch for ch in effective)
            samples = [s & mask for s in raw]
            response = {
                "channels": effective,
                "action": "read",
                "sample_count": len(samples),
                "samples": samples,
            }
            if render_image:
                png = rendering.render_digital(effective, samples, sample_rate)
                return _image_tool_result(response, png)
            return response

        if action == "start":
            buf = buffer_size if buffer_size is not None else 8192
            la.setup_acquisition(
                mode=dwf.AcquisitionMode.SCAN_SHIFT,
                sample_rate=sample_rate,
                buffer_size=buf,
                configure=True,
                start=True,
            )
            persisted = list(channels) if channels is not None else list(range(16))
            _active_la_channels[device_index] = persisted
            return {
                "action": "start",
                "status": "running",
                "channels": persisted,
                "sample_rate": sample_rate,
                "buffer_size": buf,
            }

        # action == "single"
        buf = buffer_size if buffer_size is not None else int(sample_rate * duration)
        actual_duration = buf / sample_rate
        la.setup_acquisition(sample_rate=sample_rate, buffer_size=buf, start=True)

        timeout = max(actual_duration * 10, 5.0)
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

        response = {
            "channels": channels,
            "sample_rate": sample_rate,
            "duration": actual_duration,
            "sample_count": len(filtered),
            "samples": filtered,
        }
        if render_image:
            png = rendering.render_digital(channels, filtered, sample_rate)
            return _image_tool_result(response, png)
        return response
    except Exception as exc:  # noqa: BLE001
        get_manager().release(device_index)
        return {"error": str(exc)}


def register(mcp: FastMCP) -> None:
    """Register digital tools with the MCP server."""
    mcp.tool(digital_capture)
