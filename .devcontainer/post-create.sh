#!/bin/bash
set -euo pipefail

echo "--- Fixing directory ownership ---"
echo "[chown] /home/vscode/.config"
sudo chown -R vscode:vscode /home/vscode/.config
echo "[chown] /home/vscode/.claude"
sudo chown -R vscode:vscode /home/vscode/.claude
echo "[chown] /home/vscode/.venv"
sudo chown -R vscode:vscode /home/vscode/.venv
# uv cache volume may be created as root; fix ownership so uv can write to it
echo "[chown] /home/vscode/.cache (uv cache volume)"
sudo chown -R vscode:vscode /home/vscode/.cache

echo "--- Configuring Claude Code onboarding ---"
echo "[claude] writing ~/.claude.json (if absent)"
if [ ! -f "$HOME/.claude.json" ]; then
  cat > "$HOME/.claude.json" << 'EOF'
{
  "hasCompletedOnboarding": true,
  "hasAckedPrivacyPolicy": true,
  "completedOnboardingAt": "2026-02-10T00:00:00.000Z",
  "opusProMigrationComplete": true
}
EOF
  echo "[claude] created ~/.claude.json"
else
  echo "[claude] ~/.claude.json already exists, skipping"
fi

echo "--- Installing mise and pinned tools ---"
# mise reads .mise.toml at the repo root and installs every tool listed there
# (codex, etc.). Re-running is safe and fast when the versions already match.
if ! command -v mise >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/mise" ]; then
  echo "[mise] installing mise from https://mise.run"
  curl -fsSL \
    --retry 5 --retry-delay 2 --retry-connrefused \
    --connect-timeout 10 --max-time 60 \
    https://mise.run | sh
else
  echo "[mise] mise already installed, skipping installer"
fi
echo "[mise] adding shims to PATH for current shell"
export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:$PATH"
echo "[mise] trusting .mise.toml"
mise trust
echo "[mise] installing tools pinned in .mise.toml"
mise install
echo "[mise] persisting shim PATH to ~/.bashrc (if missing)"
if ! grep -q 'mise/shims' "$HOME/.bashrc" 2>/dev/null; then
  # shellcheck disable=SC2016
  echo 'export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:$PATH"' >> "$HOME/.bashrc"
fi

echo "--- Creating Python venv and installing dependencies ---"
# Create venv and install Python package in editable mode with dev extras.
# `--allow-existing` keeps the venv intact when the `venv` Docker volume
# survives a devcontainer rebuild — without it, `uv venv` prompts the user
# and the post-create step hangs.
echo "[uv] creating venv at ~/.venv"
uv venv --allow-existing ~/.venv
echo "[uv] activating venv"
# shellcheck disable=SC1090,SC1091
source ~/.venv/bin/activate
echo "[uv] installing dwf-mcp-server[dev] in editable mode"
uv pip install -e "/workspaces/dwf-mcp-server[dev]"

echo "--- Tool verification ---"
python3 --version
uv --version
ruff --version
yamllint --version
gh --version
node --version
codex --version
rumdl --version
taplo --version
shellcheck --version
python3 -c "import dwf_mcp_server.server" 2>/dev/null && echo "dwf-mcp-server: ok" || echo "dwf-mcp-server: import failed (check libdwf installation)"

# Check uv cache volume permissions
if [ ! -w /home/vscode/.cache/uv ]; then
  echo "WARNING: uv cache is not writable. Run: docker volume rm dwf-mcp-server-uv-cache and rebuild the container."
fi

echo "Dev container ready!"
