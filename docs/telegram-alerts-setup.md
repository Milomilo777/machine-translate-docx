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
or a channel). There are two ways to discover the id; pick whichever
is more convenient.

#### 2a. Easy way — `@userinfobot` (recommended)

This is the path most people pick on the first try:

1. In Telegram, in the search bar type **`@userinfobot`** (it's an
   official utility bot — no token, no setup).
2. Open it and click **Start**.
3. The bot replies *instantly* with something like:

   ```
   You
   Id: 987654321        ← this is your MTD_TELEGRAM_CHAT_ID
   First: Mousa
   Username: @…
   ```

4. Copy the `Id` number. Done.

You do **not** need to do this for the alerts bot itself — `@userinfobot`
just tells you your own user id, which is the same as your DM-with-any-bot
chat id.

#### 2b. Manual way — `getUpdates` URL in a browser

This is the original method. It only works if you've already messaged
your alerts bot at least once. Use it when `@userinfobot` is not
available (rare).

1. In Telegram, search for the username `@<your_bot_username>` of the
   bot you created in step 1 (the link `@BotFather` gave you).
2. Click **Start** (or send any message — the text doesn't matter).
3. **Open a real web browser** (Chrome / Safari / Firefox / Edge —
   *not* Telegram). Paste this URL and replace `<TOKEN>` with your
   bot token:

   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```

   ⚠️ **Common mistake** — pasting this URL *into Telegram* does
   nothing. Telegram displays it as a clickable link or a plain
   message; it does not actually fetch the URL. The fetch must
   happen from a browser, where the response is shown as JSON.

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
yet. Send any message to the bot, then refresh the URL.

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

### 4. Optional — multiple recipients

`MTD_TELEGRAM_CHAT_ID` accepts **a list** of chat ids, separated by
commas, semicolons, or whitespace. Every alert is fan-out'd to every
id in the list. Three patterns work:

#### 4a. Multiple individual people via DM

Each person:

1. Opens your bot and clicks **Start** (so the bot can DM them —
   Telegram blocks bots from messaging users who haven't opted in).
2. Finds their own chat id with `@userinfobot` (see step 2a).
3. Tells you the number.

You list them on the server:

```bash
MTD_TELEGRAM_CHAT_ID=987654321,123456789,555000111
```

✓ Pros: each person sees the alert in their own DM, on their own
device. No one else in the list can see who else is listed.
✗ Cons: if you have 10 people, you have 10 ids to maintain.

#### 4b. A private Telegram group (best for small teams)

1. In Telegram, **Create a new group**, give it a name (e.g.
   "SMTV Alerts"), add your bot as a member alongside the people
   who should receive alerts.
2. In `@BotFather`: `/setprivacy` → pick your bot → **Disable**.
   This lets the bot read every message in the group (needed only
   so it can confirm the group's id; you can re-enable it later
   without losing the id).
3. In the group, send any message (e.g. "hi"). Then in a browser
   open `https://api.telegram.org/bot<TOKEN>/getUpdates`. Look for
   `"chat":{"id":-987654321,"type":"group", …}`. Group ids start
   with a minus sign — that is part of the id, not a typo.
4. Set:

   ```bash
   MTD_TELEGRAM_CHAT_ID=-987654321
   ```

5. (Optional) re-run `/setprivacy` → **Enable** so the bot stops
   reading every group message; alerts continue to flow.

✓ Pros: one id, everyone sees alerts together, can discuss inline.
✗ Cons: any group member can see every alert. Don't add anyone you
wouldn't show every failure to.

#### 4c. A Telegram channel (best for one-way broadcast)

1. In Telegram, **Create a new channel** (Public or Private — both
   work), give it a name (e.g. "SMTV Alerts").
2. Open the channel → **Manage Channel** → **Administrators** →
   **Add Administrator** → search for your bot's username →
   add it. Give it just the **Post Messages** permission.
3. Find the channel id:
   - For a **public** channel with a username (e.g. `@smtv_alerts`),
     just use the handle: `MTD_TELEGRAM_CHAT_ID=@smtv_alerts`.
   - For a **private** channel, post any message in the channel,
     then in a browser open
     `https://api.telegram.org/bot<TOKEN>/getUpdates`. Look for
     `"chat":{"id":-1001234567890,"type":"channel", …}`. Channel
     ids start with `-100` — that is part of the id.
4. People who should receive alerts then **subscribe** to the
   channel (one click). They cannot reply (channels are one-way
   from admins to subscribers).

✓ Pros: subscribers join / leave themselves; you don't manage a
list. Subscribers can mute / unmute on their own.
✗ Cons: one-way only — no one can reply or discuss in the channel.

#### Mixing patterns

Nothing stops you from combining all three. The launcher just walks
the list and sends to every id. Example — your DM, the team group,
and a public channel:

```bash
MTD_TELEGRAM_CHAT_ID=987654321,-987654321,@smtv_alerts
```

If one id fails (bot kicked from a group, channel deleted, etc.)
the launcher logs `[telegram] recipient <id> skipped: …` and moves
on to the next. The other recipients still receive their copy.

### 5. Optional — disable the docx attachment

The launcher tries to send the input docx as a Telegram document
attachment too. If you want only the text alert (e.g. policy / size
concerns), set:

```bash
MTD_TELEGRAM_NO_ATTACHMENT=1
```

The text alert always carries the failure reason, the input filename,
the job ID, and the path of the on-disk failure archive.

---

## Troubleshooting — common first-time mistakes

### "I pasted the URL in the chat with the bot but nothing happened"

Telegram does not fetch URLs — it just displays them. The
`getUpdates` URL must be opened in a real **web browser** (Chrome,
Safari, Firefox, Edge — desktop or mobile). When opened correctly,
the page shows raw JSON. If the URL appears as a clickable link in
your Telegram chat, that means it was sent as a message, not opened.

**Fix:** copy the URL, paste it into your browser's address bar,
press Enter. Or skip the URL entirely and use `@userinfobot` (step
2a above).

### "I leaked the token in a chat / screenshot / repo"

The token is the *only* credential between the world and your bot.
Anyone who has it can post as your bot to any chat where the bot
is added. **Revoke it immediately** — do not wait:

1. In Telegram, message **`@BotFather`**.
2. Send `/revoke`.
3. Pick the bot whose token leaked.
4. `@BotFather` replies with a brand-new token. The old one stops
   working at that exact moment, even if a copy is still in the
   wild.
5. Update `MTD_TELEGRAM_TOKEN` on the server with the new value
   and restart the launcher.

The new token never has to touch any chat — write it directly into
the server's `.env` file (which is already in `.gitignore`).

### "result is empty in the JSON response"

The `getUpdates` API only returns updates the bot has received.
First-time setup: send any message to the bot, then refresh the URL.
If you used a private channel, post a message *in the channel*
(the bot must be an admin first).

### "bot can't initiate a conversation with a user"

Telegram bots **cannot DM users who haven't messaged the bot first**.
Each new recipient must open your bot and click **Start** at least
once. After that, the bot can DM them at any time.

### "The bot is in my group but I don't see a `chat.id` in `getUpdates`"

`@BotFather` ships every bot with **Group Privacy enabled by
default** — the bot only sees messages directed at it (replies,
mentions, commands). To get the group's id from `getUpdates`:

1. Mention the bot in the group ("@your_bot_username hi") OR
2. Temporarily disable privacy via `@BotFather` → `/setprivacy`
   → **Disable**, fetch the id, then re-enable for safety.

You only need to do this once — the group id never changes.

### "The bot was kicked / removed and I don't know"

The launcher logs `[telegram] recipient <id> skipped: …` whenever
a delivery fails. If you stop seeing that recipient receive alerts,
check the launcher's stdout. To re-add: invite the bot back to the
group / channel; no env change required.

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
