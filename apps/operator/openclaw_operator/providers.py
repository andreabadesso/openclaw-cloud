"""Provider configuration for customer pod integrations.

Providers are split into two categories:

- NATIVE_PROVIDERS: Handled by openclaw's built-in tools/skills.
  The OAuth token from Nango is injected as an env var that openclaw
  already knows how to read.

- MCP_SERVERS: No native openclaw support — access via mcporter MCP servers.
"""

# Providers with native openclaw tool/skill support.
# key = provider name, value = env var the native tool expects.
NATIVE_PROVIDERS: dict[str, str] = {
    "github": "GH_TOKEN",
    "notion": "NOTION_API_KEY",
    "slack": "SLACK_BOT_TOKEN",
}

# Providers that require MCP servers (no native openclaw support).
MCP_SERVERS: dict[str, dict] = {
    "linear": {
        "type": "http",
        "baseUrl": "https://mcp.linear.app/sse",
    },
    "jira": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "mcp-atlassian"],
        "tokenEnv": "JIRA_API_TOKEN",
    },
    "google": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/google-drive-mcp"],
        "tokenEnv": "GOOGLE_ACCESS_TOKEN",
    },
}
