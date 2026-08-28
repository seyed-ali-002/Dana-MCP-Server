# 🧠 Dana MCP Server

> **A cross-platform Python MCP server that turns your computer into an Agent accessible from ChatGPT, Grok, and Claude.**

🇮🇷 **Persian documentation:** [README.md](README.md)

Dana is a cross-platform Python MCP Server, independent from PHP, that runs on your computer and exposes a public HTTPS MCP endpoint through Tailscale Funnel.

## 🙏 Special Thanks

[svg](https://github.com/seyed-ali-002/python-mcp-server#%D8%AA%D8%B4%DA%A9%D8%B1-%D9%88%DB%8C%DA%98%D9%87)

Special thanks to **Mohsen Samadinejad**. The core execution idea, initial architecture, and implementation direction of this tool originated from that idea.

His **PHP MCP Server** implementation was the primary behavioral reference for this Python rewrite. Observable behavior, tool contracts, the MCP protocol, and compatibility scenarios with the PHP version were used as references during the migration.

🔗 GitHub: https://github.com/samadinejad

## ✨ Features

- 🐍 Python implementation, independent from PHP
- 🖥️ Linux, Windows, and macOS support
- 🌐 HTTPS exposure through Tailscale Funnel
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

## 🚀 Quick Start

### 1. Clone

```bash
git clone git@github.com:seyed-ali-002/Dana-MCP-Server.git
cd Dana-MCP-Server
```

### 2. Run

**Linux / macOS:**

```bash
./run.sh
```

**Windows:**

```bat
run.bat
```

The launcher handles Python environment setup, dependency installation, persistent token creation, Dana startup, Tailscale Funnel setup, hostname discovery, and printing the MCP connector URL.

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
