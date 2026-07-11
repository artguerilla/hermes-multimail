#!/usr/bin/env bash
# Setup development environment for hermes-multimail
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Installing hermes-multimail with dev dependencies..."
pip install -e ".[dev]"

echo "==> Setup complete. Run verification with:"
echo "     python3 -m py_compile email_multi/*.py"
echo "     python3 -m unittest"
echo "     ruff check email_multi tests"
echo "     python -m build"
echo "     twine check dist/*"
