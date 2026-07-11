#!/usr/bin/env bash
# Setup development environment for hermes-multimail
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Setting up hermes-multimail..."

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

echo "Installing pre-commit hook..."
if [ -f scripts/pre-commit ]; then
    chmod +x scripts/pre-commit
    cp scripts/pre-commit .git/hooks/pre-commit
    echo "Pre-commit hook installed."
else
    echo "Warning: scripts/pre-commit not found, skipping hook install."
fi

echo "Setup complete. Run 'ruff check email_multi tests' to lint, 'python -m unittest' to test."
