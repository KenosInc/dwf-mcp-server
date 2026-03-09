# Stage 1: builder — installs the package and dependencies
FROM python:3.14-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src/ src/

# Install into the system Python and stage site-packages at a version-agnostic path
RUN uv pip install --system --no-cache . \
 && PY_SITE=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))') \
 && cp -a "$PY_SITE" /opt/site-packages

# Stage 2: runtime — minimal image without build tools
FROM python:3.14-slim

# Install system dependencies required by the Digilent Adept 2 Runtime.
# The Runtime itself is proprietary, so it is NOT bundled — users add it
# via a derived Dockerfile (see comment below).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages and entry-point script from builder.
# Site-packages go through a staging path so the COPY is version-agnostic;
# a RUN step then moves them to the correct Python-version directory.
COPY --from=builder /opt/site-packages /opt/site-packages
COPY --from=builder /usr/local/bin/dwf-mcp-server /usr/local/bin/dwf-mcp-server
RUN PY_SITE=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))') \
 && cp -a /opt/site-packages/* "$PY_SITE"/ \
 && rm -rf /opt/site-packages

# Digilent Adept 2 Runtime and WaveForms SDK (libdwf.so) are proprietary
# and NOT included in this image.
#
# Users should create a derived Dockerfile to add them:
#   FROM ghcr.io/kenosinc/dwf-mcp-server:latest
#   ARG ADEPT_VERSION=2.27.9
#   ARG WAVEFORMS_VERSION=3.24.4
#   RUN apt-get update \
#       && apt-get install -y --no-install-recommends curl \
#       && ARCH="$(dpkg --print-architecture)" \
#       && curl -fsSL "https://files.digilent.com/Software/Adept2%20Runtime/${ADEPT_VERSION}/digilent.adept.runtime_${ADEPT_VERSION}-${ARCH}.deb" \
#          -o /tmp/adept-runtime.deb \
#       && curl -fsSL "https://files.digilent.com/Software/Waveforms/${WAVEFORMS_VERSION}/digilent.waveforms_${WAVEFORMS_VERSION}_${ARCH}.deb" \
#          -o /tmp/waveforms.deb \
#       && (apt-get install -y --no-install-recommends /tmp/adept-runtime.deb /tmp/waveforms.deb || true) \
#       && for cmd in xdg-desktop-menu xdg-icon-resource xdg-mime; do \
#            printf '#!/bin/sh\nexit 0\n' > "/usr/bin/$cmd" && chmod +x "/usr/bin/$cmd"; \
#          done \
#       && dpkg --configure -a \
#       && apt-get purge -y curl && apt-get autoremove -y \
#       && rm -f /tmp/adept-runtime.deb /tmp/waveforms.deb \
#       && rm -rf /var/lib/apt/lists/*

LABEL io.modelcontextprotocol.server.name="io.github.KenosInc/dwf-mcp-server"

CMD ["dwf-mcp-server"]
