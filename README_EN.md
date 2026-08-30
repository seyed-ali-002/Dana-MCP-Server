# 🧠 Dana MCP Server

> **A cross-platform Python MCP server that turns your computer into an Agent accessible from ChatGPT, Grok, and Claude.**

🇮🇷 **Persian documentation:** [README.md](README.md)

---

Dana is a cross-platform Python MCP Server, independent from PHP. For initial setup, use the Installer; Dana can then run in Local Mode on a personal computer or Server Mode on a Linux server.

## 📚 Table of Contents

- [Features](#-features)
- [Deployment Modes](#deployment-modes)
  - [Interactive Installer](#interactive-installer)
  - [Local Mode](#local-mode)
  - [Server Mode](#server-mode)
  - [Terminal UI](#terminal-ui)
- [Quick Start](#-quick-start)
  - [Clone](#1-clone)
  - [Install and Setup](#2-install-and-setup)
  - [Connector URL](#3-connector-url)
- [Installing and Logging in to Tailscale](#-installing-and-logging-in-to-tailscale)
- [Managing Dana in Server Mode](#️-managing-dana-in-server-mode)
- [Token Management](#-token-management)
- [Browser and Security Tools](#-enabling-browser-and-security-tools)
- [Connecting ChatGPT, Grok, and Claude](#-connecting-chatgpt-grok-and-claude)
- [Filesystem Access Restrictions](#-dana-filesystem-access-restrictions)
- [Basic Usage](#️-basic-usage)
- [Architecture](#-architecture)
- [Tests](#-tests)
- [Contributing](#-contributing)
- [License](#-license)
- [Special Thanks](#-special-thanks)

---

> For the fastest setup, start with **Quick Start** and then follow either **Local Mode** or **Server Mode** for your environment.

---

## 🙏 Special Thanks

Special thanks to **Mohsen Samadinejad**. The core execution idea, initial architecture, and implementation direction of this tool originated from that idea.

His **PHP MCP Server** implementation was the primary behavioral reference for this Python rewrite. Observable behavior, tool contracts, the MCP protocol, and compatibility scenarios with the PHP version were used as references during the migration.

🔗 GitHub: https://github.com/samadinejad

## ✨ Features

- 🐍 Python implementation, independent from PHP
- 🖥️ Linux, Windows, and macOS support
- 🚀 Interactive installer with automatic isolated `.venv` setup
- 🌐 Local Mode with Tailscale Funnel
- 🌐 Server Mode with domain, HTTPS, existing reverse-proxy integration, and systemd
- 🔐 Tokenized Local Mode URLs and a standard HTTPS endpoint for Server Mode
- 📁 File, directory, and code editing tools
- 💻 Shell and process management
- 🌿 Git, testing, linting, building, and package management
- 🌍 HTTP/API and network tools
- 🐳 Docker and SQLite
- 🌐 Web and browser automation
- 🐞 Debugging and code-quality tools
- 📄 Persian/RTL Word and PDF generation
- 📝 README, changelog, reports, and documentation generation

## Deployment Modes

Dana has one shared core with two isolated deployment modes:

- **Local Mode**: runs on a personal computer and uses the existing Tailscale workflow.
- **Server Mode**: runs on a Linux VPS or dedicated server without Tailscale, using a domain and HTTPS, an isolated localhost backend, automatic reverse-proxy integration, and systemd.

The active mode is selected with `DANA_DEPLOYMENT_MODE=local` or `DANA_DEPLOYMENT_MODE=server`.

### Interactive Installer

For normal installation and setup, run only the Installer:

```bash
python3 install.py
```

The Installer creates the project `.venv` and installs all Python dependencies inside it, so it does not modify the system-managed Python environment and avoids PEP 668 errors.

After installation, Dana is run from the created environment. `scripts/run.py` and the `run*` files are direct/compatibility runners, not the primary installation path.

The installer asks for the deployment mode first and then performs only the setup required for that mode. After dependency checks and installation, the terminal is cleared and the final connection information is displayed cleanly.

### Server Mode

Server Mode is designed for VPS and dedicated servers that may already host one or more web projects. Dana runs on an **isolated free internal port** and listens only on `127.0.0.1`, so it does not directly conflict with public ports `80` and `443` or existing web services.

The installer automatically:

1. Selects a free backend port for Dana.
2. Runs Dana through systemd on `127.0.0.1:<PORT>`.
3. Detects the existing reverse proxy:
   - Nginx
   - Caddy
   - Apache
4. Finds the Virtual Host configuration for the selected domain.
5. Creates a backup before changing the configuration.
6. Adds the `/mcp` route to the Dana backend.
7. Validates the proxy configuration.
8. Rolls back automatically if validation or configuration fails.
9. Reloads the proxy only after successful validation.

Architecture:

```text
Internet
   │
   ▼
https://mcp.example.com
   │
   ▼
Existing Nginx / Caddy / Apache
   ├── /     → Existing Web Project
   └── /mcp  → 127.0.0.1:<DANA_PORT>
                    │
                    ▼
                 Dana MCP
```

Example configuration:

```env
DANA_DEPLOYMENT_MODE=server
DANA_HOST=127.0.0.1
DANA_PORT=<auto-selected-port>
DANA_PUBLIC_HOST=mcp.example.com
```

The canonical MCP endpoint is:

```text
https://mcp.example.com/mcp
```

> Server Mode does not put the token inside the public URL, keeping the connector endpoint a standard HTTPS URL.

### Local Mode

Local Mode keeps the existing Tailscale workflow. **For normal installation and setup, run only `python3 install.py`.** The installer creates the project `.venv`, installs dependencies there, and configures Local Mode.

`./run.sh`, `run.bat`, and `scripts/run.py` are direct/compatibility runners for subsequent launches; they are not the primary installation path.

The installer and runtime are mode-aware, so Local and Server networking configuration remains isolated.

### Terminal UI

The CLI and runtime use Rich panels for readable status output. Connection URLs are always printed on one uninterrupted line so they can be copied safely. The terminal is also cleared after dependency setup so the final screen stays clean.

## 🚀 Quick Start

**Recommended path for all users: run the Installer only.**

### 1. Clone

```bash
git clone git@github.com:seyed-ali-002/Dana-MCP-Server.git
cd Dana-MCP-Server
```

### 2. Install and setup

**Linux / macOS:**

```bash
python3 install.py
```

**Windows:**

```bat
python install.py
```

The Installer is the only recommended initial setup path. It creates the project `.venv`, installs dependencies into the isolated environment, asks for Local or Server Mode, and configures only the selected deployment mode.

`./run.sh`, `run.bat`, and `scripts/run.py` are direct/compatibility runners for starting Dana after installation; they are not installation commands.

> ⚠️ Tailscale must be installed and authenticated on the machine.

### 🔐 Installing and Logging in to Tailscale

If Tailscale is not installed or you are not signed in yet, follow the steps for your platform below.

#### 🐧 Linux

1. Download and install Tailscale from:
   https://tailscale.com/download/linux
2. Enable and start the service:

```bash
sudo systemctl enable --now tailscaled
```

3. Log in:

```bash
sudo tailscale up
```

4. The command displays an authentication URL. Open it in a browser, sign in to your Tailscale account, and approve the device.
5. Verify the connection:

```bash
tailscale status
```

#### 🪟 Windows

1. Download Tailscale from:
   https://tailscale.com/download/windows
2. Install and launch the application.
3. Click **Log in**.
4. Your browser will open. Sign in to Tailscale and approve the device.
5. Confirm that Tailscale shows **Connected**.

#### 🍎 macOS

1. Download Tailscale from:
   https://tailscale.com/download/mac
2. Install and launch the application.
3. Open Tailscale from the menu bar and select **Log in**.
4. Sign in through the browser and approve the device.
5. Confirm that Tailscale shows **Connected**.

> 💡 **Note:** Dana uses Tailscale Funnel to expose the MCP endpoint publicly. The signed-in Tailscale account must therefore be allowed to use Funnel.

🔗 Official documentation: https://tailscale.com/kb/start

## ⏹️ Managing Dana in Server Mode

Dana runs as a systemd service named `dana` in Server Mode.

### Stop the service

```bash
sudo systemctl stop dana
```

### Start the service

```bash
sudo systemctl start dana
```

### Restart the service

```bash
sudo systemctl restart dana
```

### Check service status

```bash
sudo systemctl status dana --no-pager
```

### Follow live logs

```bash
sudo journalctl -u dana -f
```

### Disable automatic startup

```bash
sudo systemctl disable dana
```

### Enable automatic startup again

```bash
sudo systemctl enable dana
```

> Dana normally listens only on `127.0.0.1` in Server Mode. Its backend port is therefore not publicly exposed; public access is provided through the HTTPS reverse proxy and the `/mcp` route.

### 👷 Worker Count

During Dana installation or launch, you will be asked for the number of workers. The default is **5**. This is suitable for most use cases; increase it when multiple clients or concurrent tool operations require more capacity. The supported range is **1 to 128**.

The selected value is stored in `.env` as:

```env
DANA_WORKERS=5
```

### 3. Connector URL

The launcher prints a URL similar to:

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

Use this URL directly as the MCP Custom Connector URL. **No separate Authorization header is required in Local Mode.**

For Server Mode, use the standard endpoint:

```text
https://<your-domain>/mcp
```

## 🔑 Token Management

The token is persistent and does not change on every Dana startup.

Generate a new token with:

```bash
python scripts/regenerate_token.py
```

Restart Dana after regeneration.

## 🌐 Enabling Browser and Security Tools

Install Dana's optional advanced dependencies:

```bash
pip install -e ".[full]"
playwright install chromium
```

Or install browser support only:

```bash
pip install -e ".[browser]"
playwright install chromium
```

This enables Playwright browser capabilities and Python dependency security auditing.

## 🤖 Connecting ChatGPT, Grok, and Claude

### ChatGPT

Open the **Plugins / Connectors** area in ChatGPT and select the option for adding an MCP or Custom Connector. Enter the URL printed by Dana.

> The exact menu name and location may vary between ChatGPT versions.

### Grok

Open **Custom Connectors** in Grok, create an MCP connector, and enter the Dana URL.

### Claude

Open **Custom Connectors** in Claude, add an MCP connection, and enter the same Dana URL.

### ⚠️ Important

If a connector was created against an older Dana version, delete/recreate it when necessary so the client performs a fresh `tools/list` discovery.

## 🔒 Dana Filesystem Access Restrictions

Dana can be restricted to paths explicitly chosen by the user. Settings are stored in `config/access_policy.json`.

```json
{
  "allowed_paths": ["/home/user/projects", "/mnt/workspace"],
  "deny_paths": []
}
```

An empty `allowed_paths` list means unrestricted access, while `deny_paths` can still block sensitive locations. Paths are resolved before checking to defend against traversal and common symlink bypasses. Policy-aware tools include filesystem, project analysis, logs, databases, build paths, and browser screenshot output. MCP management tools are also provided: `get_allowed_paths`, `set_allowed_paths_tool`, `add_allowed_path_tool`, `remove_allowed_path_tool`, and `validate_path_access`.

## 🛠️ Basic Usage

Once connected, the chatbot can discover and use Dana's MCP tools. For example, it can create or edit files, search code, run tests, manage Git, inspect APIs, debug applications, or create Persian Word/PDF documents.

Dana executes tools on the **same machine where the server is running**, so operating-system permissions and the account running Dana matter.

## 🧩 Architecture

### Local Mode

```text
ChatGPT / Grok / Claude
          │
          │ MCP over HTTPS
          ▼
   Tailscale Funnel
          │
          ▼
      Dana Server
          │
    ┌─────┼─────┐
    ▼     ▼     ▼
 Files  Shell  Git ...
```

### Server Mode

```text
ChatGPT / Grok / Claude
          │
          │ MCP over HTTPS
          ▼
 Existing Reverse Proxy :443
 Nginx / Caddy / Apache
          │
          ├── /     → Existing Web Projects
          │
          └── /mcp  → 127.0.0.1:<DANA_PORT>
                           │
                           ▼
                        Dana MCP
```

In Server Mode, Dana uses its own internal backend port and automatically integrates the `/mcp` route with the existing reverse proxy, preserving other web projects hosted on the same server.

## 🧪 Tests

```bash
pytest -q
```

## 🤝 Contributing

Issues and Pull Requests are welcome.

1. Open an Issue 🐛
2. Implement the proposed fix or feature 🛠️
3. Add or update tests 🧪
4. Submit a Pull Request 🚀

When reporting a bug, include the OS, Python version, Dana version, and relevant logs whenever possible.

## 📜 License

See [LICENSE](LICENSE) for the project license.

---

⭐ If Dana is useful to you, consider starring the repository and contributing to its development.

## 🧠 Codebase Memory and Context Optimization
Dana incrementally indexes projects with SQLite + FTS5. Use `index_codebase`, then `search_codebase_memory` to retrieve only relevant context within a budget. `get_library_docs` caches public documentation URLs and `context_compress` removes duplicate context.
