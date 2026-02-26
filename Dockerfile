# Stage 1: builder — installs the package and dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src/ src/

# Install into the system Python so we can copy site-packages cleanly
RUN uv pip install --system --no-cache .

# Stage 2: runtime — minimal image without build tools
FROM python:3.12-slim

# Copy installed packages and entry-point script from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages \
                    /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/dwf-mcp-server /usr/local/bin/dwf-mcp-server

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
