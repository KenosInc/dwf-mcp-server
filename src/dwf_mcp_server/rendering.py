"""Waveform image rendering helpers for capture tools.

These helpers turn captured samples into PNG plots so vision-capable LLM
clients can "see" the signal directly instead of reasoning over thousands
of raw sample values.

Pure functions — no hardware access, no MCP types — plus one small MCP
adapter (`build_image_tool_result`) that the tool modules share.
"""

import io
import math
import os

from fastmcp.tools.tool import ToolResult
from fastmcp.utilities.types import Image

# Force the headless Agg backend before any matplotlib import. setdefault so a
# user-supplied MPLBACKEND env var still wins.
os.environ.setdefault("MPLBACKEND", "Agg")


_FIGSIZE = (8.0, 4.0)
_DPI = 100


def build_image_tool_result(response: dict, png: bytes) -> ToolResult:
    """Wrap a tool response dict + PNG into a fastmcp `ToolResult`.

    Returning a `ToolResult` (instead of a `(dict, Image)` tuple) preserves
    `structured_content` on the wire — the tuple form drops it under
    fastmcp 3.2.x because the second tuple slot is interpreted as the
    structured payload.
    """
    image_content = Image(data=png, format="png").to_image_content()
    return ToolResult(content=[image_content], structured_content=response)


def _validate_sample_rate(sample_rate: float) -> None:
    # `not (x > 0)` already rejects NaN, but `inf` would pass the `> 0` check
    # and propagate into matplotlib as a silently-broken time axis.
    if not math.isfinite(sample_rate) or sample_rate <= 0:
        msg = f"sample_rate must be a finite positive number, got {sample_rate!r}"
        raise ValueError(msg)


def _validate_voltage_range(voltage_range: float) -> None:
    if not math.isfinite(voltage_range) or voltage_range <= 0:
        msg = f"voltage_range must be a finite positive number, got {voltage_range!r}"
        raise ValueError(msg)


def _validate_finite_floats(samples: list[float]) -> None:
    """Reject NaN / ±Inf — matplotlib would render a degraded plot silently."""
    for i, v in enumerate(samples):
        if not math.isfinite(v):
            msg = f"samples contain non-finite value at index {i}: {v!r}"
            raise ValueError(msg)


def _select_time_unit(duration_s: float) -> tuple[str, float]:
    """Pick a sensible time-axis unit/scale for a window of `duration_s` seconds."""
    if duration_s < 1e-3:
        return "µs", 1e6
    if duration_s < 1.0:
        return "ms", 1e3
    return "s", 1.0


def render_analog(
    samples: list[float],
    sample_rate: float,
    voltage_range: float,
) -> bytes:
    """Render a single-channel analog waveform as a PNG line plot.

    Args:
        samples: Voltage samples in volts.
        sample_rate: Sampling rate in Hz (used to derive the time axis).
        voltage_range: Configured peak-to-peak input range in volts; used to
            set Y-axis limits so noise floors and small signals stay legible
            even when the trace itself is mostly flat.

    Returns:
        PNG bytes (~10–50 KB at the default figure size).
    """
    _validate_sample_rate(sample_rate)
    _validate_voltage_range(voltage_range)
    _validate_finite_floats(samples)

    import matplotlib.pyplot as plt  # noqa: PLC0415  -- intentionally lazy

    fig, ax = plt.subplots(figsize=_FIGSIZE, dpi=_DPI)
    try:
        n = len(samples)
        if n == 0:
            ax.set_xlim(0.0, 1.0)
            ax.text(0.5, 0.5, "(no samples)", ha="center", va="center", transform=ax.transAxes)
            unit = "s"
        else:
            duration = max(n / sample_rate, 1e-12)
            unit, scale = _select_time_unit(duration)
            t = [(i / sample_rate) * scale for i in range(n)]
            ax.plot(t, samples, linewidth=1.0)
        ax.set_xlabel(f"Time [{unit}]")
        ax.set_ylabel("Voltage [V]")
        ax.grid(True, alpha=0.3)
        half = voltage_range / 2.0
        if half > 0:
            ax.set_ylim(-half, half)

        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png")
        return buf.getvalue()
    finally:
        plt.close(fig)


