<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=240&color=0:0A2540,50:1B4965,100:2C7DA0&text=iCloud%20Mail%20Manager%20MCP&fontColor=ffffff&fontSize=46&fontAlignY=38&desc=MCP%20Automation%20for%20Apple%20iCloud%20Mail&descAlignY=58&animation=fadeIn" alt="iCloud Mail Manager MCP Hero Banner" />
</p>

<p align="center">
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white"></a>
  <a href="https://modelcontextprotocol.io/"><img alt="MCP" src="https://img.shields.io/badge/Model%20Context%20Protocol-Ready-0A7EA4?style=for-the-badge"></a>
  <img alt="IMAP" src="https://img.shields.io/badge/IMAP-imap.mail.me.com-00599C?style=for-the-badge">
  <img alt="SMTP" src="https://img.shields.io/badge/SMTP-smtp.mail.me.com-1D4ED8?style=for-the-badge">
  <img alt="Modes" src="https://img.shields.io/badge/Modes-PRIVATE%20%7C%20BUSINESS%20%7C%20MIXED-334155?style=for-the-badge">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-16A34A?style=for-the-badge">
</p>

<p align="center">
  <b>Enterprise-grade Claude Extension for full Apple iCloud Mail operations.</b><br>
  Production-ready documentation for clean GitHub publishing.
</p>

<p align="center">
  <img src="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3YxOWpqY2Q3OW9vd2QxZmx1eHh2aTBzMW9zbnppMmViNnBrYnJ6dyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ZVik7pBtu9dNS/giphy.gif" width="960" alt="iCloud Mail Manager Live Demo" />
</p>


---


> [!IMPORTANT]
> Never commit real credentials. Keep only `.env.example` in Git and use `.env` locally.

## Product Overview

`icloud-mail-manager` is a production-focused Python Claude Extension that enables complete Apple iCloud Mail management through IMAP + SMTP.

It is built for modern AI toolchains and supports:
- High-confidence inbox automation
- Structured folder and message operations
- Smart organization strategies by account context
- Secure credential handling and robust connection recovery

---

## Visual Tool Dashboard

| Tool | What It Does | Typical Use |
|---|---|---|
| `list_folders` | Lists all folders and recursive hierarchy | Discover full mailbox structure |
| `manage_folder` | Creates, renames, or deletes folders/subfolders | Organize mailbox taxonomy |
| `search_emails` | Advanced email filtering by sender/subject/date/keyword | Build targeted workflows |
| `read_email` | Reads full email body (text + HTML) by UID | Analyze message content |
| `manage_attachments` | Lists and saves attachments | Archive or process files |
| `send_email` | Sends rich emails with optional attachments | Outbound communication automation |
| `organize_email` | Moves email or sets read/unread state | Operational inbox triage |
| `suggest_organization` | Suggests folders based on senders + mode | Auto-structure recommendations |

### Account Context Modes

- `PRIVATE`
- `BUSINESS`
- `MIXED`

How each mode impacts organization suggestions:

- `PRIVATE`: Personal-life oriented suggestions (family, shopping, subscriptions, travel, personal finance, social updates).
- `BUSINESS`: Work-oriented suggestions (clients, projects, invoices, legal, operations, HR, internal communication).
- `MIXED`: Hybrid strategy that balances personal and professional senders in the same mailbox.

Mode scope:

- The mode primarily influences `suggest_organization` recommendations.
- Core email actions (`search_emails`, `read_email`, `send_email`, `organize_email`) remain available in all modes.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create local environment file

```bash
cp .env.example .env
```

Edit `.env`:

```env
ICLOUD_EMAIL=your_icloud_email@icloud.com
ICLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
ACCOUNT_MODE=MIXED
```

### 3. Run server directly

```bash
python server.py
```

---

## Apple App-Specific Password

1. Sign in at https://appleid.apple.com/
2. Open **Sign-In and Security**
3. Click **App-Specific Passwords**
4. Click **Generate an app-specific password**
5. Add a label (for example: `MCP iCloud Mail`)
6. Copy the generated password into `ICLOUD_APP_PASSWORD`

---

## Integration Modes

Claude supports two different integration models. They are not the same:

| Model | Designed For | Main Files | Typical Use |
|---|---|---|---|
| Plugin Mode | Claude Code (developer workflow) | `.claude-plugin/plugin.json`, `.mcp.json` | Local development and fast iteration |
| Extensions Mode | Claude Extensions runtime | `manifest.json`, `bootstrap.py` | Packaged extension behavior and managed startup |

### Claude Code Plugin Mode

> [!NOTE]
> If you see `No manifest.json found in extension folder`, you are likely using Plugin mode while expecting Extensions mode, or vice versa.

Plugin manifest:
- `.claude-plugin/plugin.json`

Run locally:

```bash
cd icloud-mail-manager-mcp
claude --plugin-dir .
```

Then in Claude Code:
1. Run `/reload-plugins`
2. Verify tools are visible
3. Trigger a tool such as `search_emails`

Plugin environment source:
- `.mcp.json`

What it does:

- Exposes this MCP server directly inside Claude Code.
- Lets you reload quickly during development (`/reload-plugins`).
- Best when you are iterating on tools and testing changes frequently.

### Claude Extensions Mode

Extensions manifest:
- `manifest.json`

Minimum required files:
- `manifest.json`
- `bootstrap.py`
- `server.py`
- `requirements.txt`

What it does:

- Runs the project as an extension package recognized by Claude Extensions.
- Uses `manifest.json` as the extension contract and startup definition.
- Uses `bootstrap.py` to verify/install runtime dependencies before launching `server.py`.

When to choose which:

- Choose Plugin Mode for development speed and local debugging.
- Choose Extensions Mode for extension-style deployment and runtime consistency.

---

## Modern Claude Desktop Config Block

Typical macOS path:
- `~/Library/Application Support/Claude/mcp-config.json`

```json
{
  "mcpServers": {
    "icloud-mail-manager": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": [
        "/absolute/path/to/icloud-mail-manager-mcp/server.py"
      ],
      "env": {
        "ICLOUD_EMAIL": "your_icloud_email@icloud.com",
        "ICLOUD_APP_PASSWORD": "xxxx-xxxx-xxxx-xxxx",
        "ACCOUNT_MODE": "MIXED"
      }
    }
  }
}
```

---

## Troubleshooting Callouts

> [!WARNING]
> If logs show `ModuleNotFoundError: No module named 'dotenv'` followed by `Server disconnected`, runtime dependencies are missing.

The project includes `bootstrap.py`, which validates and installs required packages (`mcp`, `python-dotenv`) before starting `server.py`.

Manual fallback install:

```bash
/opt/homebrew/bin/python3 -m pip install --user --break-system-packages mcp python-dotenv
```

Then fully restart Claude Desktop.

---

## Publish Security Checklist

- [ ] Real `.env` is not tracked
- [ ] `.env.example` is present and generic
- [ ] No real email/password values in repository files
- [ ] App-Specific Password rotated if previously exposed
- [ ] Repository visibility set to `Private` until final validation
- [ ] Local logs/secrets are excluded by `.gitignore`

---

## Project Structure

```text
icloud-mail-manager-mcp/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── icloud-help/
│       └── SKILL.md
├── .env.example
├── .gitignore
├── .mcp.json
├── bootstrap.py
├── manifest.json
├── README.md
├── requirements.txt
└── server.py
```

---

## License

MIT
