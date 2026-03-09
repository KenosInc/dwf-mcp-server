#!/bin/bash
set -euo pipefail

echo "--- Fixing directory ownership ---"
# Claude Code needs write access to the config and claude directories
sudo chown -R vscode:vscode /home/vscode/.config
sudo chown -R vscode:vscode /home/vscode/.claude
sudo chown -R vscode:vscode /home/vscode/.venv

# uv cache volume may be created as root; fix ownership so uv can write to it
sudo chown -R vscode:vscode /home/vscode/.cache

echo "--- Configuring Claude Code onboarding ---"
# Claude Code skip onboarding
if [ ! -f "$HOME/.claude.json" ]; then
  cat > "$HOME/.claude.json" << 'EOF'
{
  "hasCompletedOnboarding": true,
  "hasAckedPrivacyPolicy": true,
  "completedOnboardingAt": "2026-02-10T00:00:00.000Z",
  "opusProMigrationComplete": true
}
EOF
  echo "Created ~/.claude.json"
else
  echo "~/.claude.json already exists, skipping"
fi

echo "--- Installing global npm tools ---"
npm install -g markdownlint-cli2

echo "--- Creating Python venv and installing dependencies ---"
# Create venv and install Python package in editable mode with dev extras
uv venv ~/.venv
# shellcheck disable=SC1091
source ~/.venv/bin/activate
uv pip install -e "/workspaces/dwf-mcp-server[dev]"

echo "--- Tool verification ---"
python3 --version
uv --version
ruff --version
yamllint --version
gh --version
node --version
markdownlint-cli2 --version
python3 -c "import dwf_mcp_server.server" 2>/dev/null && echo "dwf-mcp-server: ok" || echo "dwf-mcp-server: import failed (check libdwf installation)"

# Check uv cache volume permissions
if [ ! -w /home/vscode/.cache/uv ]; then
  echo "WARNING: uv cache is not writable. Run: docker volume rm dwf-mcp-server-uv-cache and rebuild the container."
fi

echo "Dev container ready!"
