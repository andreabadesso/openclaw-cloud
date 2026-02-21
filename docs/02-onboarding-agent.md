# Onboarding Agent

The onboarding agent is the heart of the product experience. A non-technical user opens a chat — on the web or directly in Telegram — and an AI conducts a natural conversation that ends with a fully configured, running OpenClaw agent.

No TOML. No SSH. No Nix.

---

## Design Goals

- **Conversational, not form-based** — feels like talking to a knowledgeable friend, not filling out a signup wizard
- **Short** — the happy path is 5–7 exchanges. We don't interrogate users
- **Smart defaults** — the agent infers as much as possible (timezone from browser, language from message, tier from described use case)
- **Recoverable** — sessions persist 24h; users can come back and resume
- **Transparent** — the agent explains what it's setting up and why

---

## Technology Stack

- **Runtime**: Python 3.12
- **LLM**: Kimi Code (`kimi-coding/k2p5`) via the platform's token-proxy
- **Framework**: LangChain with a custom `ConversationChain` + tool use
- **State**: Redis (session TTL 24h), persisted to Postgres on completion
- **Transport**: WebSocket relay via `api` service → `web` frontend

---

## Session State Machine

```
NEW → GREETING → GATHERING_USE_CASE → GATHERING_TELEGRAM
    → GATHERING_PREFERENCES → RECOMMENDING_TIER
    → AWAITING_PAYMENT → PROVISIONING → COMPLETE
                                      ↘ FAILED
```

Each state is stored in Redis keyed by `session:{session_id}`. On WebSocket reconnect, the session resumes from the last saved state.

---

## Conversation Flow

### Step 1: Greeting & Use Case

```
Agent: Hey! I'm going to set up your personal AI coding agent. It'll be
       yours — running 24/7, accessible via Telegram.

       First: what do you mainly want it to help you with?
       (e.g. "review my code", "write tests", "help me learn Rust",
       "answer questions about my codebase")

User:  I want it to help me write Python code and review PRs

Agent: Love it. Python + code review — a solid combo.

       A few quick ones:
       - What language do you prefer for conversations? (I detected English)
       - Roughly how active do you expect to be? A few chats a day, or
         hammering it all day?
```

### Step 2: Telegram Setup

```
Agent: Your agent lives in Telegram. Do you already have a Telegram bot
       token, or do you need help creating one?

       [I have a token] [Help me create one]

User:  Help me create one

Agent: Easy. Here's how:
       1. Open Telegram and search for @BotFather
       2. Send /newbot
       3. Choose a name (e.g. "My Coding Agent") and a username (e.g. mycodingbot)
       4. BotFather will send you a token like: 7123456789:AAH...

       Paste your token here when you have it.

User:  7123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Agent: Got it ✓ — I'll keep that safe and encrypted.

       One last thing: what's your Telegram user ID? (I need it so only
       you can talk to your agent)

       Not sure? Message @userinfobot on Telegram — it'll reply with your ID.

User:  123456789
```

### Step 3: Tier Recommendation

Based on the gathered data, the agent reasons over `box.toml` parameters and selects a tier:

```
Agent: Based on what you've told me, here's what I'd set up for you:

       ┌─────────────────────────────────────────┐
       │  Your OpenClaw Agent                    │
       │                                         │
       │  Model:    Kimi k2p5 (thinking: medium) │
       │  Language: English                      │
       │  Server:   2 CPU · 4 GB RAM · 40 GB SSD │
       │  Tokens:   2,000,000 / month            │
       │                                         │
       │  Plan: Pro — $49/month                  │
       └─────────────────────────────────────────┘

       You mentioned you're fairly active, so I went with Pro to make sure
       you don't hit limits mid-conversation. But Starter ($19/mo) works
       fine if you want to try first.

       Which would you like?

       [Starter · $19/mo]  [Pro · $49/mo · Recommended]  [Team · $129/mo]
```

### Step 4: Payment → Provisioning

