#!/usr/bin/env bash
set -e

echo "=== Building translation-robot (Java) ==="
mvn clean package -DskipTests -q
echo "=== Build complete. JAR: target/translation-robot.jar ==="

echo "=== Installing Python dependencies ==="
pip3 install -r requirements.txt -q
echo "=== Python dependencies installed ==="
