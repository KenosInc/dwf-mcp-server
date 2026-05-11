"""Analog instrument tools (oscilloscope, AWG, measurement) for Digilent WaveForms."""

import math
import statistics
import time
from typing import Literal

import dwfpy as dwf
from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult

from dwf_mcp_server import rendering
from dwf_mcp_server.session import get_manager

# Tracks the channel last used by analog_capture(action="start") and
# generate_waveform(action="start"), keyed by device_index. Used to fill in
# the channel for follow-up read/stop calls when the caller omits it. Updated
# on start; reads on read/stop only when channel is None.
_active_scope_channel: dict[int, int] = {}
_active_awg_channel: dict[int, int] = {}


def _validate_analog_channel(channel: int) -> None:
    """Reject channel values outside 1..2 before subtracting to a 0-based index.

    Without this guard, `channel=0` would silently become index -1 and
    Python's negative indexing would target CH2/W2 instead of erroring.
    """
    if channel not in (1, 2):
        msg = f"channel must be 1 or 2, got {channel}"
        raise ValueError(msg)


def analog_capture(
    channel: int | None = None,
    sample_rate: float = 1_000_000.0,
    duration: float = 0.001,
    voltage_range: float = 5.0,
    buffer_size: int | None = None,
    action: Literal["single", "start", "read", "stop"] = "single",
    device_index: int = 0,
    render_image: bool = False,
) -> dict | ToolResult:
    """Capture analog waveform samples from an oscilloscope channel.

    The `action` parameter selects the capture lifecycle:

    - `"single"` (default): one-shot blocking capture for `duration` seconds, then
      returns the samples. Use for quick measurements.
    - `"start"`: begin a continuous SCAN_SHIFT capture into a circular buffer
      (`buffer_size` samples, default 8192) that persists across tool calls.
    - `"read"`: fetch the latest samples from a running continuous capture. Can be
      called repeatedly. If `channel` is omitted, the channel from the matching
      `start` call on this device is reused.
    - `"stop"`: stop the continuous capture.

    Use the start/read/stop sequence when you need to observe the scope while
    another instrument (AWG, LA) is running concurrently.

    Args:
        channel: Oscilloscope channel number (1 or 2). Defaults to 1 for
            `single`/`start`. For `read`, defaults to whichever channel the
            preceding `start` used; an error is returned if no `start` is on
            record and no channel is supplied.
        sample_rate: Sampling rate in Hz (default: 1 MHz). Used by `single`/`start`.
        duration: Single-shot capture duration in seconds (default: 1 ms).
            Determines buffer size for `single` if `buffer_size` is unset.
        voltage_range: Input voltage range in Volts peak-to-peak (default: 5 V).
        buffer_size: Circular buffer size for continuous capture (default: 8192).
            Also overrides `duration`-derived buffer for `single`.
        action: Capture lifecycle action (default: "single").
        device_index: Device index (default: 0, the first device).
        render_image: When True, also return a PNG plot of the captured samples
            alongside the response dict (default: False). Only meaningful for
            `single`/`read`; ignored for `start`/`stop`. Errors and start/stop
            responses always return a plain dict.

    Returns:
        Plain dict by default. When `render_image=True` and samples were
        captured, a `ToolResult` carrying both the dict (as structured content)
        and the PNG image.
    """
    try:
        device = get_manager().acquire(device_index)
        scope = device.analog_input

        if action == "stop":
            scope.configure(start=False)
            ch = _active_scope_channel.pop(device_index, None)
            response: dict = {"action": "stop", "status": "stopped"}
            if ch is not None:
                response["channel"] = ch
            return response

        if action == "read":
            ch = channel if channel is not None else _active_scope_channel.get(device_index)
            if ch is None:
                return {
                    "error": (
                        "No active scope capture on this device; "
                        "call analog_capture(action='start') first or pass channel."
                    )
                }
            _validate_analog_channel(ch)
            ch_idx = ch - 1
            scope.read_status(read_data=True)
            samples: list[float] = scope[ch_idx].get_data().tolist()
            response = {
                "channel": ch,
                "action": "read",
                "sample_count": len(samples),
                "unit": "V",
                "samples": samples,
            }
            if render_image:
                png = rendering.render_analog(samples, sample_rate, voltage_range)
                return rendering.build_image_tool_result(response, png)
            return response

        ch = channel if channel is not None else 1
        _validate_analog_channel(ch)
        ch_idx = ch - 1

        if action == "start":
            buf = buffer_size if buffer_size is not None else 8192
            scope[ch_idx].setup(range=voltage_range, enabled=True)
            scope.setup_acquisition(
                mode=dwf.AcquisitionMode.SCAN_SHIFT,
                sample_rate=sample_rate,
                buffer_size=buf,
                configure=True,
                start=True,
            )
            _active_scope_channel[device_index] = ch
            return {
                "channel": ch,
                "action": "start",
                "status": "running",
                "sample_rate": sample_rate,
                "buffer_size": buf,
                "voltage_range": voltage_range,
            }

        # action == "single"
        buf = buffer_size if buffer_size is not None else int(sample_rate * duration)
        actual_duration = buf / sample_rate
        scope[ch_idx].setup(range=voltage_range, enabled=True)
        scope.setup_acquisition(sample_rate=sample_rate, buffer_size=buf, start=True)

        timeout = max(actual_duration * 10, 5.0)
        deadline = time.monotonic() + timeout
        while scope.read_status(read_data=True) != dwf.Status.DONE:
            if time.monotonic() > deadline:
                return {"error": "Capture timed out."}
            time.sleep(0.001)

        samples = scope[ch_idx].get_data().tolist()

        response = {
            "channel": ch,
            "sample_rate": sample_rate,
            "duration": actual_duration,
            "sample_count": len(samples),
            "unit": "V",
            "samples": samples,
        }
        if render_image:
            png = rendering.render_analog(samples, sample_rate, voltage_range)
            return rendering.build_image_tool_result(response, png)
        return response
    except Exception as exc:  # noqa: BLE001
        get_manager().release(device_index)
        return {"error": str(exc)}


