set -u
cd /home/kalyan/projects/VoiceAI
echo "=== uv:"; command -v uv || echo MISSING
echo "=== pip in venv:"; apps/api/.venv/bin/python -m pip --version 2>&1 | head -2
echo "=== dev tools:"; for t in pytest ruff mypy alembic celery uvicorn; do printf "%s: " $t; ls apps/api/.venv/bin/$t >/dev/null 2>&1 && echo present || echo MISSING; done