# Agent Connections — System Prompt Template

## Overview

When a customer has active connections, the OpenClaw gateway pod receives connection
configuration via the `OPENCLAW_CONNECTIONS` environment variable. The gateway uses
this to inject connection instructions into the agent's system prompt.

## OPENCLAW_CONNECTIONS Format

```json
{
    "nango_proxy_url": "http://nango-server.platform.svc.cluster.local:8080",
    "nango_secret_key": "nango-secret-key-here",
    "connections": [
        {
            "provider": "github",
            "connection_id": "customer-uuid_github"
        },
        {
            "provider": "slack",
            "connection_id": "customer-uuid_slack"
        }
    ]
}
```

## System Prompt Addition

Add to the agent's system prompt when connections are available:

```
You have access to the following external service connections:
{{#each connections}}
- {{provider}}: Use the proxy to make API calls
{{/each}}

To call an external API, make HTTP requests to the Nango proxy:

URL: {{nango_proxy_url}}/proxy/{{api_path}}
Headers:
  - Connection-Id: {{connection_id}}
  - Provider-Config-Key: {{provider}}
  - Authorization: Bearer {{nango_secret_key}}

Example — List GitHub repos:
  GET http://nango-server.platform.svc.cluster.local:8080/proxy/user/repos
  Headers:
    Connection-Id: customer-uuid_github
    Provider-Config-Key: github
    Authorization: Bearer <nango_secret_key>

Example — Send Slack message:
  POST http://nango-server.platform.svc.cluster.local:8080/proxy/chat.postMessage
  Headers:
    Connection-Id: customer-uuid_slack
    Provider-Config-Key: slack
    Authorization: Bearer <nango_secret_key>
  Body: {"channel": "#general", "text": "Hello from OpenClaw!"}
```

## Connection ID Convention

Format: `{customer_id}_{provider}`

Example: `abc123-def456_github`

## Requesting New Connections

If the agent needs access to a service that isn't connected, it can generate a
deep link for the user:

```
/connect/{provider}?token={short-lived-token}
```

The token is generated via `POST /internal/connect-link` with:

```json
{
    "customer_id": "...",
    "provider": "github"
}
```

This returns a URL that can be sent to the user via Telegram. The user opens the
link in their browser, completes the OAuth flow, and the connection becomes
available to the agent.
