# 🚀 Telegram Share Bot v2

A **production-ready** Telegram bot platform for permanent file sharing, poster publishing, reactions, scheduled posts, and analytics — deployable on **Vercel** in minutes.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📄 **Permanent File Sharing** | Any file → instant permanent link. Supports docs, video, photo, audio, voice, stickers, up to 2 GB |
| 📦 **Multi-File Shares** | Bundle up to 50 files into one link |
| 🖼 **Poster Creator** | Photo + caption + up to 3 custom buttons |
| 📢 **Channel Publishing** | Publish posters to a Telegram channel |
| ⏰ **Scheduled Publishing** | Queue posts for any future UTC time |
| 👍 **Reaction System** | Live 👍 ❤️ 👎 reaction buttons with toggle voting |
| ✏️ **Inline Poster Editing** | Edit image, caption, or buttons at any time |
| 📊 **Analytics Dashboard** | Global and per-share stats |
| 🛠 **Admin Panel** | Full user/share management with ban system |
| 🔒 **Rate Limiting** | Redis-backed per-user request throttling |
| 📋 **Pagination** | All lists paginated with inline navigation |

---

## 🏗 Architecture

```
Telegram → Webhook → FastAPI → Aiogram Dispatcher
                                      ↓
                              Middleware chain
                         (Auth → Ban check → Rate limit)
                                      ↓
                              Handler Routers
                                      ↓
                            Service layer (pure async)
                                      ↓
                              Redis (Upstash)
```

**Key principles:**
- **Zero file storage** — only `file_id` strings stored in Redis
- **Stateless serverless** — each Vercel invocation is independent
- **FSM via Redis** — aiogram stores state in Redis, survives cold starts
- **Cron scheduling** — Vercel Cron calls `/cron` every minute to publish due posts

---

## 📁 Project Structure

```
telegram-share-bot-v2/
├── api/
│   ├── index.py              # FastAPI app — Vercel entry point
│   ├── config.py             # Pydantic settings
│   ├── redis_client.py       # Async Redis singleton
│   ├── middleware/
│   │   ├── auth.py           # Ban check + user upsert
│   │   └── rate_limit.py     # Per-user sliding window limits
│   ├── handlers/
│   │   ├── start.py          # /start + deep-link delivery
│   │   ├── share.py          # File capture + /my /find /delete
│   │   ├── multi.py          # /multi FSM flow
│   │   ├── poster.py         # /poster FSM + /publish
│   │   ├── edit_poster.py    # /editposter FSM
│   │   ├── reactions.py      # react: callbacks
│   │   ├── schedule.py       # /schedule FSM
│   │   ├── analytics.py      # /stats
│   │   └── admin.py          # /admin dashboard
│   ├── services/
│   │   ├── share_service.py  # Share CRUD + multi sessions
│   │   ├── poster_service.py # Poster CRUD
│   │   ├── media_sender.py   # Smart file delivery + media groups
│   │   ├── reaction_service.py # Toggle-vote reactions
│   │   ├── scheduler.py      # Schedule queue + cron processor
│   │   ├── analytics_service.py # Global counters
│   │   ├── pagination.py     # Generic paginator
│   │   └── security.py       # Ownership + ban management
│   ├── keyboards/
│   │   ├── share.py
│   │   ├── poster.py
│   │   ├── reactions.py
│   │   ├── pagination.py
│   │   └── admin.py
│   ├── states/
│   │   └── poster_states.py  # FSM state groups
│   └── utils/
│       ├── constants.py      # Redis key templates + limits
│       ├── helpers.py        # ID gen, file extraction, formatting
│       ├── validators.py     # URL, datetime, ID validation
│       └── logger.py         # Structured logging
├── vercel.json
├── requirements.txt
├── runtime.txt
├── .env.example
└── README.md
```

---

## ⚙️ Setup

### 1. Clone & install