```
[User selects Pro → Stripe Checkout opens]

[Payment succeeds → Stripe webhook fires]

Agent: Payment confirmed! Setting up your agent now...

       ⏳ Creating your server... (Hetzner cloud)
       ✅ Server created (your-name.agents.openclaw.cloud)
       ⏳ Installing NixOS + OpenClaw...
       ✅ OpenClaw configured and running
       ⏳ Connecting Telegram bot...
       ✅ Bot connected

       🎉 Your agent is live!

       Open Telegram and message your bot:
       → @yourcodingbot_bot

       Say "hello" to test it. It'll respond within a few seconds.

       Your dashboard is at: app.openclaw.cloud/dashboard
       Monthly token usage and settings are all there.
```

---

## Agent System Prompt

```
You are the OpenClaw onboarding assistant. Your job is to set up a personal
AI coding agent for the user. You are friendly, concise, and technically
knowledgeable but never condescending.

You are collecting the following information to configure the agent:
1. use_case: what the user wants the agent to help with (free text)
2. language: preferred conversation language (default: detected from messages)
3. activity_level: low / medium / high (inferred from description)
4. telegram_bot_token: a valid Telegram bot token
5. telegram_user_id: the user's Telegram numeric ID
6. tier: starter / pro / team (recommended based on activity)

Rules:
- Never ask for more than 2 pieces of information per message
- If you can infer something from context, do — don't ask
- The telegram_bot_token MUST be validated (format: digits:alphanum, 46+ chars)
- Do NOT mention Nix, NixOS, nixos-anywhere, TOML, or SSH to the user
- Keep each message under 150 words
- Use plain language, not technical jargon
- When the user is ready to pay, output a JSON config block for the system
  to parse (see format below)

Config output format (emit when state=RECOMMENDING_TIER and user confirms tier):
<config>
{
  "use_case": "...",
  "language": "en",
  "activity_level": "medium",
  "telegram_bot_token": "...",
  "telegram_user_id": 123456789,
  "tier": "pro",
  "thinking_level": "medium",
  "model": "kimi-coding/k2p5"
}
</config>
```

---

## Tier Inference Logic

The agent uses this heuristic (can be tuned):

| Signal | → Tier |
|---|---|
| "just trying out", "personal project", "hobby" | Starter |
| "daily use", "my team", "work projects" | Pro |
| "all day", "production codebase", "multiple people" | Team |
| No signal | Pro (safe default) |

The agent explains the recommendation briefly and always lets the user choose.

---

## Config → box.toml Translation

When the agent outputs a `<config>` block, the `onboarding-agent` service parses it and translates it into a `box.toml` for the operator:

```python
def config_to_box_toml(config: OnboardingConfig, box_name: str, proxy_token: str) -> str:
    tier = TIERS[config.tier]
    return f"""
hostname    = "{box_name}"
system      = "x86_64-linux"
timezone    = "{config.timezone}"
locale      = "{LANG_LOCALES[config.language]}"
stateVersion = "25.11"

[boot]
mode = "bios"

[disk]
device = "/dev/sda"

[swap]
size = {tier.swap_mb}

[networking]
ports = [22]

[sops]
ageKeyPaths = ["/etc/ssh/ssh_host_ed25519_key"]
secrets = ["kimi_proxy_token", "telegram_bot_token"]

[root]
sshKeys = ["{OPERATOR_SSH_PUBLIC_KEY}"]

[[users]]
name = "openclaw"
shell = "bash"
groups = ["wheel"]
sshKeys = ["{OPERATOR_SSH_PUBLIC_KEY}"]

[openclaw]
enable = true

[openclaw.agents]
model = "{config.model}"
thinkingDefault = "{config.thinking_level}"

[openclaw.telegram]
tokenFile = "/run/secrets/telegram_bot_token"
allowFrom = [{config.telegram_user_id}]

[openclaw.env]
KIMI_BASE_URL = "https://proxy.openclaw.cloud/v1"
KIMI_API_KEY  = "/run/secrets/kimi_proxy_token"
"""
```

The proxy token is a customer-specific token generated at provisioning time, stored in the operator's secrets vault (Hashicorp Vault or K8s Secrets), and injected into the box's SOPS secrets.

---

## Resumable Sessions

If a user closes the browser mid-conversation, the session is stored in Redis with TTL 24h. On return:
- Via web: session cookie restores the chat
- Via Telegram: user DMs the onboarding bot; the bot recognizes the Telegram ID and resumes

Sessions that reach `AWAITING_PAYMENT` and never pay are cleaned up after 24h via a cron job.
