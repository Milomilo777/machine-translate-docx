#!/usr/bin/env bash
# Install mtd as a systemd service on Ubuntu 22.04+ / Debian 12+.
#
# Usage (as root or via sudo):
#     curl -fsSL https://raw.githubusercontent.com/Milomilo777/machine-translate-docx/master/scripts/install_server.sh | sudo bash
#
# Or, from a local clone:
#     sudo bash scripts/install_server.sh
#
# What it does:
#   1. Adds the deadsnakes PPA (Python 3.11) on Ubuntu, skips on
#      Debian 12 which ships 3.11 in the base archive.
#   2. Installs python3.11 + python3.11-venv + git + libxml2 (lxml dep).
#   3. Creates a non-root `mtd` system user with /opt/mtd home.
#   4. Clones the repo (or uses the existing one if invoked from a clone).
#   5. Sets up a venv at /opt/mtd/.venv with requirements-server.txt.
#   6. Runs the setup wizard interactively (writes config.toml).
#   7. Installs the systemd unit, enables it, starts it.
#   8. Prints next-step pointers (Caddy, journalctl, /health URL).
#
# Idempotent: re-running on an existing install upgrades pip deps and
# restarts the service. The setup wizard skips sections that already
# have values unless the operator chooses to replace them.

set -euo pipefail

# ── helpers ──────────────────────────────────────────────────────────────────

INFO() { printf "\033[1;36m[install]\033[0m %s\n" "$*"; }
WARN() { printf "\033[1;33m[install]\033[0m %s\n" "$*" >&2; }
DIE()  { printf "\033[1;31m[install]\033[0m %s\n" "$*" >&2; exit 1; }

need_root() {
    [[ $(id -u) -eq 0 ]] || DIE "Run as root (sudo bash $0)."
}

detect_os() {
    if [[ -f /etc/os-release ]]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        echo "${ID:-unknown}-${VERSION_ID:-unknown}"
    else
        echo "unknown"
    fi
}

# ── settings (overridable via env) ───────────────────────────────────────────

MTD_USER="${MTD_USER:-mtd}"
MTD_HOME="${MTD_HOME:-/opt/mtd}"
MTD_REPO_URL="${MTD_REPO_URL:-https://github.com/Milomilo777/machine-translate-docx.git}"
MTD_BRANCH="${MTD_BRANCH:-master}"
MTD_REPO_DIR="${MTD_REPO_DIR:-${MTD_HOME}/app}"
MTD_VENV_DIR="${MTD_VENV_DIR:-${MTD_HOME}/.venv}"
MTD_CONFIG_PATH="${MTD_CONFIG_PATH:-${MTD_HOME}/config.toml}"
MTD_RUNTIME_DIR_HOST="${MTD_RUNTIME_DIR_HOST:-${MTD_HOME}/runtime_dir}"
SYSTEMD_UNIT="${SYSTEMD_UNIT:-/etc/systemd/system/mtd-server.service}"

# ── steps ────────────────────────────────────────────────────────────────────

need_root
OS="$(detect_os)"
INFO "Detected OS: ${OS}"
INFO "Target user: ${MTD_USER}    home: ${MTD_HOME}"

INFO "[1/8] Installing system packages…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -qq -y \
    python3.11 python3.11-venv python3.11-dev \
    git curl ca-certificates \
    libxml2 libxslt1.1 \
    2>&1 | tail -5 || {
        # On Ubuntu 22.04 python3.11 isn't in the base archive — add deadsnakes.
        WARN "python3.11 missing from default repos; adding deadsnakes PPA…"
        apt-get install -qq -y software-properties-common
        add-apt-repository -y ppa:deadsnakes/ppa
        apt-get update -qq
        apt-get install -qq -y python3.11 python3.11-venv python3.11-dev
    }
INFO "  ✓ python3.11 present at $(command -v python3.11)"

INFO "[2/8] Creating system user '${MTD_USER}'…"
if ! id "${MTD_USER}" &>/dev/null; then
    useradd --system --create-home --home-dir "${MTD_HOME}" \
            --shell /usr/sbin/nologin "${MTD_USER}"
    INFO "  ✓ user created"
else
    INFO "  · user already exists"
fi
mkdir -p "${MTD_HOME}" "${MTD_RUNTIME_DIR_HOST}"
chown -R "${MTD_USER}:${MTD_USER}" "${MTD_HOME}"