def generate_waveform(
    channel: int | None = None,
    waveform: Literal["sine", "square", "triangle", "dc", "noise", "ramp-up", "ramp-down"] = "sine",
    frequency: float = 1000.0,
    amplitude: float = 1.0,
    offset: float = 0.0,
    duration: float = 0.0,
    action: Literal["pulse", "start", "stop"] = "pulse",
    device_index: int = 0,
) -> dict:
    """Generate an analog waveform using the built-in function generator (AWG).

    The `action` parameter selects the output lifecycle:

    - `"pulse"` (default): emit the waveform for `duration` seconds and stop. If
      `duration == 0`, output runs continuously (legacy continuous mode).
    - `"start"`: begin continuous output that persists across tool calls. The AWG
      keeps running until `action="stop"` is called or the device session closes.
    - `"stop"`: stop the AWG output without resetting its configuration. If
      `channel` is omitted, the channel from the matching `start` call is reused.
      Other waveform parameters are ignored when stopping.

    Use start/stop when another instrument (LA, scope) needs to observe the AWG
    output across multiple tool invocations (e.g. W1↔DIO loopback verification).

    Args:
        channel: AWG channel number (1 or 2). Defaults to 1 for
            `pulse`/`start`. For `stop`, defaults to the channel of the most
            recent `start` on this device; an error is returned if no `start`
            is on record and no channel is supplied.
        waveform: Waveform type: sine, square, triangle, dc, noise, ramp-up,
            ramp-down (default: "sine"). Ignored when action="stop".
        frequency: Signal frequency in Hz (default: 1000 Hz).
        amplitude: Signal amplitude in Volts peak (default: 1 V).
        offset: DC offset in Volts (default: 0 V).
        duration: Generation duration in seconds; 0 = continuous (default: 0).
            Only used by action="pulse".
        action: Output lifecycle action (default: "pulse").
        device_index: Device index (default: 0, the first device).
    """
    try:
        device = get_manager().acquire(device_index)

        if action == "stop":
            ch_num = channel if channel is not None else _active_awg_channel.get(device_index)
            if ch_num is None:
                return {
                    "error": (
                        "No active AWG output on this device; "
                        "call generate_waveform(action='start') first or pass channel."
                    )
                }
            _validate_analog_channel(ch_num)
            device.analog_output[ch_num - 1].configure(start=False)
            # Only clear persistence if we stopped the persisted channel — preserves
            # the active channel record when the caller explicitly stops a different one.
            if _active_awg_channel.get(device_index) == ch_num:
                del _active_awg_channel[device_index]
            return {"channel": ch_num, "action": "stop", "status": "stopped"}

        ch_num = channel if channel is not None else 1
        _validate_analog_channel(ch_num)
        ch = device.analog_output[ch_num - 1]
        ch.setup(
            waveform,
            frequency=frequency,
            amplitude=amplitude,
            offset=offset,
            start=True,
        )

        if action == "start":
            _active_awg_channel[device_index] = ch_num
            return {
                "channel": ch_num,
                "action": "start",
                "status": "running",
                "waveform": waveform,
                "frequency": frequency,
                "amplitude": amplitude,
                "offset": offset,
            }

        # action == "pulse"
        if duration > 0:
            time.sleep(duration)
            ch.reset()

        return {
            "channel": ch_num,
            "waveform": waveform,
            "frequency": frequency,
            "amplitude": amplitude,
            "offset": offset,
            "duration": duration if duration > 0 else "continuous",
        }
    except Exception as exc:  # noqa: BLE001
        get_manager().release(device_index)
        return {"error": str(exc)}


