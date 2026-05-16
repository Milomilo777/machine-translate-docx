#!/usr/bin/env bash
# Daily backup of mtd-server's irreplaceable state.
#
# What's backed up:
#   · config.toml        (API keys, Telegram, auth hash)
#   · runtime_dir/Log json file/   (per-run JSON sidecars)
#   · runtime_dir/cache/ (translation cache — speeds up reruns)
#   · runtime_dir/subscribers.txt  (newsletter list)
#
# What's NOT backed up:
#   · uploads/ — transient, regenerated on every job
#   · failures/ — already archived per-run by the launcher; keep
#     locally if you need post-mortems
#   · the venv and source tree — re-installable from git in 2 minutes
#
# Output: /var/backups/mtd/mtd-YYYY-MM-DD.tgz
# Retention: 30 days locally; consider rsync-ing to off-box storage.
#
# Install as a cron job (root):
#     sudo cp scripts/mtd-backup.sh /usr/local/sbin/mtd-backup
#     sudo chmod 755 /usr/local/sbin/mtd-backup
#     sudo crontab -e
#       # at 03:30 every day:
#       30 3 * * *  /usr/local/sbin/mtd-backup

set -euo pipefail

# ── settings (overridable via env) ───────────────────────────────────────────

MTD_HOME="${MTD_HOME:-/opt/mtd}"
MTD_CONFIG_PATH="${MTD_CONFIG_PATH:-${MTD_HOME}/config.toml}"
MTD_RUNTIME_DIR="${MTD_RUNTIME_DIR:-${MTD_HOME}/runtime_dir}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/mtd}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# ── prepare ──────────────────────────────────────────────────────────────────

TS="$(date -u +%Y-%m-%d)"
OUT="${BACKUP_DIR}/mtd-${TS}.tgz"
mkdir -p "${BACKUP_DIR}"

# Build the include list, only adding paths that actually exist.
INCLUDES=()
[[ -f "${MTD_CONFIG_PATH}"             ]] && INCLUDES+=("${MTD_CONFIG_PATH}")
[[ -d "${MTD_RUNTIME_DIR}/Log json file" ]] && INCLUDES+=("${MTD_RUNTIME_DIR}/Log json file")
[[ -d "${MTD_RUNTIME_DIR}/cache"       ]] && INCLUDES+=("${MTD_RUNTIME_DIR}/cache")
[[ -f "${MTD_RUNTIME_DIR}/subscribers.txt" ]] && INCLUDES+=("${MTD_RUNTIME_DIR}/subscribers.txt")
[[ -f "${MTD_RUNTIME_DIR}/subscribers_report_state.json" ]] && INCLUDES+=("${MTD_RUNTIME_DIR}/subscribers_report_state.json")

if [[ ${#INCLUDES[@]} -eq 0 ]]; then
    echo "[backup] nothing to back up; skipping." >&2
    exit 0
fi

# ── create archive ──────────────────────────────────────────────────────────

# `-P` to keep absolute paths so a restore lays things back exactly
# where they came from. tar will warn about absolute paths; that's fine.
tar --create --gzip --preserve-permissions --absolute-names \
    --file "${OUT}" \
    "${INCLUDES[@]}" 2>/dev/null

# Permissions: only root can read backups (they contain the API key).
chmod 0600 "${OUT}"

SIZE="$(du -h "${OUT}" | cut -f1)"
echo "[backup] $(date -u --iso-8601=seconds) → ${OUT} (${SIZE})"

# ── prune old backups ────────────────────────────────────────────────────────

# Keep only the last RETENTION_DAYS dailies. find's -delete is atomic
# enough for this use; failures are surfaced via cron's mail-to-root.
DELETED="$(find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'mtd-*.tgz' \
            -mtime +"${RETENTION_DAYS}" -print -delete | wc -l)"
if [[ "${DELETED}" -gt 0 ]]; then
    echo "[backup] pruned ${DELETED} archive(s) older than ${RETENTION_DAYS} days."
fi

# Optional: copy to an off-box destination. Uncomment and edit one:
#
#   rsync --quiet --partial --archive "${OUT}" backup-user@offsite:/backups/mtd/
#
#   aws s3 cp "${OUT}" s3://my-backup-bucket/mtd/ --quiet
#
# Both are best-effort; failures here should NOT bring down the cron.
