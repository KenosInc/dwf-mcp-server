# dwf-mcp-server

MCP Server for [Digilent WaveForms](https://digilent.com/reference/software/waveforms/waveforms-3/start)
instruments — oscilloscope, arbitrary waveform generator (AWG), and logic analyzer.

## Supported Devices

- Analog Discovery 2 (AD2)
- Analog Discovery 3 (AD3)
- Digital Discovery (DD)
- Any device supported by the Digilent WaveForms SDK

## Prerequisites

1. **Digilent WaveForms SDK** must be installed on the **host** machine.
   Download from [digilent.com](https://digilent.com/reference/software/waveforms/waveforms-3/start).

2. **libdwf.so** is proprietary and is **not bundled** in the Docker image.
   It must be volume-mounted from the host at runtime (see [Usage](#usage)).

## Installation

### Claude Code

```bash
claude mcp add dwf -- docker run -i --rm \
  -v /usr/lib/libdwf.so:/usr/lib/libdwf.so \
  -v /usr/lib/libdmgr.so.2:/usr/lib/libdmgr.so.2 \
  -v /usr/lib/libdmgt.so.2:/usr/lib/libdmgt.so.2 \
  -v /usr/lib/libdjtg.so.2:/usr/lib/libdjtg.so.2 \
  --privileged \
  ghcr.io/kenosinc/dwf-mcp-server
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dwf": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/usr/lib/libdwf.so:/usr/lib/libdwf.so",
        "-v", "/usr/lib/libdmgr.so.2:/usr/lib/libdmgr.so.2",
        "-v", "/usr/lib/libdmgt.so.2:/usr/lib/libdmgt.so.2",
        "-v", "/usr/lib/libdjtg.so.2:/usr/lib/libdjtg.so.2",
        "--privileged",
        "ghcr.io/kenosinc/dwf-mcp-server"
      ]
    }
  }
}
```

### Docker (direct)

```bash
docker pull ghcr.io/kenosinc/dwf-mcp-server
```

## Usage

All four `.so` files below must be present on the host (installed with the WaveForms SDK):

| Host path | Notes |
|---|---|
| `/usr/lib/libdwf.so` | Main WaveForms library |
| `/usr/lib/libdmgr.so.2` | Device manager |
| `/usr/lib/libdmgt.so.2` | Device management transport |
| `/usr/lib/libdjtg.so.2` | JTAG transport |

Pass `--privileged` so the container can access USB devices.

## Available MCP Tools

| Tool | Description |
|---|---|
| `list_devices` | List all connected Digilent WaveForms devices |
| `device_info` | Get detailed information about a specific device |
| `analog_capture` | Capture analog waveform samples (oscilloscope) |
| `generate_waveform` | Generate an analog signal (AWG): sine, square, triangle, … |
| `measure` | Measure DC voltage, RMS, frequency, period, or peak-to-peak |
| `digital_capture` | Capture digital logic signals (logic analyzer) |

## Development

See [CLAUDE.md](CLAUDE.md) for development setup, coding conventions, and release procedures.

## License

[MIT](LICENSE)
