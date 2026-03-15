#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Starting SMTV GUI ==="
cd "$REPO_ROOT"
python3 src/machine_translate_gui.py