def measure(
    channel: int = 1,
    measurement: Literal["dc", "rms", "frequency", "period", "peak_to_peak"] = "dc",
    sample_rate: float = 1_000_000.0,
    duration: float = 0.01,
    device_index: int = 0,
    render_image: bool = False,
) -> dict | ToolResult:
    """Measure an electrical quantity using the oscilloscope.

    Single-shot measurement; for continuous observation use
    `analog_capture(action="start"/"read"/"stop")` instead.

    Args:
        channel: Oscilloscope channel number (1 or 2, default: 1).
        measurement: Measurement type: dc (mean), rms, frequency, period, peak_to_peak
            (default: "dc").
        sample_rate: Sampling rate in Hz (default: 1 MHz).
        duration: Measurement window in seconds (default: 10 ms).
        device_index: Device index (default: 0, the first device).
        render_image: When True, also return a PNG plot of the measurement
            window with annotations (default: False). The response dict
            shape is unchanged either way; raw samples are not exposed.

    Returns:
        Plain dict by default. When `render_image=True` succeeds, a
        `ToolResult` carrying the same dict (as structured content) plus
        the PNG image. Errors always return a plain dict.
    """
    try:
        buffer_size = int(sample_rate * duration)
        ch_idx = channel - 1

        device = get_manager().acquire(device_index)
        scope = device.analog_input
        scope[ch_idx].setup(enabled=True)
        scope.setup_acquisition(sample_rate=sample_rate, buffer_size=buffer_size, start=True)

        timeout = max(duration * 10, 5.0)
        deadline = time.monotonic() + timeout
        while scope.read_status(read_data=True) != dwf.Status.DONE:
            if time.monotonic() > deadline:
                return {"error": "Measurement timed out."}
            time.sleep(0.001)

        samples: list[float] = scope[ch_idx].get_data().tolist()

        value, unit = _compute_measurement(samples, measurement, sample_rate)
        response = {"channel": channel, "measurement": measurement, "value": value, "unit": unit}
        if render_image:
            png = rendering.render_measurement(samples, sample_rate, measurement, value)
            return rendering.build_image_tool_result(response, png)
        return response
    except Exception as exc:  # noqa: BLE001
        get_manager().release(device_index)
        return {"error": str(exc)}


def _compute_measurement(
    samples: list[float], measurement: str, sample_rate: float
) -> tuple[float, str]:
    """Compute a scalar measurement from raw sample data."""
    if measurement == "dc":
        return statistics.mean(samples), "V"
    if measurement == "rms":
        return math.sqrt(sum(x * x for x in samples) / len(samples)), "V"
    if measurement == "peak_to_peak":
        return max(samples) - min(samples), "V"
    if measurement == "frequency":
        crossing_indices = [
            i for i in range(1, len(samples)) if (samples[i - 1] < 0) != (samples[i] < 0)
        ]
        if len(crossing_indices) < 2:
            return 0.0, "Hz"
        num_half_periods = len(crossing_indices) - 1
        time_span = (crossing_indices[-1] - crossing_indices[0]) / sample_rate
        return num_half_periods / (2 * time_span), "Hz"
    if measurement == "period":
        freq, _ = _compute_measurement(samples, "frequency", sample_rate)
        return (1.0 / freq) if freq > 0 else 0.0, "s"
    msg = f"Unknown measurement type: {measurement}"
    raise ValueError(msg)


def register(mcp: FastMCP) -> None:
    """Register analog tools with the MCP server."""
    mcp.tool(analog_capture)
    mcp.tool(generate_waveform)
    mcp.tool(measure)
