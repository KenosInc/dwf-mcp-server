"""Digilent WaveForms MCP Server entry point."""

from fastmcp import FastMCP

from dwf_mcp_server.tools import analog, devices, digital

mcp = FastMCP("dwf-mcp-server")

devices.register(mcp)
analog.register(mcp)
digital.register(mcp)


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
