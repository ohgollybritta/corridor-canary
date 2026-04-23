# corridor-canary — Raspberry Pi setup (Sage host)

Matched to your existing Sage setup: ntfy.sh, Pi user `sage`, system-level systemd services.

## 0. Prereqs

Already on the Pi if Sage is running. Quick confirm:

```bash
python3 --version      # 3.9+ fine; 3.11+ better
which git
```

## 1. Pick a new ntfy topic

Your family's phones are subscribed to Sage's topic (in `~/.sage_config.json` as `ntfy_topic`). **Do not reuse it.** Pick something new, long, and unguessable:

```bash
# Quick generator
echo "canary-corridor-$(head /dev/urandom | tr -dc a-z0-9 | head -c 8)"
```

Remember the value you pick — phone subscribes to this exact string. On ntfy.sh free tier the topic name *is* the access control, so treat it like a password and don't paste it in public.

## 2. Clone

```bash
cd /home/sage
git clone https://github.com/ohgollybritta/corridor-canary.git
cd corridor-canary
```

(Or scp the tarball over and extract.)

## 3. Virtualenv + deps

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 4. Configure

```bash
mkdir -p /home/sage/.config/corridor-canary
cp .env.example /home/sage/.config/corridor-canary/env
chmod 600 /home/sage/.config/corridor-canary/env
nano /home/sage/.config/corridor-canary/env
```

Fill in `NTFY_TOPIC` with the topic you generated. `NTFY_SERVER` is already set to `https://ntfy.sh`. Leave `NTFY_TOKEN` blank.

## 5. Subscribe on your phone

Open the ntfy app → **Add subscription** → paste the same topic string → set it to `max` priority (so alerts punch through Do Not Disturb if you want them to; adjust to taste).

**Do not** add this topic to anyone else's phone.

## 6. Verify ntfy

```bash
set -a; . /home/sage/.config/corridor-canary/env; set +a
.venv/bin/python corridor-canary.py --test
```

Phone should buzz once with "corridor-canary test". If not, quick curl sanity check:

```bash
curl -d "manual test from Pi" "$NTFY_SERVER/$NTFY_TOPIC"
```

If that works but `--test` doesn't, the env file isn't loading — check the `set -a` line and the file path.

## 7. Dry-run the matcher against the live feed

```bash
.venv/bin/python corridor-canary.py --dry-run
```

Expected: `entries=N new=N pushed=0 first_run=True`. `N` is current feed size.

## 8. Install as system-level systemd service (matches Sage pattern)

Your existing Sage runs system-level as user `sage`. Doing the same here for consistency:

```bash
sudo tee /etc/systemd/system/corridor-canary.service > /dev/null << 'EOF'
[Unit]
Description=corridor-canary NCMEC missing-child watcher (southern US-1)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=sage
Group=sage
EnvironmentFile=/home/sage/.config/corridor-canary/env
WorkingDirectory=/home/sage/corridor-canary
ExecStart=/home/sage/corridor-canary/.venv/bin/python /home/sage/corridor-canary/corridor-canary.py

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/sage/.local/state/corridor-canary
EOF

sudo tee /etc/systemd/system/corridor-canary.timer > /dev/null << 'EOF'
[Unit]
Description=Run corridor-canary every 20 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=20min
RandomizedDelaySec=90
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Pre-create state dir (ProtectHome=read-only blocks the service from mkdir)
sudo -u sage mkdir -p /home/sage/.local/state/corridor-canary

sudo systemctl daemon-reload
sudo systemctl enable --now corridor-canary.timer

systemctl list-timers | grep canary
systemctl status corridor-canary.timer
```

Tail logs:

```bash
sudo journalctl -u corridor-canary.service -f
```

## 9. Verify over a full cycle

Wait ~20 minutes after the first seed run. Then:

```bash
sudo journalctl -u corridor-canary.service --since "1 hour ago"
sudo -u sage cat /home/sage/.local/state/corridor-canary/seen.json | python3 -m json.tool | head
```

Expect:
- First fire: `first_run=True pushed=0` (seeding)
- Subsequent fires: `first_run=False pushed=0` most of the time — correct, no new in-corridor alerts
- Occasional fires: `pushed=1+` when a matching entry lands, phone buzzes once

## 10. Watchlist tweaks

Edit `/home/sage/corridor-canary/watchlist.py`. No restart needed — the service re-imports on every timer fire.

## 11. Uninstall

```bash
sudo systemctl disable --now corridor-canary.timer
sudo rm /etc/systemd/system/corridor-canary.{service,timer}
sudo systemctl daemon-reload
# Optional: remove state + config
rm -rf /home/sage/.local/state/corridor-canary /home/sage/.config/corridor-canary
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Feed fetch failed: 403` | NCMEC blocked the UA string. Update `CANARY_UA` in env with a real contact address. |
| Service runs but never pushes | Check that `first_run=False` in logs and the feed actually contains in-corridor entries. Run `--dry-run` with a widened watchlist briefly to confirm the matcher fires at all. |
| `ProtectSystem` / write errors | State dir wasn't pre-created. `sudo -u sage mkdir -p /home/sage/.local/state/corridor-canary` and retry. |
| Phone not receiving | Confirm phone is subscribed to the exact topic string (case-sensitive). Try the curl test in step 6. |
| Duplicate pushes | Shouldn't happen — if it does, save `seen.json` and open an issue. GUID dedupe is supposed to prevent this. |

## Integration notes with Sage itself

The canary is deliberately **not** wired into Sage's voice loop. No announcement, no LED state change, no bedtime suppression, no chime. It's a silent watcher that only writes to ntfy.

If later you want it to respect Sage's bedtime mode (suppress phone pushes between 10pm and 7am when Sage is asleep), the simplest hook is a small flag file Sage writes on `goodnight` / `good morning`. The canary can check for its presence and skip `push_ntfy()`. Say the word if you want that bolted on.
