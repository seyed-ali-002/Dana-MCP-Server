# Dana MCP Server

Turn AI chatbots into agents that can work with your computer, files, code, and tools through MCP.

🇮🇷 [Persian guide](README_FA.md) · 🇬🇧 This page

---

## What Dana does

Dana runs on **your** machine. Compatible clients (ChatGPT, Claude, Grok, …) connect over MCP and can:

- read and edit files and projects
- run commands, tests, and builds
- use Git, Docker, browsers, and more

You stay in control. The core server is free and self-hosted.

---

## Quick start (Desktop — recommended)

1. Download the latest **Dana Desktop** build for your OS from  
   [GitHub Releases](https://github.com/seyed-ali-002/Dana-MCP-Server/releases/latest).
2. Open the app and go to **Setup**.
3. Click **Install & Activate** (or **Activate Dana** if Tailscale is already installed).

Dana will:

1. Download and install **Tailscale** if needed (with automatic mirrors if a host is blocked).
2. Ask the OS for admin rights when required (UAC on Windows, password dialog on Linux/macOS).  
   Dana never stores your password.
3. Show a **login / Funnel approval link** in the app — copy it or open it in the browser.
4. Start the local MCP server and enable Tailscale Funnel when you confirm.

![Setup](docs/images/dana-desktop-setup.svg)

![Download progress](docs/images/dana-download-progress.svg)

![Login link](docs/images/dana-auth-link.svg)

### Three panels

| Panel | Use it for |
|---|---|
| **Setup** | Install Tailscale, log in, start Dana, enable Funnel |
| **Control** | Start/stop, copy MCP URLs, token, optional advanced settings |
| **Logs** | Setup/errors on the left · tool activity on the right |

### MCP URLs

Local:

```text
http://127.0.0.1:8765/<TOKEN>/mcp
```

Public (after Funnel):

```text
https://<machine>.<tailnet>.ts.net/<TOKEN>/mcp
```

Paste the URL into your MCP client. Use **Test connection** in Control to verify.

### Admin password

Installing Tailscale or enabling Funnel may require administrator rights:

- **Windows** — approve the UAC prompt
- **Linux** — polkit (`pkexec`) dialog or `sudo` in a terminal
- **macOS** — system password dialog

If automatic download fails (for example HTTP 403), use **Open Tailscale download**, install manually, then **Continue after install**.

---

## Terminal install (optional)

```bash
git clone https://github.com/seyed-ali-002/Dana-MCP-Server.git
cd Dana-MCP-Server
python3 -m pip install -e .
dana gui
```

Or run the server only:

```bash
python3 -m dana.main
```

Default local endpoint: `http://127.0.0.1:8765/mcp` (token path is recommended).

---

## Connect a client

1. Complete Setup until Funnel is active (or use the local URL on the same machine).
2. Copy the tokenized MCP URL from **Control → Endpoints**.
3. Add it as a custom MCP server in ChatGPT / Claude / Grok / other compatible clients.

More architecture detail: [project_description_md/](project_description_md/).

---

## Safety notes

- The auth token protects the MCP endpoint. Treat it like a password.
- Funnel exposes Dana on the public HTTPS URL for your tailnet machine — only enable it if you intend that.
- Closing the desktop app stops the Dana runtime; Funnel routes are left as-is.

---

## Thanks

Special thanks to [Mohsen Samadinejad](https://github.com/samadinejad) for early architectural inspiration.

---

## License

See the repository license file.
