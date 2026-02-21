ALL_PROVIDERS = ["github", "google", "slack", "linear", "notion", "jira"]

PROVIDER_EXAMPLES: dict[str, dict] = {
    "github": {
        "name": "GitHub",
        "example": "GET /proxy/user/repos",
        "description": "GitHub API (repos, issues, PRs, code search)",
    },
    "slack": {
        "name": "Slack",
        "example": "POST /proxy/chat.postMessage with body {\"channel\":\"#general\",\"text\":\"Hello!\"}",
        "description": "Slack API (messages, channels, users)",
    },
    "linear": {
        "name": "Linear",
        "example": "POST /proxy/graphql with body {\"query\":\"{ issues { nodes { title state { name } } } }\"}",
        "description": "Linear API (issues, projects, cycles)",
    },
    "notion": {
        "name": "Notion",
        "example": "POST /proxy/v1/search with headers Notion-Version: 2022-06-28 and body {\"query\":\"\"}",
        "description": "Notion API (pages, databases, blocks)",
    },
    "google": {
        "name": "Google",
        "example": "GET /proxy/calendar/v3/calendars/primary/events?maxResults=10",
        "description": "Google API (calendar, drive, gmail)",
    },
    "jira": {
        "name": "Jira",
        "example": "GET /proxy/rest/api/3/search?jql=assignee=currentUser()",
        "description": "Jira API (issues, projects, boards)",
    },
}
