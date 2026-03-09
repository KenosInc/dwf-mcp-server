# dwf-mcp-server

MCP Server for [Digilent WaveForms](https://digilent.com/reference/software/waveforms/waveforms-3/start)
instruments — oscilloscope, arbitrary waveform generator (AWG), and logic analyzer.
Built on [dwfpy](https://github.com/mariusgreuel/dwfpy), a Python binding for the
Digilent WaveForms SDK (`libdwf`).

## Supported Devices

- Analog Discovery 2 (AD2)
- Analog Discovery 3 (AD3)
- Digital Discovery (DD)
- Any device supported by the Digilent WaveForms SDK

## Prerequisites

- **Docker** installed on the host machine.
- **No host-side WaveForms SDK installation is required.** The proprietary `libdwf.so` is added
  via a derived Dockerfile layer (see [Installation](#installation)).


## Installation

The public Docker image **does not bundle any Digilent proprietary software**
(Adept 2 Runtime, WaveForms SDK / `libdwf.so`). You must create a derived image
that adds them.

### 1. Create a derived Dockerfile

Create a file named `Dockerfile.dwf`:

```dockerfile
FROM ghcr.io/kenosinc/dwf-mcp-server:latest

ARG ADEPT_VERSION=2.27.9
ARG WAVEFORMS_VERSION=3.24.4
RUN ARCH="$(dpkg --print-architecture)" \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -fsSL "https://files.digilent.com/Software/Adept2%20Runtime/${ADEPT_VERSION}/digilent.adept.runtime_${ADEPT_VERSION}-${ARCH}.deb" \
       -o /tmp/adept-runtime.deb \
    && curl -fsSL "https://files.digilent.com/Software/Waveforms/${WAVEFORMS_VERSION}/digilent.waveforms_${WAVEFORMS_VERSION}_${ARCH}.deb" \
       -o /tmp/waveforms.deb \
    && (apt-get install -y --no-install-recommends /tmp/adept-runtime.deb /tmp/waveforms.deb || true) \
    && for cmd in xdg-desktop-menu xdg-icon-resource xdg-mime; do \
         printf '#!/bin/sh\nexit 0\n' > "/usr/bin/$cmd" && chmod +x "/usr/bin/$cmd"; \
       done \
    && dpkg --configure -a \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -f /tmp/adept-runtime.deb /tmp/waveforms.deb \
    && rm -rf /var/lib/apt/lists/*
```

### 2. Build the image

```bash
docker build -f Dockerfile.dwf -t dwf-mcp-server .
```

### 3. Configure your MCP client

#### Claude Code

```bash
claude mcp add dwf -- docker run -i --rm --privileged dwf-mcp-server
```

#### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dwf": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--privileged",
        "dwf-mcp-server"
      ]
    }
  }
}
```

Pass `--privileged` so the container can access USB devices.

## Available MCP Tools

| Tool | Description |
|---|---|
| `list_devices` | List all connected Digilent WaveForms devices |
| `device_info` | Get detailed information about a specific device |
| `analog_capture` | Capture analog waveform samples (oscilloscope) |
| `generate_waveform` | Generate an analog signal (AWG): sine, square, triangle, ... |
| `measure` | Measure DC voltage, RMS, frequency, period, or peak-to-peak |
| `power_supply` | Control the programmable power supply (V+ / V-) |
| `digital_capture` | Capture digital logic signals (logic analyzer) |
| `gpio_read` | Read the logic level of a digital I/O pin |
| `gpio_write` | Set the logic level of a digital I/O pin |
| `spi_transfer` | Send and receive data over SPI using the digital protocol interface |

## Development

See [CLAUDE.md](CLAUDE.md) for development setup, coding conventions, and release procedures.

## License

[MIT](LICENSE)
