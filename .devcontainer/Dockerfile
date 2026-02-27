FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        usbutils \
        yamllint \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
RUN pip install --no-cache-dir uv

# Install ruff (linter / formatter)
RUN pip install --no-cache-dir ruff

# Smoke tests: fail the build early if any tool is missing
RUN python3 --version \
    && uv --version \
    && ruff --version \
    && yamllint --version
