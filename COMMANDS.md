# Jarvis Core — Daily Commands

## Start a dev session (3 terminals)
# T1 — gateway
cd ~/Documents/IIT_Mandi_AgenticAI/Jarvis_Core && conda activate jarvis-core
uvicorn main:app --reload

# T2 — ngrok tunnel (note the new URL it prints!)
ngrok http 8000

# T3 — re-register webhook (EVERY ngrok restart, new URL each time)
source .env
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=https://NEW-NGROK-URL.ngrok-free.dev/webhook/telegram"

## End a session
# 1. Update PROGRESS.md (what got done + NEXT line) AND README.md (if
#    architecture/infra/files changed — not every session needs this,
#    but check). Starting 2026-07-13: both, every session, not just PROGRESS.
# 2. git add -A && git commit -m "..."

## Reference
# Check current webhook:  curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
# SSH tunnel to dslab:    ssh -L 11434:localhost:11434 teaching@172.18.40.103
# Edit file from terminal: open -e <filename>