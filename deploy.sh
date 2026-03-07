#!/bin/bash
set -e
# Self-heal Windows CRLF line endings on Linux
sed -i 's/\r$//' "$0" 2>/dev/null || true

echo "Starting Zero-Touch Deployment..."
# Ensure Docker is installed
if ! command -v docker &> /dev/null; then echo "Docker not found! Please install it."; exit 1; fi

docker-compose up -d --build

# Safe Taiwan Cron (First Saturday, 11 AM UTC+8 = 03:00 AM UTC)
CRON_JOB="0 3 * * 6 [ \"\$(date +\%e)\" -le 7 ] && /sbin/reboot"
(crontab -l 2>/dev/null | grep -Fv "/sbin/reboot"; echo "$CRON_JOB") | crontab -

echo "Deployment successful."