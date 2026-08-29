# 🧠 Dana MCP Server

> **A cross-platform Python MCP server that turns your computer into an Agent accessible from ChatGPT, Grok, and Claude.**

🇮🇷 **Persian documentation:** [README.md](README.md)

Dana is a cross-platform Python MCP Server, independent from PHP. For initial setup, use the Installer; Dana can then run in Local Mode on a personal computer or Server Mode on a Linux server.

## 🙏 Special Thanks

[svg](https://github.com/seyed-ali-002/python-mcp-server#%D8%AA%D8%B4%DA%A9%D8%B1-%D9%88%DB%8C%DA%98%D9%87)

Special thanks to **Mohsen Samadinejad**. The core execution idea, initial architecture, and implementation direction of this tool originated from that idea.

His **PHP MCP Server** implementation was the primary behavioral reference for this Python rewrite. Observable behavior, tool contracts, the MCP protocol, and compatibility scenarios with the PHP version were used as references during the migration.

🔗 GitHub: https://github.com/samadinejad

## ✨ Features

- 🐍 Python implementation, independent from PHP
- 🖥️ Linux, Windows, and macOS support
- 🚀 Interactive installer with automatic isolated `.venv` setup
- 🌐 Local Mode with Tailscale Funnel
- 🌐 Server Mode with domain/IP, Caddy, and systemd
- 🔐 Persistent token-based connector URL
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
- **Server Mode**: runs on a Linux VPS or dedicated server without Tailscale, using a domain or IP, HTTPS (for domains), and systemd.

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

Server Mode automatically configures supported Linux dependencies, Caddy and systemd, generates a Bearer Token, and runs Dana on `127.0.0.1:8765`. When the input is a domain, Caddy acts as the reverse proxy and manages HTTPS; for a direct IP, the installer displays an HTTP endpoint.

Example configuration:

```env
DANA_DEPLOYMENT_MODE=server
DANA_HOST=127.0.0.1
DANA_PUBLIC_HOST=mcp.example.com
DANA_AUTH_TOKEN=<generated-token>
```

The canonical MCP endpoint is:

```text
https://mcp.example.com/mcp
```

Server Mode MCP requests require:

```text
Authorization: Bearer <DANA_AUTH_TOKEN>
```

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

### 3. Connector URL

The launcher prints a URL similar to:

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

Use this URL directly as the MCP Custom Connector URL. **No separate Authorization header is required.**

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
  "allowed_paths": [
    "/home/user/projects",
    "/mnt/workspace"
  ],
  "deny_paths": []
}
```

An empty `allowed_paths` list means unrestricted access, while `deny_paths` can still block sensitive locations. Paths are resolved before checking to defend against traversal and common symlink bypasses. Policy-aware tools include filesystem, project analysis, logs, databases, build paths, and browser screenshot output. MCP management tools are also provided: `get_allowed_paths`, `set_allowed_paths_tool`, `add_allowed_path_tool`, `remove_allowed_path_tool`, and `validate_path_access`.

## 🛠️ Basic Usage

Once connected, the chatbot can discover and use Dana's MCP tools. For example, it can create or edit files, search code, run tests, manage Git, inspect APIs, debug applications, or create Persian Word/PDF documents.

Dana executes tools on the **same machine where the server is running**, so operating-system permissions and the account running Dana matter.

## 🧩 Architecture

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

Dana is independent from the PHP service and uses its own server configuration so it can coexist with existing services.

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