```bash
git clone https://github.com/yourname/telegram-share-bot-v2
cd telegram-share-bot-v2
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create your bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. `/newbot` → follow prompts → copy the **token**
3. Get your **user ID** from [@userinfobot](https://t.me/userinfobot)

### 3. Set up Redis (Upstash — free)

1. Go to [upstash.com](https://upstash.com) → create a **Redis** database
2. Copy the **REST URL** — it starts with `rediss://`

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

Required variables:

| Variable | Description |
|---|---|
| `BOT_TOKEN` | From BotFather |
| `BOT_USERNAME` | Your bot's username (no @) |
| `ADMIN_ID` | Your Telegram numeric user ID |
| `REDIS_URL` | Upstash `rediss://` URL |
| `BASE_URL` | Your Vercel deployment URL |
| `WEBHOOK_SECRET` | Any strong random string |
| `DEFAULT_CHANNEL_ID` | Channel ID for publishing (optional, 0 to disable) |

---

## 🚀 Vercel Deployment

### 1. Install Vercel CLI

```bash
npm i -g vercel
```

### 2. Add secrets to Vercel

```bash
vercel secrets add bot_token       "your_bot_token"
vercel secrets add bot_username    "yourbotusername"
vercel secrets add admin_id        "123456789"
vercel secrets add redis_url       "rediss://..."
vercel secrets add base_url        "https://yourproject.vercel.app"
vercel secrets add webhook_secret  "your_random_secret"
vercel secrets add default_channel_id "0"
```

### 3. Deploy

```bash
vercel --prod
```

### 4. Register the webhook

After deployment, call the registration endpoint once:

```bash
curl -X POST https://yourproject.vercel.app/set_webhook \
  -H "x-cron-secret: your_random_secret"
```

Or open it in a browser / Postman. The bot is now live.

---

## 🤖 Command Reference

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/start <share_id>` | Receive a shared file |
| `/multi` | Start collecting files for a multi-share |
| `/poster` | Create a poster |
| `/publish <poster_id>` | Publish a poster to the default channel |
| `/editposter <poster_id>` | Edit an existing poster |
| `/schedule <poster_id> YYYY-MM-DD HH:MM` | Schedule a poster |
| `/my` | View your shares (paginated) |
| `/find <share_id>` | Look up a share by ID |
| `/delete <share_id>` | Delete one of your shares |
| `/stats` | Analytics dashboard |
| `/admin` | Admin control panel |
| `/list` | Admin: list all shares |

---

## 🔧 Local Development

```bash
# Run with uvicorn (polling not supported — use ngrok for local webhook)
uvicorn api.index:app --reload --port 8000

# Expose locally with ngrok
ngrok http 8000

# Register the ngrok URL as webhook
curl -X POST http://localhost:8000/set_webhook \
  -H "x-cron-secret: your_secret"
```

---

## 📊 Redis Key Schema

| Key pattern | Type | Purpose |
|---|---|---|
| `share:<id>` | String (JSON) | Single/multi share metadata |
| `poster:<id>` | String (JSON) | Poster template |
| `user:<id>` | String (JSON) | User profile |
| `user:<id>:shares` | Sorted Set | User's share IDs (score = created_at) |
| `user:<id>:posters` | Sorted Set | User's poster IDs |
| `reactions:<pid>:<key>` | Set | User IDs who reacted |
| `analytics:global` | Hash | Global counters |
| `schedule:<id>` | String (JSON) | Schedule record |
| `schedules:queue` | Sorted Set | Schedule IDs (score = publish_at) |
| `session:multi:<uid>` | String (JSON) | In-progress multi-collect session (TTL 1h) |
| `users` | Set | All known user IDs |
| `shares` | Set | All active share IDs |
| `banned_users` | Set | Banned user IDs |
| `rl:<uid>:<bucket>` | String | Rate-limit counter (auto-expiring) |

---

## 🔒 Rate Limits

| Bucket | Limit | Window |
|---|---|---|
| General | 10 requests | 15 seconds |
| `/multi` | 3 creations | 60 seconds |
| `/poster` | 5 publishes | 60 seconds |
| Admin | Unlimited | — |

---

## 📝 License

MIT — use freely, credit appreciated.
