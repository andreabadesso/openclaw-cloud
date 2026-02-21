# Agent Connections — System Prompt Template

## Overview

When a customer has active connections, the OpenClaw gateway pod receives connection
configuration via the `OPENCLAW_CONNECTIONS` environment variable. The container
entrypoint generates a static `AGENTS.md` in the workspace directory that instructs
the agent to call the platform API at runtime to discover connections dynamically.

This means connections can be added/removed without rebuilding the pod — the agent
always gets fresh data by calling the API.

## OPENCLAW_CONNECTIONS Format

```json
{
    "nango_proxy_url": "http://nango-server.platform.svc.cluster.local:8080",
    "nango_secret_key": "nango-secret-key-here",
    "api_url": "http://api.platform.svc.cluster.local:8000",
    "api_secret": "shared-agent-secret",
    "customer_id": "customer-uuid",
    "web_url": "http://10.69.1.217:3000",
    "connections": [
        {
            "provider": "github",
            "connection_id": "customer-uuid_github"
        }
    ]
}
```

## Generated AGENTS.md

The entrypoint generates a **static** `AGENTS.md` that only contains:
- The API URL, auth header, and customer ID
- Instructions to call `GET /internal/agent/connections` to discover live connections
- Instructions to call `POST /internal/agent/connect-link` to request new ones

The agent fetches connection details at runtime, so they're always up to date.

## API Endpoints

### GET /internal/agent/connections

Returns the current connection config for a customer. Authenticated via shared secret.

**Headers:**
- `Authorization: Bearer <AGENT_API_SECRET>`
- `X-Customer-Id: <customer_id>`

**Response:**
```json
{
    "proxy_url": "http://nango-server.platform.svc.cluster.local:8080",
    "proxy_headers": {
        "Connection-Id": "<connection_id>",
        "Provider-Config-Key": "<provider>",
        "Authorization": "Bearer <nango_secret>"
    },
    "connections": [
        {
            "provider": "github",
            "connection_id": "customer-uuid_github",
            "provider_config_key": "github",
            "example": "GET /proxy/user/repos",
            "description": "GitHub API (repos, issues, PRs, code search)"
        }
    ],
    "available_providers": [
        {
            "provider": "slack",
            "name": "Slack",
            "example": "POST /proxy/chat.postMessage with body {...}",
            "description": "Slack API (messages, channels, users)"
        }
    ]
}
```

### POST /internal/agent/connect-link

Generates a deep-link URL for OAuth. Authenticated via shared secret.

**Headers:**
- `Authorization: Bearer <AGENT_API_SECRET>`
- `Content-Type: application/json`

**Request:**
```json
{
    "customer_id": "...",
    "provider": "github"
}
```

**Response:**
```json
{
    "url": "http://host:3000/connect/github?token=<short-lived-token>"
}
```

The token expires after 15 minutes.

## Connection ID Convention

Format: `{customer_id}_{provider}`

Example: `abc123-def456_github`

## NetworkPolicy

Customer pods are allowed egress to:
- `token-proxy` (port 8080) — LLM API proxy
- `nango-server` (port 8080) — Nango proxy for authenticated API calls
- `api` (port 8000) — internal agent endpoint for connection discovery and deep-link generation
- Public IPs (port 443) — Telegram API
- CoreDNS (UDP 53) — DNS resolution
