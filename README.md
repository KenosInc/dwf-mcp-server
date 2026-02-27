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
   See the [Host Setup Guide](docs/host-setup.md) for detailed
   installation and verification steps.

2. **libdwf.so** is proprietary and is **not bundled** in the Docker image.
   It must be volume-mounted from the host at runtime (see [Usage](#usage)).

## Installation

### Claude Code

```bash
claude mcp add dwf -- docker run -i --rm \
  -v /usr/lib/libdwf.so:/usr/lib/libdwf.so:ro \
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
        "-v", "/usr/lib/libdwf.so:/usr/lib/libdwf.so:ro",
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

Mount `libdwf.so` from the host (installed with the WaveForms SDK).
Adept 2 Runtime dependencies (`libdmgr`, `libdmgt`, etc.) are bundled in the Docker image.

| Host path | Notes |
|---|---|
| `/usr/lib/libdwf.so` | Main WaveForms library (proprietary, not bundled) |

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
