#!/usr/bin/env bash
# Helper to run commands with uv on PATH inside WSL
export PATH="$HOME/.local/bin:$PATH"
cd /home/kalyan/projects/VoiceAI/apps/api || exit 1
exec "$@"