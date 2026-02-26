"""Analog instrument tools (oscilloscope, AWG, measurement) for Digilent WaveForms."""

import math
import statistics
import time
from typing import Literal

from fastmcp import FastMCP


def analog_capture(
    channel: int = 1,
    sample_rate: float = 1_000_000.0,
    duration: float = 0.001,
    voltage_range: float = 5.0,
    device_index: int = 0,
) -> dict:
    """Capture analog waveform samples from an oscilloscope channel.

    Args:
        channel: Oscilloscope channel number (1 or 2, default: 1).
        sample_rate: Sampling rate in Hz (default: 1 MHz).
        duration: Capture duration in seconds (default: 1 ms → 1000 samples at 1 MHz).
        voltage_range: Input voltage range in Volts peak-to-peak (default: 5 V).
        device_index: Device index (default: 0, the first device).

    Returns:
        Dictionary with 'samples' (list of floats in Volts) and metadata.
    """
    try:
        import dwfpy as dwf  # noqa: PLC0415

        buffer_size = int(sample_rate * duration)
        ch_idx = channel - 1  # dwfpy uses 0-based channel indexing

        with dwf.Device(device_id=device_index) as device:
            scope = device.analog_input
            scope.setup(sample_rate=sample_rate, buffer_size=buffer_size)
            scope[ch_idx].setup(range=voltage_range, enable=True)
            scope.single()

            timeout = max(duration * 10, 5.0)
            deadline = time.monotonic() + timeout
            while not scope.is_done():
                if time.monotonic() > deadline:
                    return {"error": "Capture timed out."}
                time.sleep(0.001)

            samples: list[float] = scope[ch_idx].get_data().tolist()

        return {
            "channel": channel,
            "sample_rate": sample_rate,
            "duration": duration,
            "sample_count": len(samples),
            "unit": "V",
            "samples": samples,
        }
    except OSError as exc:
        return {"error": f"Failed to load libdwf: {exc}. Mount libdwf.so from the host."}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def generate_waveform(
    channel: int = 1,
    waveform: Literal["sine", "square", "triangle", "dc", "noise", "rampup", "rampdown"] = "sine",
    frequency: float = 1000.0,
    amplitude: float = 1.0,
    offset: float = 0.0,
    duration: float = 0.0,
    device_index: int = 0,
) -> dict:
    """Generate an analog waveform using the built-in function generator (AWG).

    Args:
        channel: AWG channel number (1 or 2, default: 1).
        waveform: Waveform type: sine, square, triangle, dc, noise, rampup, rampdown
            (default: "sine").
        frequency: Signal frequency in Hz (default: 1000 Hz).
        amplitude: Signal amplitude in Volts peak (default: 1 V).
        offset: DC offset in Volts (default: 0 V).
        duration: Generation duration in seconds; 0 = continuous (default: 0).
        device_index: Device index (default: 0, the first device).
    """
    try:
        import dwfpy as dwf  # noqa: PLC0415

        ch_idx = channel - 1

        with dwf.Device(device_id=device_index) as device:
            ch = device.analog_output[ch_idx]
            ch.setup(
                waveform,
                frequency=frequency,
                amplitude=amplitude,
                offset=offset,
                start=True,
            )
            if duration > 0:
                time.sleep(duration)
                ch.reset()

        return {
            "channel": channel,
            "waveform": waveform,
            "frequency": frequency,
            "amplitude": amplitude,
            "offset": offset,
            "duration": duration if duration > 0 else "continuous",
        }
    except OSError as exc:
        return {"error": f"Failed to load libdwf: {exc}. Mount libdwf.so from the host."}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def measure(
    channel: int = 1,
    measurement: Literal["dc", "rms", "frequency", "period", "peak_to_peak"] = "dc",
    sample_rate: float = 1_000_000.0,
    duration: float = 0.01,
    device_index: int = 0,
) -> dict:
    """Measure an electrical quantity using the oscilloscope.

    Args:
        channel: Oscilloscope channel number (1 or 2, default: 1).
        measurement: Measurement type: dc (mean), rms, frequency, period, peak_to_peak
            (default: "dc").
        sample_rate: Sampling rate in Hz (default: 1 MHz).
        duration: Measurement window in seconds (default: 10 ms).
        device_index: Device index (default: 0, the first device).
    """
    try:
        import dwfpy as dwf  # noqa: PLC0415

        buffer_size = int(sample_rate * duration)
        ch_idx = channel - 1

        with dwf.Device(device_id=device_index) as device:
            scope = device.analog_input
            scope.setup(sample_rate=sample_rate, buffer_size=buffer_size)
            scope[ch_idx].setup(enable=True)
            scope.single()

            timeout = max(duration * 10, 5.0)
            deadline = time.monotonic() + timeout
            while not scope.is_done():
                if time.monotonic() > deadline:
                    return {"error": "Measurement timed out."}
                time.sleep(0.001)

            samples: list[float] = scope[ch_idx].get_data().tolist()

        value, unit = _compute_measurement(samples, measurement, sample_rate)
        return {"channel": channel, "measurement": measurement, "value": value, "unit": unit}
    except OSError as exc:
        return {"error": f"Failed to load libdwf: {exc}. Mount libdwf.so from the host."}
    except Exception as exc:  # noqa: BLE001
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
