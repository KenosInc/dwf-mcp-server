"""Digilent WaveForms MCP Server entry point."""

from fastmcp import FastMCP

from dwf_mcp_server.tools import analog, devices, digital, gpio, protocols

mcp = FastMCP("dwf-mcp-server")

devices.register(mcp)
analog.register(mcp)
digital.register(mcp)
gpio.register(mcp)
protocols.register(mcp)


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
