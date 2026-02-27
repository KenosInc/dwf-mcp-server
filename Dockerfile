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

# Install Digilent Adept 2 Runtime (provides libdmgr, libdpcomm, libdftd2xx, etc.)
# libdwf.so itself is proprietary and must be bind-mounted from the host.
ARG ADEPT_VERSION=2.27.9
RUN ARCH="$(dpkg --print-architecture)" \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -fsSL "https://files.digilent.com/Software/Adept2%20Runtime/${ADEPT_VERSION}/digilent.adept.runtime_${ADEPT_VERSION}-${ARCH}.deb" \
       -o /tmp/adept-runtime.deb \
    && apt-get install -y --no-install-recommends /tmp/adept-runtime.deb \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -f /tmp/adept-runtime.deb \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages and entry-point script from builder.
# Site-packages go through a staging path so the COPY is version-agnostic;
# a RUN step then moves them to the correct Python-version directory.
COPY --from=builder /opt/site-packages /opt/site-packages
COPY --from=builder /usr/local/bin/dwf-mcp-server /usr/local/bin/dwf-mcp-server
RUN PY_SITE=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))') \
 && cp -a /opt/site-packages/* "$PY_SITE"/ \
 && rm -rf /opt/site-packages

# libdwf.so is proprietary and must be mounted from the host.
# Adept 2 Runtime (libdmgr, libdmgt, etc.) is already installed above.
#
# Example (Linux host with WaveForms SDK installed):
#   docker run -i --rm \
#     -v /usr/lib/libdwf.so:/usr/lib/libdwf.so:ro \
#     --privileged \
#     ghcr.io/kenosinc/dwf-mcp-server

CMD ["dwf-mcp-server"]
