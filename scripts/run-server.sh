#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

JAR="$REPO_ROOT/target/translation-robot.jar"

if [ ! -f "$JAR" ]; then
    echo "ERROR: JAR not found at $JAR"
    echo "Run scripts/build.sh first."
    exit 1
fi

echo "=== Starting Translation Robot Server ==="
cd "$REPO_ROOT"
java -jar "$JAR"
