# Telegram alerts — setup & security guide

> Telegram is the lowest-friction failure-alert channel: free forever,
> no IP reputation issues (unlike SMTP), no third-party signup
> (unlike SendGrid / Brevo), and the SDK is just a single HTTPS POST.
>
> When a translation job fails, the launcher will (a) archive the
> input docx + stdout + meta.json under
> `runtime_dir/failures/<job_id>__<UTC ts>/`, (b) send a short text
> message to the configured Telegram chat, and (c) optionally attach
> the input docx itself (capped at ~20 MB). All steps are best-effort
> — alerting failures never block the launcher.

---

## What you need before starting

1. A phone or computer with **Telegram** installed and a working
   Telegram account.
2. SSH or local access to the machine that runs `local_launcher.py`.
3. Two strings you'll generate below:
   - `MTD_TELEGRAM_TOKEN` — bot's secret API token
   - `MTD_TELEGRAM_CHAT_ID` — the chat to send alerts to

---

## Step-by-step setup (≈ 5 minutes)

### 1. Create a bot via @BotFather

In Telegram, search for **`@BotFather`** (the official bot for
managing bots). Open it and send these commands one by one:

```
/start
/newbot
```

`@BotFather` will ask:

- **"Choose a name for your bot."** Anything human-readable, e.g.
  `SMTV Translate Alerts`. This is what shows in chat.
- **"Choose a username for your bot."** Must end in `bot`.
  Example: `smtv_translate_alerts_bot`. If the name is taken,
  `@BotFather` rejects it; pick another.

Once you accept a username, `@BotFather` replies with something like:

```
Done! Congratulations on your new bot. You will find it at t.me/smtv_translate_alerts_bot.

Use this token to access the HTTP API:
123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

Keep your token secure and store it safely, it can be used by
anyone to control your bot.
```

**Copy that token line.** That is your `MTD_TELEGRAM_TOKEN`. Treat
it like a password — it is the only credential between the world and
your bot.

### 2. Find your chat ID

The token alone is not enough — Telegram also needs to know **which
chat** to deliver alerts to (your DM with the bot, a group you're in,
or a channel).

The simplest case is a 1:1 DM with your bot:

1. In Telegram, search for the username `@<your_bot_username>`
   (the link `@BotFather` gave you).
2. Click **Start** (or send `/start`).
3. In a **browser**, open this URL — replace `<TOKEN>` with the token
   from step 1:

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

4. You should see a JSON response. Look for `"chat":{"id":NNNNNNN,…}`.
   The number `NNNNNNN` is your `MTD_TELEGRAM_CHAT_ID`.

   Example response (abridged):

   ```json
   {
     "ok": true,
     "result": [{
       "update_id": 123,
       "message": {
         "chat": { "id": 987654321, "type": "private", … }
       }
     }]
   }
   ```

   → `MTD_TELEGRAM_CHAT_ID = 987654321`

If the `result` list is empty, the bot hasn't received any message
yet. Send `/start` to the bot once and re-fetch the URL.

### 3. Configure the launcher

On the server (or your dev machine), set two environment variables.
The simplest way is a `.env` file next to `local_launcher.py`:

```bash
# .env (NOT committed — already in .gitignore)
MTD_TELEGRAM_TOKEN=123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
MTD_TELEGRAM_CHAT_ID=987654321
```

Or export them inline before launching:

```bash
export MTD_TELEGRAM_TOKEN=…
export MTD_TELEGRAM_CHAT_ID=…
python local_launcher.py
```

On Windows (`cmd`):

```bat
set MTD_TELEGRAM_TOKEN=…
set MTD_TELEGRAM_CHAT_ID=…
E:\Python311\python.exe local_launcher.py
```

That's it. Restart the launcher; the next time a job fails you'll
get a Telegram message within ~1 second.

### 4. Optional — disable the docx attachment

The launcher tries to send the input docx as a Telegram document
attachment too. If you want only the text alert (e.g. policy / size
concerns), set:

```bash
MTD_TELEGRAM_NO_ATTACHMENT=1
```

The text alert always carries the failure reason, the input filename,
the job ID, and the path of the on-disk failure archive.

---

## Security best practices

### Treat the token like a password

- Never commit the token to git. The `.env` pattern above + the
  existing `.gitignore` rule keep it out.
- Never paste the token in a chat, screenshot, or screen-share
  unless you're prepared to revoke it immediately afterwards.
- If you suspect leakage, run **`/revoke`** to `@BotFather` and
  generate a new token. The old one stops working instantly.

### What an attacker who steals the token CAN do

- Send messages **as your bot** to any chat where your bot has
  been added. They cannot read messages sent by other users to
  the bot unless that bot processes commands (this one does not).
- Read past messages **only** if the bot is in a group with
  history enabled and the attacker can see the same updates.

### What they CANNOT do

- Read your DMs, contacts, or other Telegram chats.
- Impersonate you (the bot is a separate identity).
- Reach the launcher itself — the token is for **outbound** API
  calls only; the launcher does not poll updates.

### Rate limits / abuse protection

- Telegram throttles 30 messages/sec per chat. The launcher sends
  at most one message per failure (plus one document) so this is
  effectively unlimited for our use.
- If the alert call ever times out (10 s default), the launcher
  swallows the exception and continues — you'll never see a job
  hang because Telegram is down.
- The token is sent over HTTPS only; Telegram pins TLS for its
  Bot API endpoints.

### Privacy

- Messages flow to `api.telegram.org` (Telegram-operated servers,
  Singapore + global edge). The input docx, if attached, is stored
  on Telegram's media servers indefinitely (until the chat is
  cleared). If your docs contain sensitive content, set
  `MTD_TELEGRAM_NO_ATTACHMENT=1` and rely on the local
  `runtime_dir/failures/` archive for inspection.

### Hardening checklist

- [ ] Token in env only, never in code, command-line, or shared
      logs.
- [ ] `.env` in `.gitignore` (already is).
- [ ] Bot is a private 1:1 DM, not in a public group.
- [ ] If you must use a group, disable bot's "Group privacy" via
      `@BotFather` → `/mybots` → Bot Settings → Group Privacy →
      `Enable` (default; means bot only sees commands directed at
      it, not every group message).
- [ ] Periodically run `/myinfo` in `@BotFather` to confirm the
      bot's identity hasn't been altered.
- [ ] Keep `MTD_TELEGRAM_NO_ATTACHMENT=1` if your docs are sensitive
      and you only need the text alert.

---

## Quick test from the command line

After setting the two env vars, you can fire a manual test alert:

```bash
python -c "
import os, json, urllib.request
url = f'https://api.telegram.org/bot{os.environ[\"MTD_TELEGRAM_TOKEN\"]}/sendMessage'
req = urllib.request.Request(
    url,
    data=json.dumps({
        'chat_id': os.environ['MTD_TELEGRAM_CHAT_ID'],
        'text':    'Test alert from machine-translate-docx setup.'
    }).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
print(urllib.request.urlopen(req, timeout=10).read().decode())
"
```

Expected: a JSON response starting with `{"ok":true,…}` and a
matching message in your Telegram chat within a second. If you see
`{"ok":false,…}`, the error message inside is usually self-
explanatory (`Unauthorized` = bad token; `chat not found` = wrong
chat_id; `bad request` = chat_id type wrong, etc.).

---

## Revoking access

To kill the bot entirely:

1. In Telegram, message `@BotFather`.
2. Send `/deletebot`, pick the bot, confirm.

To rotate the token without deleting the bot:

1. `@BotFather` → `/revoke` → pick the bot.
2. Update `MTD_TELEGRAM_TOKEN` on the server, restart the launcher.