INFO "[3/8] Fetching repo to ${MTD_REPO_DIR}…"
if [[ -d "${MTD_REPO_DIR}/.git" ]]; then
    INFO "  · repo present; fetching latest ${MTD_BRANCH}…"
    sudo -u "${MTD_USER}" git -C "${MTD_REPO_DIR}" fetch --quiet origin
    sudo -u "${MTD_USER}" git -C "${MTD_REPO_DIR}" checkout --quiet "${MTD_BRANCH}"
    sudo -u "${MTD_USER}" git -C "${MTD_REPO_DIR}" reset --hard --quiet "origin/${MTD_BRANCH}"
else
    INFO "  · cloning ${MTD_REPO_URL}…"
    sudo -u "${MTD_USER}" git clone --quiet --branch "${MTD_BRANCH}" \
        "${MTD_REPO_URL}" "${MTD_REPO_DIR}"
fi
INFO "  ✓ repo at $(sudo -u ${MTD_USER} git -C ${MTD_REPO_DIR} rev-parse --short HEAD)"

INFO "[4/8] Setting up Python venv…"
if [[ ! -x "${MTD_VENV_DIR}/bin/python" ]]; then
    sudo -u "${MTD_USER}" python3.11 -m venv "${MTD_VENV_DIR}"
fi
sudo -u "${MTD_USER}" "${MTD_VENV_DIR}/bin/python" -m pip install \
    --quiet --upgrade pip wheel setuptools
INFO "[5/8] Installing requirements-server.txt (server-only deps)…"
sudo -u "${MTD_USER}" "${MTD_VENV_DIR}/bin/python" -m pip install \
    --quiet -r "${MTD_REPO_DIR}/requirements-server.txt"
INFO "  ✓ deps installed ($(${MTD_VENV_DIR}/bin/python -m pip list 2>/dev/null | wc -l) packages)"

INFO "[6/8] Running setup wizard…"
echo "  ────────────────────────────────────────────────"
echo "  The wizard will ask for OpenAI API key, Telegram"
echo "  bot token, web-UI password, and any optional"
echo "  alerting destinations. Skip optional sections by"
echo "  pressing Enter."
echo "  ────────────────────────────────────────────────"
export MTD_CONFIG_PATH MTD_RUNTIME_DIR="${MTD_RUNTIME_DIR_HOST}"
sudo -E -u "${MTD_USER}" "${MTD_VENV_DIR}/bin/python" \
    "${MTD_REPO_DIR}/scripts/setup_wizard.py" --config "${MTD_CONFIG_PATH}"

INFO "[7/8] Installing systemd unit…"
install -m 0644 "${MTD_REPO_DIR}/scripts/mtd-server.service" "${SYSTEMD_UNIT}"
# Substitute paths into the unit
sed -i \
    -e "s|@@MTD_USER@@|${MTD_USER}|g" \
    -e "s|@@MTD_VENV_DIR@@|${MTD_VENV_DIR}|g" \
    -e "s|@@MTD_REPO_DIR@@|${MTD_REPO_DIR}|g" \
    -e "s|@@MTD_CONFIG_PATH@@|${MTD_CONFIG_PATH}|g" \
    -e "s|@@MTD_RUNTIME_DIR@@|${MTD_RUNTIME_DIR_HOST}|g" \
    "${SYSTEMD_UNIT}"
systemctl daemon-reload
systemctl enable --quiet mtd-server.service
systemctl restart mtd-server.service

INFO "[8/8] Verifying boot…"
sleep 2
if systemctl is-active --quiet mtd-server.service; then
    INFO "  ✓ mtd-server.service is RUNNING"
else
    WARN "  ✗ service failed to start; check 'journalctl -u mtd-server -n 50'"
fi

PORT="$(awk -F'[ =]+' '/^port[[:space:]]*=/{print $3; exit}' "${MTD_CONFIG_PATH}" 2>/dev/null || echo 3000)"
HOST="$(awk -F'"' '/^host[[:space:]]*=/{print $2; exit}' "${MTD_CONFIG_PATH}" 2>/dev/null || echo 127.0.0.1)"

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Install complete."
echo
echo "   Config:     ${MTD_CONFIG_PATH}  (chmod 0600, owner ${MTD_USER})"
echo "   Service:    systemctl status mtd-server"
echo "   Logs:       journalctl -u mtd-server -f"
echo "   Health:     curl http://${HOST}:${PORT}/health"
echo "   Re-config:  sudo -u ${MTD_USER} ${MTD_VENV_DIR}/bin/python \\"
echo "                 ${MTD_REPO_DIR}/scripts/setup_wizard.py"
echo
echo " Next:"
echo "   · Stand up Caddy on port 443 to terminate TLS"
echo "       (see scripts/Caddyfile.example)"
echo "   · Configure backups + log rotation"
echo "       (see scripts/mtd-backup.sh + scripts/mtd-logrotate)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
