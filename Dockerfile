# Stage 1: builder — installs the package and dependencies from uv.lock
FROM python:3.14-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

# uv defaults to symlinks; copy is required when the .venv is later moved
# across stages (the symlink targets disappear in the runtime image).
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md ./
COPY src/ src/

# `--frozen` aborts if uv.lock is out of date relative to pyproject.toml.
# `--no-dev` excludes dev / test dependencies from the runtime image.
RUN uv sync --frozen --no-dev

# Stage 2: runtime — minimal image without build tools
FROM python:3.14-slim

# Install system dependencies required by the Digilent Adept 2 Runtime.
# The Runtime itself is proprietary, so it is NOT bundled — users add it
# via a derived Dockerfile (see comment below).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libusb-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy the pinned virtual environment from the builder stage. `dwf-mcp-server`
# resolves to /app/.venv/bin/dwf-mcp-server via PATH.
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

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
