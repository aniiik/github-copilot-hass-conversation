<a name="readme-top"></a>

<div align="center">
  <h1>GitHub Copilot Conversation</h1>
  <p><strong>Home Assistant custom integration — use GitHub Copilot as a conversation agent with access to GPT-4.1, Claude, Mistral, Llama, and more.</strong></p>

  <p><em>This is not an officially supported integration and is not affiliated with GitHub or Microsoft.</em></p>

  [![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
  [![HA Version](https://img.shields.io/badge/Home%20Assistant-2023.5%2B-blue?style=for-the-badge&logo=home-assistant)](https://www.home-assistant.io/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
</div>

---

## Table of Contents

1. [About](#about)
2. [Features](#features)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Options](#options)
7. [Controlling devices](#controlling-devices)
8. [Using as a service action](#using-as-a-service-action)
9. [FAQ](#faq)
10. [License](#license)

---

## About

This integration makes **GitHub Copilot** available as a conversation agent inside Home Assistant's built-in Assist voice pipeline. It authenticates via GitHub's Device Flow OAuth (the same flow VS Code uses) and talks to the Copilot API directly using raw `aiohttp` — **zero pip dependencies**.

Because GitHub Copilot's API is OpenAI-compatible, you get access to a wide range of models through a single Copilot subscription — no separate API keys needed.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Features

| Feature | Status | Description |
|---|---|---|
| Conversation agent in HA Assist | Done | Selectable as agent in Voice Assistants |
| Smart home control | Done | Control lights, switches, covers, locks, etc. via HA's LLM API |
| Multi-model support | Done | GPT-4.1, GPT-4o, Claude Sonnet, Mistral, Llama, DeepSeek, and more |
| Dynamic model discovery | Done | Available models fetched from Copilot API at setup and in options |
| Streaming responses | Done | Words appear progressively in the HA UI |
| Device Flow OAuth | Done | No API key to paste — authorize via github.com/login/device |
| Conversation memory | Done | Context kept per session via HA's ChatLog |
| Jinja2 system prompt | Done | Templates with `{{ now() }}`, `{{ ha_name }}` etc. |
| Multilingual | Done | Responds in the user's language |
| Continue conversation | Done | Keeps microphone open after questions (Experimental) |
| Zero dependencies | Done | Pure `aiohttp` — no openai SDK, no langchain |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Requirements

| Requirement | Details |
|---|---|
| Home Assistant Core | 2023.5+ |
| GitHub account | With an active [GitHub Copilot](https://github.com/features/copilot) subscription |

No API keys, no pip packages, no external services beyond GitHub.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Installation

### Via HACS (recommended)

1. HACS > **Integrations** > three-dot menu > **Custom repositories**
2. URL: `https://github.com/aniiik/github-copilot-hass-conversation` — category: **Integration**
3. Search "GitHub Copilot Conversation" > **Download**
4. **Fully restart** Home Assistant

### Manual

1. Copy `custom_components/copilot_conversation/` to your HA `/config/custom_components/` directory
2. **Fully restart** Home Assistant (not just reload)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Configuration

### Setting up the integration

1. **Settings > Devices & Services > + Add Integration**
2. Search for **GitHub Copilot Conversation**
3. A device code screen appears — open [github.com/login/device](https://github.com/login/device) in your browser and enter the displayed code
4. After authorizing, choose your preferred AI model from the dropdown
5. Done — the integration verifies your Copilot subscription automatically

### Selecting as voice assistant

1. **Settings > Voice Assistants** > click your assistant
2. Set **Conversation agent** to **GitHub Copilot Conversation**
3. Save

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Options

Click the integration > **Configure** to change settings.

| Option | Default | Description |
|---|---|---|
| **AI model** | `openai/gpt-4.1` | Which model to use (fetched dynamically from Copilot API) |
| **System prompt** | See below | Jinja2 template with AI instructions |
| **Control Home Assistant** | Off | Allow the AI to control exposed devices via HA's LLM API |
| **Temperature** | `0.7` | Creativity: 0.0 = deterministic, 2.0 = creative |
| **Max tokens** | `1024` | Maximum response length |
| **Continue conversation** | Off | Keep listening after questions (Experimental) |

### System prompt

The system prompt supports Jinja2 templates:

```jinja2
You are a helpful voice assistant for {{ ha_name }}.
Answer in the same language the user speaks.
Be concise and friendly.
Today is {{ now().strftime('%A, %B %d, %Y') }}.
```

### Continue conversation (Experimental)

When enabled, the assistant automatically keeps the microphone open after any response containing a question (`?`). Uses HA's native `continue_conversation` flag — no automation needed.

> **Note:** Requires a satellite device that supports `assist_satellite.start_conversation`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Controlling devices

Enable **Control Home Assistant** in the options (select "Assist"), then expose entities via **Settings > Voice Assistants > Exposed devices**.

### Example commands

| What you say | What happens |
|---|---|
| "Turn off the kitchen light" | `light.turn_off` |
| "Open the blinds" | `cover.open_cover` |
| "Lock the front door" | `lock.lock` |
| "Set thermostat to 21" | `climate.set_temperature` |
| "Activate the movie scene" | `scene.turn_on` |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## Using as a service action

Use `conversation.process` in automations or scripts:

```yaml
action: conversation.process
data:
  agent_id: conversation.github_copilot_conversation
  text: "What is the temperature in the living room?"
response_variable: result
```

The response text is in `result.response.speech.plain.speech`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## FAQ

**Q: The integration does not appear in the Voice Assistants dropdown.**
A: Make sure you performed a full restart (not just reload).

**Q: I get a 401 or 403 error.**
A: Verify you have an active GitHub Copilot subscription. The integration will trigger a re-authentication flow if your token expires.

**Q: Which models are available?**
A: The integration dynamically fetches models from the Copilot API. Available models depend on your Copilot subscription tier. Common models include GPT-4.1, GPT-4o, Claude Sonnet, Mistral Small, and Llama 3.3.

**Q: Does this require a GitHub PAT (Personal Access Token)?**
A: No. The integration uses GitHub's Device Flow OAuth — the same mechanism VS Code uses. You authorize via your browser at github.com/login/device.

**Q: Are my conversations stored?**
A: Conversations are processed via GitHub Copilot's servers. See GitHub's [privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement) for details.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

## License

Distributed under the MIT License. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
