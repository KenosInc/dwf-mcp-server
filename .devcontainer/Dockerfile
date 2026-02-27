FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        usbutils \
        yamllint \
    && rm -rf /var/lib/apt/lists/*

# Install Digilent Adept 2 Runtime (provides libdmgr, libdpcomm, libdftd2xx, etc.)
# libdwf.so itself is proprietary and must be bind-mounted from the host.
ARG ADEPT_VERSION=2.27.9
RUN ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL "https://files.digilent.com/Software/Adept2%20Runtime/${ADEPT_VERSION}/digilent.adept.runtime_${ADEPT_VERSION}-${ARCH}.deb" \
       -o /tmp/adept-runtime.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/adept-runtime.deb \
    && rm -f /tmp/adept-runtime.deb \
    && rm -rf /var/lib/apt/lists/*

# Allow vscode user to access USB devices (owned by root:root in the container)
RUN usermod -aG root vscode

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

# Smoke tests: fail the build early if any tool is missing
RUN python3 --version \
    && uv --version \
    && yamllint --version
