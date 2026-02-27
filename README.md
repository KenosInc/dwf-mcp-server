# dwf-mcp-server

MCP Server for [Digilent WaveForms](https://digilent.com/reference/software/waveforms/waveforms-3/start)
instruments — oscilloscope, arbitrary waveform generator (AWG), and logic analyzer.

## Supported Devices

- Analog Discovery 2 (AD2)
- Analog Discovery 3 (AD3)
- Digital Discovery (DD)
- Any device supported by the Digilent WaveForms SDK

## Prerequisites

The Docker image bundles the Digilent Adept 2 Runtime and WaveForms SDK
(`libdwf.so` + device firmware). No host-side SDK installation or volume
mounts are required — just Docker and a USB-connected device.

## Installation

### Claude Code

```bash
claude mcp add dwf -- docker run -i --rm --privileged \
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

Pass `--privileged` so the container can access USB devices.
All required libraries and firmware are bundled in the image.

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
