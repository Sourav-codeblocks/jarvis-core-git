# Jarvis Core — Daily Commands

Droplet: `159.89.166.167`. Everything below runs there over SSH — this
file no longer reflects local dev (ngrok tunnel etc.), which was the
workflow before the droplet deployment existed. If you're doing local
dev again for some reason, that section is preserved at the bottom.

## SSH in
ssh root@159.89.166.167
(swap `root` for whatever user you actually use, if different)

## Restart a tenant's bot after a code change
sudo systemctl restart jarvis-gateway          # Keshri Pipes
sudo systemctl restart jarvis-gateway-mihika   # Mihika's Studio
sudo systemctl restart jarvis-gateway-dance    # My Dance Academy

## Check a service is actually up (not crash-looping)
sudo systemctl status jarvis-gateway --no-pager
# (swap in -mihika / -dance as needed)

## Watch a bot's live logs while testing in Telegram
sudo journalctl -u jarvis-gateway -f
# Ctrl+C to stop following. Useful to open in a SECOND ssh window so you
# can still run other commands (e.g. DB checks) while it tails.

## Apply a code fix safely (the pattern used throughout 2026-08-01 session)
cd /opt/jarvis-core   # or whichever tenant folder
# 1. Write a self-contained apply_*.py patch script: backs up the target
#    file, does an exact-string replace (asserts the old text exists
#    first so it fails loudly instead of silently no-op'ing), writes the
#    result.
python3 apply_whatever_fix.py
python3 -m py_compile <changed_file>.py && echo "COMPILE OK"
# 2. VERIFY the patch actually landed -- don't trust "COMPILE OK" alone,
#    it only proves the file still parses, not that your edit applied.
grep -n "<new text>" <changed_file>.py     # should find it
grep -n "<old text>" <changed_file>.py     # should find NOTHING
# 3. Only then restart + retest live + commit.

## Check real data (Supabase) from the droplet
# Use the VENV's python, not system python -- system python doesn't have
# supabase/dotenv installed and will throw ModuleNotFoundError.
cd /opt/jarvis-core
cat > /tmp/check_something.py << 'EOF'
import os
from dotenv import load_dotenv
load_dotenv("/opt/jarvis-core/.env")   # pass the path explicitly when
                                         # running via heredoc/stdin --
                                         # find_dotenv() can't locate a
                                         # caller frame in that case.
from supabase import create_client
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
# ... your query here ...
EOF
/opt/jarvis-core/venv/bin/python3 /tmp/check_something.py

## Git — per tenant folder, all now under version control
cd /opt/jarvis-core   # or -mihika / -dance
git status
git add -A && git commit -m "..."
git push origin droplet-live    # Keshri Pipes only has a real remote so far

## Company profile edits (Keshri Pipes)
# Edit the real source file, NOT Supabase directly, so they stay in sync:
nano /opt/jarvis-core/data/keshri/company_profile.md
/opt/jarvis-core/venv/bin/python3 /opt/jarvis-core/load_company_profile.py --tenant keshri-pipes --file data/keshri/company_profile.md
# IMPORTANT: restart the gateway after -- resolve_tenant() caches the
# profile, the loader does NOT clear it automatically (found live
# 2026-08-01, cost real time before we realized the reload wasn't taking
# effect without a restart).
sudo systemctl restart jarvis-gateway

## Nginx routes (all three bots, one droplet)
# /webhook/telegram              -> 8000 (Keshri Pipes)
# /mihika/webhook/telegram       -> 8001 (Mihika's Studio, rewritten)
# /dance/webhook/telegram        -> 8002 (My Dance Academy, rewritten)
# Config: /etc/nginx/sites-available/jarvis

## Check current Telegram webhook for a bot
source .env   # in that tenant's folder, for its own TELEGRAM_BOT_TOKEN
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"

## End a session
# 1. Update PROGRESS.md (what got done + NEXT line)
# 2. git add -A && git commit -m "..." in every folder touched
# 3. git push where a remote exists
# 4. Write/update the session handoff doc if the session was substantial

---

## Old local-dev workflow (pre-droplet, kept for reference only)
# This was used before the droplet existed. Not the current workflow --
# everything now runs on 159.89.166.167 directly, no tunnel needed.

# T1 — gateway (local machine)
cd ~/Documents/IIT_Mandi_AgenticAI/Jarvis_Core && conda activate jarvis-core
uvicorn main:app --reload

# T2 — ngrok tunnel (new URL every restart on free tier)
ngrok http 8000

# T3 — re-register webhook against the new ngrok URL
source .env
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=https://NEW-NGROK-URL.ngrok-free.dev/webhook/telegram"

# SSH tunnel to dslab (original local-Ollama setup, likely also obsolete
# now that cloud providers are in the fallback chain -- confirm before
# relying on this)
ssh -L 11434:localhost:11434 teaching@172.18.40.103