def render_digital(
    channels: list[int],
    samples: list[int],
    sample_rate: float,
) -> bytes:
    """Render a multi-pin logic-analyzer trace as a PNG.

    Each requested DIO pin appears as its own row of square waves, stacked
    vertically. The X axis auto-scales to s/ms/µs based on the capture window.

    Args:
        channels: DIO pin indices included in `samples`. Must match the
            channel subset the capture tool used to mask the integers.
        samples: Per-tick integers where bit N = state of DIO pin N (already
            masked to the requested channels by the caller).
        sample_rate: Sampling rate in Hz.

    Returns:
        PNG bytes.
    """
    _validate_sample_rate(sample_rate)

    import matplotlib.pyplot as plt  # noqa: PLC0415  -- intentionally lazy

    rows = max(len(channels), 1)
    fig_height = max(1.5, 0.5 * rows + 1.0)
    fig, ax = plt.subplots(figsize=(_FIGSIZE[0], fig_height), dpi=_DPI)
    try:
        n = len(samples)
        if n == 0 or not channels:
            ax.set_xlim(0.0, 1.0)
            ax.set_ylim(0.0, 1.0)
            ax.text(
                0.5,
                0.5,
                "(no samples)" if n == 0 else "(no channels)",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_xlabel("Time [s]")
        else:
            duration = max(n / sample_rate, 1e-12)
            unit, scale = _select_time_unit(duration)
            t = [(i / sample_rate) * scale for i in range(n)]

            ordered = list(channels)
            yticks = []
            ylabels = []
            for row, pin in enumerate(reversed(ordered)):
                base = row * 1.5
                trace = [base + ((s >> pin) & 1) for s in samples]
                ax.step(t, trace, where="post", linewidth=1.0)
                yticks.append(base + 0.5)
                ylabels.append(f"DIO{pin}")

            ax.set_yticks(yticks)
            ax.set_yticklabels(ylabels)
            ax.set_ylim(-0.3, len(ordered) * 1.5 - 0.2)
            ax.set_xlabel(f"Time [{unit}]")
            ax.grid(True, axis="x", alpha=0.3)

        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png")
        return buf.getvalue()
    finally:
        plt.close(fig)


def render_measurement(
    samples: list[float],
    sample_rate: float,
    measurement: str,
    value: float,
) -> bytes:
    """Render the measurement window as a PNG with annotations.

    Annotations depend on `measurement`:
    - dc / rms: horizontal line at the measured level.
    - peak_to_peak: Vmin / Vmax markers.
    - frequency / period: detected zero-crossings highlighted.

    Args:
        samples: Voltage samples used to compute the measurement.
        sample_rate: Sampling rate in Hz.
        measurement: One of "dc", "rms", "frequency", "period", "peak_to_peak".
        value: The measured scalar value (in V or Hz / s depending on type).

    Returns:
        PNG bytes.
    """
    _validate_sample_rate(sample_rate)
    _validate_finite_floats(samples)

    import matplotlib.pyplot as plt  # noqa: PLC0415  -- intentionally lazy

    fig, ax = plt.subplots(figsize=_FIGSIZE, dpi=_DPI)
    try:
        n = len(samples)
        if n == 0:
            ax.set_xlim(0.0, 1.0)
            ax.text(0.5, 0.5, "(no samples)", ha="center", va="center", transform=ax.transAxes)
            ax.set_xlabel("Time [s]")
            ax.set_ylabel("Voltage [V]")
        else:
            duration = max(n / sample_rate, 1e-12)
            unit, scale = _select_time_unit(duration)
            t = [(i / sample_rate) * scale for i in range(n)]
            ax.plot(t, samples, linewidth=1.0, color="#1f77b4")

            if measurement in ("dc", "rms"):
                ax.axhline(
                    value,
                    color="#d62728",
                    linewidth=1.0,
                    linestyle="--",
                    label=f"{measurement}={value:.4g} V",
                )
                ax.legend(loc="upper right")
            elif measurement == "peak_to_peak":
                vmin, vmax = min(samples), max(samples)
                ax.axhline(
                    vmax, color="#d62728", linewidth=1.0, linestyle="--", label=f"max={vmax:.4g} V"
                )
                ax.axhline(
                    vmin, color="#2ca02c", linewidth=1.0, linestyle="--", label=f"min={vmin:.4g} V"
                )
                ax.legend(loc="upper right")
            elif measurement in ("frequency", "period"):
                crossings = [i for i in range(1, n) if (samples[i - 1] < 0) != (samples[i] < 0)]
                if crossings:
                    xs = [(i / sample_rate) * scale for i in crossings]
                    ys = [samples[i] for i in crossings]
                    ax.scatter(
                        xs, ys, color="#d62728", s=18, zorder=3, label=f"{measurement}={value:.4g}"
                    )
                    ax.legend(loc="upper right")

            ax.set_xlabel(f"Time [{unit}]")
            ax.set_ylabel("Voltage [V]")
            ax.grid(True, alpha=0.3)

        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png")
        return buf.getvalue()
    finally:
        plt.close(fig)
