"""MCP server configuration per provider for mcporter integration."""

MCP_SERVERS: dict[str, dict] = {
    "linear": {
        "type": "http",
        "baseUrl": "https://mcp.linear.app/sse",
    },
    "github": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/github-mcp-server"],
        "tokenEnv": "GITHUB_PERSONAL_ACCESS_TOKEN",
    },
    "notion": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@notionhq/notion-mcp-server"],
        "tokenEnv": "NOTION_TOKEN",
    },
    "slack": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@anthropic/slack-mcp-server"],
        "tokenEnv": "SLACK_BOT_TOKEN",
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
