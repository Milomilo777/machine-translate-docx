# Server Deployment Guide

Start-to-finish recipe for running mtd-server on a Linux VPS.

> **Resource target:** 1 vCPU, 1 GB RAM, 20 GB SSD. The OpenAI API
> path doesn't need Chrome and runs comfortably on Hetzner CX11
> (€4/mo), Contabo VPS S (€3/mo), or Vultr's $6 cloud-compute tier.

---

## TL;DR

```bash
# On a fresh Ubuntu 22.04+ / Debian 12+ VPS, as root:
curl -fsSL https://raw.githubusercontent.com/Milomilo777/machine-translate-docx/master/scripts/install_server.sh | sudo bash
```

The installer creates a non-root `mtd` user, sets up a Python 3.11
venv with the minimal dep set, runs an interactive wizard that collects
your OpenAI API key + Telegram + Web-UI password, drops a systemd unit,
and enables it on boot. Total time: ~2 minutes on a fresh box.

After install, point Caddy or nginx at `localhost:3000` for HTTPS
(see [Step 5](#step-5--https-with-caddy)).

---

## Step 1 — VPS prerequisites

| Need | Why |
|---|---|
| Ubuntu 22.04+ or Debian 12+ | Python 3.11 from deadsnakes or base archive |
| 1 vCPU, 1 GB RAM | Comfortable headroom for OpenAI-API translations |
| 20 GB SSD | Repo (~50 MB) + venv (~120 MB) + Log/cache (~5 GB after 90 days) |
| Public IPv4 | DNS A record + Let's Encrypt cert acquisition |
| Open ports 80 + 443 | HTTP→HTTPS redirect + TLS |
| SSH key auth | Root password login should be disabled in `/etc/ssh/sshd_config` |
| `OPENAI_API_KEY` | Get from <https://platform.openai.com/api-keys> |

Recommended bare-minimum hardening before install:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ufw fail2ban
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable
```

---

## Step 2 — Run the installer

From a checkout (or just clone first):

```bash
git clone https://github.com/Milomilo777/machine-translate-docx.git /tmp/mtd
sudo bash /tmp/mtd/scripts/install_server.sh
```

Or one-line from raw github:

```bash
curl -fsSL https://raw.githubusercontent.com/Milomilo777/machine-translate-docx/master/scripts/install_server.sh | sudo bash
```

The installer's 8 steps print progress markers. The wizard mid-way
through is interactive — have your OpenAI API key + Telegram bot
token ready. Press Enter to skip optional sections.

After install:

```bash
systemctl status mtd-server     # should show "active (running)"
journalctl -u mtd-server -f     # tail the launcher's stdout
curl http://127.0.0.1:3000/health
# → {"status":"ok","version":"...","uptime":7}
```

---

## Step 3 — The config file

All settings live in **one** file:

```bash
sudo cat /opt/mtd/config.toml
```

```toml
[openai]
api_key = "sk-..."

[auth]
username       = "admin"
password_hash  = "$2b$12$..."          # bcrypt — never the cleartext
session_secret = "<64-char hex>"

[server]
host                = "127.0.0.1"
port                = 3000
max_concurrent_jobs = 1

[telegram]
token         = "..."
chat_id       = "..."
no_attachment = false
scheduler_tz  = "Europe/Paris"

# Optional sections — only present if you opted in during the wizard.
# [smtp] ..., [failure_alerts] ...
```

File mode is `0600`, owner `mtd`. The API key lives here in plain
text by design — a malicious local user with `mtd` privileges has
already won. Treat the box accordingly.

**To re-run the wizard later** (rotate keys, change password, add
Telegram):

```bash
sudo -u mtd /opt/mtd/.venv/bin/python /opt/mtd/app/scripts/setup_wizard.py
sudo systemctl restart mtd-server
```

**To edit a single value by hand** (e.g. bump `max_concurrent_jobs`):

```bash
sudo -u mtd nano /opt/mtd/config.toml
sudo systemctl restart mtd-server
```

---

## Step 4 — Auth

Every route except `/health`, `/static/*`, and `/favicon.ico` is
guarded by HTTP Basic Auth. The username + password hash live under
`[auth]` in `config.toml`; the launcher checks them on every request.

What this gets you:

| Concern | Handled |
|---|---|
| Cleartext password on disk | NO — bcrypt-hashed |
| Brute force | fail2ban (optional, recommended) |
| Session fixation | n/a — Basic auth is stateless |
| Cookie hijack | n/a — no cookies |
| Login UI | browser's built-in dialog |

For a more polished login experience (form-based, password manager
friendly) you'd add a session-cookie layer in front. Not needed for
a single-operator deployment.

---

## Step 5 — HTTPS with Caddy

Caddy gets you a Let's Encrypt cert in one command:

```bash
# Install
curl -fsSL https://get.caddyserver.com | sh

# Configure
sudo cp /opt/mtd/app/scripts/Caddyfile.example /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile     # replace mtd.example.com with your hostname

# Run
sudo systemctl enable --now caddy
sudo systemctl status caddy
```

Caddy:
  · auto-fetches the cert from Let's Encrypt
  · auto-renews 30 days before expiry
  · forces HTTP→HTTPS
  · drops `/health` from the access log (cuts uptime-monitor noise)

If you'd rather use nginx + certbot, the upstream `Caddyfile.example`
documents the headers + timeouts you need to mirror.

---

## Step 6 — Log rotation (weekly compress, 90-day retention)

```bash
sudo cp /opt/mtd/app/scripts/mtd-logrotate /etc/logrotate.d/mtd-server
sudo logrotate -d /etc/logrotate.d/mtd-server   # dry-run; check for errors
```

The rules cover:
  · `runtime_dir/Log json file/*.json` — translation sidecars
  · `/var/log/caddy/mtd.access.log` — Caddy reverse-proxy access

Weekly compression keeps the I/O cost low; 90-day retention means
you can audit translations from the past quarter without filling the
disk.

---

## Step 7 — Backups (daily, 30-day retention)

```bash
sudo cp /opt/mtd/app/scripts/mtd-backup.sh /usr/local/sbin/mtd-backup
sudo chmod 755 /usr/local/sbin/mtd-backup
sudo crontab -e
# Add this line:
30 3 * * *  /usr/local/sbin/mtd-backup
```

Backups land at `/var/backups/mtd/mtd-YYYY-MM-DD.tgz` (mode 0600).
They contain `config.toml`, the JSON sidecar archive, the translation
cache, and the subscribers list.

For off-box backup, uncomment the `rsync` or `aws s3 cp` line at the
bottom of `mtd-backup.sh` and adjust to your storage. A box-only
backup survives accidental `rm -rf` but not a VPS provider going
under — keep at least one off-box copy if the data is important.

---

## Step 8 — Health monitoring

The `/health` endpoint returns 200 + a small JSON payload with no
auth:

```bash
curl https://mtd.example.com/health
# → {"status":"ok","version":"dev","uptime":12345}
```

Free monitors that can hit this:

| Service | Tier | Notes |
|---|---|---|
| UptimeRobot | free | 5-min interval, email alerts |
| Better Stack | free | 30-sec interval, status page |
| Healthchecks.io | free | "if you don't ping me, alert" |

Configure one to ping `/health` every 5 minutes and notify on
non-200.

---

## Step 9 — Updating

```bash
sudo systemctl stop mtd-server
sudo -u mtd git -C /opt/mtd/app pull
sudo -u mtd /opt/mtd/.venv/bin/python -m pip install --quiet \
    --upgrade -r /opt/mtd/app/requirements-server.txt
sudo systemctl start mtd-server
journalctl -u mtd-server -f
```

A package release that adds a `[server]` config key the wizard
doesn't yet know about will harmlessly use the default. Re-running
the wizard picks up new sections.

---

## Step 10 — Troubleshooting

### "Address already in use"

The default port 3000 is busy. Edit `config.toml`'s `[server] port`
to something else (8080, 8888) and `systemctl restart mtd-server`.

### "401 — authentication required" on every request

You set a password in the wizard but your browser/curl isn't sending
it. Browser: click the cancel button on the dialog and revisit with
the URL `https://user:pass@mtd.example.com/`. curl: add
`--user admin:yourpassword`.

### Translation fails with "OPENAI_API_KEY not set"

The key didn't propagate from `config.toml` to the subprocess. Check
that `MTD_CONFIG_PATH` in the systemd unit points to the actual file
and that the file's `[openai] api_key` is populated:

```bash
sudo -u mtd grep api_key /opt/mtd/config.toml
sudo systemctl cat mtd-server | grep MTD_CONFIG_PATH
```

### Out-of-memory kill

Check `dmesg | grep -i killed`. Most likely a 1 GB VPS hit the 512 MB
`MemoryMax` ceiling during a big translate+polish run. Two options:
  · raise `MemoryMax` in `/etc/systemd/system/mtd-server.service`
  · set `max_concurrent_jobs = 1` in `config.toml` if it's currently 2

### Caddy can't get a cert

Common causes:
  · DNS A record doesn't yet point to the box → wait + `dig mtd.example.com`
  · firewall blocks port 80 → `sudo ufw status` should list `80/tcp ALLOW`
  · another process bound to :80 → `sudo ss -tnlp | grep :80`

---

## Quick reference

| Action | Command |
|---|---|
| Start | `sudo systemctl start mtd-server` |
| Stop | `sudo systemctl stop mtd-server` |
| Restart after config edit | `sudo systemctl restart mtd-server` |
| Tail logs | `journalctl -u mtd-server -f` |
| Re-run wizard | `sudo -u mtd /opt/mtd/.venv/bin/python /opt/mtd/app/scripts/setup_wizard.py` |
| Manual backup now | `sudo /usr/local/sbin/mtd-backup` |
| Pull update | `sudo -u mtd git -C /opt/mtd/app pull && sudo systemctl restart mtd-server` |
| Health check | `curl http://127.0.0.1:3000/health` |
| Disk usage | `du -sh /opt/mtd/runtime_dir /var/backups/mtd` |

---

## Resource budget on a 1 GB VPS

| Component | RAM idle | RAM peak |
|---|---|---|
| Python launcher (3.11 + deps) | ~150 MB | ~200 MB |
| One translate+polish OpenAI job | +50 MB | +100 MB |
| Caddy reverse proxy | ~30 MB | ~50 MB |
| systemd + journald + cron | ~50 MB | ~50 MB |
| **Total budgeted** | ~280 MB | ~400 MB |
| **Available on a 1 GB VPS** | ~600 MB | — |

That leaves ~200 MB of headroom for OS caches, the occasional pip
upgrade, and a couple of concurrent uploads. Comfortable.
