"""Digilent WaveForms MCP Server entry point."""

from fastmcp import FastMCP

from dwf_mcp_server.tools import analog, devices, digital, gpio, power, protocols

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
        "Each tool call opens and closes the device. There is no persistent session — "
        "state (pin levels, waveform output) does not survive across calls."
    ),
)

devices.register(mcp)
analog.register(mcp)
digital.register(mcp)
gpio.register(mcp)
power.register(mcp)
protocols.register(mcp)


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
