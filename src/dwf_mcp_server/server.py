"""Digilent WaveForms MCP Server entry point."""

import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from dwf_mcp_server import patches
from dwf_mcp_server.diagnostics import check_environment
from dwf_mcp_server.session import get_manager
from dwf_mcp_server.tools import analog, devices, digital, gpio, power, protocols, session_tools


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[None]:
    """Release all device sessions on server shutdown."""
    yield
    get_manager().release_all()


mcp = FastMCP(
    "dwf-mcp-server",
    instructions=(
        "MCP server for Digilent WaveForms instruments (Analog Discovery 2/3, Digital Discovery).\n"
        "\n"
        "Pin/channel numbering follows hardware labels — no conversion needed:\n"
        "- DIO pins (gpio_read, gpio_write, spi_transfer, digital_capture): "
        "0-based (0-15), matching DIO0-DIO15 silk-screen labels.\n"
        "- Analog channels (analog_capture, measure, generate_waveform): "
        "1-based (1-2), matching CH1/CH2 and W1/W2 labels.\n"
        "\n"
        "Device sessions open automatically on first tool use and persist across calls. "
        "Hardware state (AWG output, GPIO levels, power supply) is maintained while the "
        "session is open. Sessions auto-close after 5 minutes of inactivity. "
        "Use close_device to explicitly end a session and stop all outputs."
    ),
    lifespan=lifespan,
)

devices.register(mcp)
analog.register(mcp)
digital.register(mcp)
gpio.register(mcp)
power.register(mcp)
protocols.register(mcp)
session_tools.register(mcp)


def main() -> None:
    """Run the MCP server over stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    patches.apply()
    if not check_environment():
        sys.exit(1)
    mcp.run()


if __name__ == "__main__":
    main()
