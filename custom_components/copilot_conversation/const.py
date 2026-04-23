"""Constants for the GitHub Copilot Conversation integration."""

DOMAIN = "copilot_conversation"

# ---------------------------------------------------------------------------
# Config keys
# ---------------------------------------------------------------------------
CONF_GITHUB_TOKEN = "github_token"
CONF_MODEL = "model"
CONF_PROMPT = "prompt"
CONF_MAX_TOKENS = "max_tokens"
CONF_TEMPERATURE = "temperature"
CONF_CONTINUE_CONVERSATION = "continue_conversation"
# Note: device control uses HA's native CONF_LLM_HASS_API from homeassistant.const

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "gpt-4.1"
DEFAULT_MAX_TOKENS = 1024
DEFAULT_TEMPERATURE = 0.7
DEFAULT_CONTINUE_CONVERSATION = False

DEFAULT_PROMPT = (
    "You are a helpful voice assistant for a smart home called {{ ha_name }}.\n"
    "Answer in the same language the user speaks.\n"
    "Be concise and friendly.\n"
    "Today is {{ now().strftime('%A, %B %d, %Y') }}."
)


# ---------------------------------------------------------------------------
# API & OAuth
# ---------------------------------------------------------------------------
COPILOT_API_BASE = "https://api.githubcopilot.com"
COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"

# VS Code Copilot Chat OAuth App Client ID (used for Device Flow)
GITHUB_OAUTH_CLIENT_ID = "Iv1.b507a08c87ecfe98"
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_DEVICE_LOGIN_URL = "https://github.com/login/device"

# Headers that mimic VS Code Copilot Chat (required for API access)
COPILOT_HEADERS = {
    "Copilot-Integration-Id": "vscode-chat",
    "User-Agent": "GitHubCopilotChat/0.26.7",
    "Editor-Version": "vscode/1.104.1",
    "Editor-Plugin-Version": "copilot-chat/0.26.7",
    "editor-version": "vscode/1.104.1",
    "editor-plugin-version": "copilot-chat/0.26.7",
    "copilot-vision-request": "true",
}

# GitHub token prefixes that can be exchanged for a short-lived Copilot token.
# Copilot tokens themselves start with "tid=" and must NOT be re-exchanged.
EXCHANGEABLE_TOKEN_PREFIXES = ("gho_", "ghp_", "ghu_", "github_pat_")

# Buffer (seconds) before token expiry to trigger a proactive refresh
TOKEN_REFRESH_BUFFER_SECS = 60

# Max tool-call round-trips to prevent infinite loops
MAX_TOOL_ITERATIONS = 10
