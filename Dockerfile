# Stage 1: builder — installs the package and dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src/ src/

# Install into the system Python and stage site-packages at a version-agnostic path
RUN uv pip install --system --no-cache . \
 && PY_SITE=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))') \
 && cp -a "$PY_SITE" /opt/site-packages

# Stage 2: runtime — minimal image without build tools
FROM python:3.12-slim

# Copy installed packages and entry-point script from builder.
# Site-packages go through a staging path so the COPY is version-agnostic;
# a RUN step then moves them to the correct Python-version directory.
COPY --from=builder /opt/site-packages /opt/site-packages
COPY --from=builder /usr/local/bin/dwf-mcp-server /usr/local/bin/dwf-mcp-server
RUN PY_SITE=$(python3 -c 'import sysconfig; print(sysconfig.get_path("purelib"))') \
 && cp -a /opt/site-packages/* "$PY_SITE"/ \
 && rm -rf /opt/site-packages

# libdwf and its dependencies are proprietary and must be mounted from the host.
# They are NOT included in this image.
#
# Example (Linux host with WaveForms SDK installed):
#   docker run -i --rm \
#     -v /usr/lib/libdwf.so:/usr/lib/libdwf.so \
#     -v /usr/lib/libdmgr.so.2:/usr/lib/libdmgr.so.2 \
#     -v /usr/lib/libdmgt.so.2:/usr/lib/libdmgt.so.2 \
#     -v /usr/lib/libdjtg.so.2:/usr/lib/libdjtg.so.2 \
#     --privileged \
#     ghcr.io/kenosinc/dwf-mcp-server

CMD ["dwf-mcp-server"]
