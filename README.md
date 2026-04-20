# iCloud Mail Manager MCP

<div align="center">

### A complete MCP server for Apple iCloud Mail management (IMAP + SMTP)

**Built with Python + MCP SDK**

</div>

---

## FR - Presentation

**icloud-mail-manager** est un serveur MCP Python qui permet de piloter un compte Apple iCloud Mail avec un mot de passe d'application Apple.

Fonctionnalites incluses :
- Liste recursive des dossiers
- Gestion des dossiers (creer, renommer, supprimer)
- Recherche avancee d'emails
- Lecture complete d'un email (texte + HTML)
- Gestion des pieces jointes (lister, sauvegarder)
- Envoi d'emails riches avec pieces jointes
- Organisation des emails (deplacer, lu/non-lu)
- Suggestion automatique de structure de dossiers selon le mode de compte

Modes de compte pris en charge via `ACCOUNT_MODE` :
- `PRIVATE`
- `BUSINESS`
- `MIXED`

---

## EN - Overview

**icloud-mail-manager** is a full Python MCP server to manage an Apple iCloud Mail account using an Apple App-Specific Password.

Included capabilities:
- Recursive folder listing
- Folder management (create, rename, delete)
- Advanced email search
- Full email reading (text + HTML)
- Attachment handling (list, save)
- Rich email sending with attachments
- Email organization (move, read/unread)
- Context-aware folder strategy suggestions based on account mode

Supported account modes through `ACCOUNT_MODE`:
- `PRIVATE`
- `BUSINESS`
- `MIXED`

---

## Installation

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root:

```env
ICLOUD_EMAIL=your_icloud_email@icloud.com
ICLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
ACCOUNT_MODE=PRIVATE
```

---

## Apple App-Specific Password

### FR - Generer le mot de passe d'application Apple

1. Connectez-vous a votre compte Apple : https://appleid.apple.com/
2. Ouvrez la section **Sign-In and Security**.
3. Cliquez sur **App-Specific Passwords**.
4. Cliquez sur **Generate an app-specific password**.
5. Donnez un nom (ex: MCP iCloud Mail), puis validez.
6. Copiez le mot de passe genere et collez-le dans `ICLOUD_APP_PASSWORD`.

### EN - Generate your Apple App-Specific Password

1. Sign in to your Apple account: https://appleid.apple.com/
2. Open **Sign-In and Security**.
3. Click **App-Specific Passwords**.
4. Click **Generate an app-specific password**.
5. Provide a label (for example: MCP iCloud Mail).
6. Copy the generated password and paste it into `ICLOUD_APP_PASSWORD`.

---

## Run the MCP Server

```bash
python server.py
```

The server starts with MCP stdio transport and exposes all tools.

---

## Claude Code Plugin Mode (Fix for manifest error)

If you saw this error:

`No manifest.json found in extension folder`

You are likely mixing extension systems. For Claude Code plugins, the manifest file is:

- `.claude-plugin/plugin.json` (not `manifest.json`)

This repository now includes a valid Claude Code plugin structure:

- `.claude-plugin/plugin.json`
- `.mcp.json`
- `skills/icloud-help/SKILL.md`

### Test locally as a Claude Code plugin

```bash
cd icloud-mail-manager-mcp
claude --plugin-dir .
```

Inside Claude Code:

1. Run `/reload-plugins`
2. Check `/agents` and available MCP tools
3. Call MCP tools such as `list_folders` or `search_emails`

### Environment variables for plugin mode

Before launching Claude Code, export these variables:

```bash
export ICLOUD_EMAIL="your_icloud_email@icloud.com"
export ICLOUD_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
export ACCOUNT_MODE="MIXED"
```

The plugin `.mcp.json` reads those values via environment substitution.

### Security note

- Never commit a real `.env` file.
- Copy `.env.example` to `.env` and fill your real values locally.

---

## Claude Extensions Mode (manifest.json)

If you install through the Claude Extensions folder, the expected format is different from plugin mode.

This project now includes `manifest.json` at repository root for that workflow.

Key difference:
- Plugin mode uses `.claude-plugin/plugin.json`
- Extensions mode uses `manifest.json`

Minimum files for Extensions mode:
- `manifest.json`
- `server.py`
- `requirements.txt`

If your installer says `No manifest.json found`, it is looking for Extensions mode and not plugin mode.

---

## Claude Desktop Configuration

Add this server to your Claude Desktop `mcp-config.json`.

Typical macOS path:
- `~/Library/Application Support/Claude/mcp-config.json`

Example:

```json
{
  "mcpServers": {
    "icloud-mail-manager": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": [
        "/absolute/path/to/apple_mcp/server.py"
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

Notes:
- Use absolute paths for `command` and `args`.
- Keep your `.env` file private and never commit real credentials.
- You can set env values either in `.env` or directly in `mcp-config.json`.

---

## Exposed Tools

- `list_folders`
- `manage_folder`
- `search_emails`
- `read_email`
- `manage_attachments`
- `send_email`
- `organize_email`
- `suggest_organization`

---

## Security and Robustness

- Credentials loaded via `python-dotenv`
- Defensive IMAP/SMTP error handling
- Timeout handling and authentication error reporting
- Graceful IMAP logout and SMTP quit on every operation

---

## Project Structure

```text
apple_mcp/
├── bootstrap.py
├── manifest.json
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── skills/
│   └── icloud-help/
│       └── SKILL.md
└── server.py
```

---

## License

Use and adapt this project to your own environment and security requirements.
