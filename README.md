# Kimi AI Agent Container — Technical Deep Dive

> A fully containerized AI agent runtime built on Alibaba Cloud Kubernetes, combining a Jupyter Python kernel, a Chromium browser, VNC/SSH remote access, and an s6-supervised service mesh — all wired together for autonomous AI agent execution.

---

## What This Is

This is the runtime environment powering **Kimi** (by Moonshot AI), an AI agent that can execute Python code, browse the web, render UI widgets, and interact with a full desktop — all inside a single container pod running on Alibaba Cloud Container Service (ACK) in `cn-beijing`.

The container is not a simple chatbot backend. It is a complete, self-contained agent workstation:

- A **Python execution kernel** (Jupyter) accessible over HTTP
- A **Chromium browser** with CDP remote control and a custom PDF viewer extension
- A **VNC + X11 desktop** at 1920×1080 for visual interaction
- **SSH access** for direct shell sessions
- An **s6 init system** managing all services with proper dependency ordering
- **Kubernetes-native** deployment with service account tokens and cluster DNS

---

## Repository Structure

```
.
├── app/                        # Core application runtime
│   ├── kernel_server.py        # FastAPI HTTP server — Jupyter kernel management API
│   ├── jupyter_kernel.py       # JupyterKernel class — kernel lifecycle + code execution
│   ├── browser_guard.py        # Browser watchdog — Playwright + CDP browser management
│   ├── utils.py                # Shared utilities (screen size, subprocess helpers)
│   ├── .agents/
│   │   └── skills/
│   │       ├── kimi-help-center/SKILL.md   # Agent skill: Kimi product help docs
│   │       └── kimi-widget/SKILL.md        # Agent skill: UI widget design system
│   ├── data/chrome_data/       # Chromium persistent user profile
│   ├── logs/chromium.log       # Chromium runtime log
│   └── pdf-viewer/             # Bundled Chrome extension (PDF.js-based viewer)
│
├── command/                    # s6 + execline binary toolkit (234 executables)
│   ├── s6-*                    # s6 supervision, logging, IPC, DNS, TLS tools
│   ├── execline*               # execline scripting language binaries
│   └── with-contenv, ...       # s6-overlay container helpers
│
├── var_run/                    # Snapshot of /var/run from the live container
│   └── var/run/
│       ├── s6/                 # s6 runtime state
│       │   ├── basedir/        # Init scripts (rc.init, rc.shutdown)
│       │   ├── container_environment/  # Per-service env vars
│       │   └── db/servicedirs/ # Compiled service definitions
│       ├── service/            # Live s6 supervision tree
│       │   ├── browser-guard/
│       │   ├── kasmvnc/
│       │   ├── kernel-server/
│       │   ├── socat/
│       │   └── sshd/
│       └── secrets/kubernetes.io/serviceaccount/  # K8s service account
│
├── ca.crt                      # Alibaba Cloud Kubernetes CA certificate
├── token                       # Kubernetes service account JWT token
├── kubeconfig.yaml             # Cluster kubeconfig
└── details                     # Live container inspection log (commands + outputs)
```

---

## The `/app` Directory — Application Runtime

### `kernel_server.py` — Jupyter Kernel Management API

A **FastAPI** application that wraps a Jupyter kernel and exposes it over HTTP on port `8888`. This is the primary interface through which the AI agent executes Python code.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Kernel health check |
| POST | `/kernel/reset` | Kill and restart the kernel |
| POST | `/kernel/interrupt` | Send SIGINT to the running kernel |
| GET | `/kernel/connection` | Full connection info (ports, keys) |
| GET | `/kernel/connection-file` | Simplified connection file path |
| GET | `/kernel/status` | Kernel alive/PID/client status |
| GET | `/kernel/debug` | Debug dump of KernelManager internals |

The server uses FastAPI's `lifespan` context manager to initialize and cleanly shut down the kernel on startup/shutdown. CORS is fully open (`*`) since it runs in a trusted container network.

**Key design choices:**
- Single global `JupyterKernel` instance per server process
- All endpoints return structured Pydantic models
- Graceful error handling — 503 if kernel not initialized, 500 on execution errors

### `jupyter_kernel.py` — Kernel Lifecycle and Code Execution

The `JupyterKernel` class wraps `jupyter_client.manager.KernelManager` and handles the full lifecycle of a Python kernel.

**Initialization flow:**
1. Creates a `KernelManager` bound to the container's host IP (not localhost)
2. Starts the kernel subprocess
3. Connects a `KernelClient` and waits for ready state (30s timeout)
4. Runs an init script that configures matplotlib with CJK font support (Noto Sans CJK SC), sets figure defaults, and enables `%matplotlib inline`

**Execution model:**
- `execute(code, timeout)` sends code via ZMQ, collects `iopub` messages until `status: idle`
- Captures `stream`, `execute_result`, `display_data`, and `error` message types
- Returns an `ExecutionResult` with `success`, `output`, `error`, and `images` (base64 PNG list)
- Auto-restarts the kernel on execution failure

**PID detection** uses a 4-method fallback chain:
1. `km.provisioner.process.pid` (jupyter-client ≥ 7)
2. `km.kernel.pid` (older versions)
3. Scan `psutil` processes for `kernel_id` in cmdline
4. Scan for connection file basename in cmdline

### `browser_guard.py` — Browser Watchdog

Manages a Chromium browser instance and keeps it alive. Two implementations are provided:

**`BrowserGuard`** — Playwright-based:
- Launches Chromium as a persistent context with a fixed user data dir (`/app/data/chrome_data`)
- Configures locale (`zh-CN`), timezone (`Asia/Shanghai`), and a realistic User-Agent with proper `Sec-CH-UA` headers
- Loads the custom PDF viewer extension
- Monitors the page list every second; restarts the browser if all tabs are closed
- Uses `pyautogui` to click the browser window into focus after launch

**`BrowserCDPGuard`** — CDP-based (active when `USE_CDP=1`):
- Launches Chromium as a subprocess with `--remote-debugging-port=9222`
- Communicates via raw WebSocket CDP messages
- Monitors tab list via `GET /json/list`; opens a new tab if none exist
- Checks window state via `Browser.getWindowForTarget` + `Browser.getWindowBounds`; restores minimized windows and maximizes non-maximized ones
- Manages per-tab WebSocket connections with automatic reconnection

**Startup sequence:**
```
wait_for_display(:99) → launch Chromium → pyautogui focus click → start_monitoring()
```

The `USE_CDP=1` environment variable (set in this container) selects `BrowserCDPGuard`.

### `utils.py` — Shared Utilities

Three small helpers:
- `get_screensize()` — queries `xrandr` for the current display resolution
- `run_command()` — synchronous subprocess wrapper with timeout
- `run_command_background()` — async subprocess launcher returning a `Popen` handle

### `pdf-viewer/` — Chrome Extension

A bundled PDF.js-based Chrome extension that intercepts PDF navigation and renders PDFs inline in the browser. Loaded via `--load-extension=/app/pdf-viewer` in both browser launch modes.

### Agent Skills (`app/.agents/skills/`)

Two agent skill definitions that extend Kimi's capabilities:

**`kimi-help-center`** — Routes user questions about Kimi's product features (subscriptions, Deep Research, Agent mode, Kimi Claw, PPT/Docs/Sheets, etc.) to the appropriate GitHub-hosted help document via `web_open_url`. Covers 15+ topic categories.

**`kimi-widget`** — A comprehensive design system specification for generating interactive HTML/SVG widgets rendered inside sandboxed iframes. Defines CSS variable usage, component patterns (radio, checkbox, toggle, slider, cards), Chart.js integration, and strict rules for dark mode compatibility and streaming-safe rendering.

---

## The `/command` Directory — s6 + execline Toolkit

This directory contains **234 statically-linked binaries** that form the init system and process supervision layer. It is mounted at `/command` and is the first entry in `PATH`.

### execline — A Non-Interactive Scripting Language

execline is a minimal scripting language designed for init scripts and service run files. Unlike shell scripts, execline programs are chains of `exec` calls — each program replaces itself with the next, making them immune to signal handling issues common in shell scripts.

Key execline binaries:

| Binary | Purpose |
|--------|---------|
| `execlineb` | execline script interpreter |
| `if` / `ifelse` / `ifte` | Conditional execution |
| `foreground` / `background` | Sequential / async execution |
| `pipeline` | Connect stdout of one program to stdin of another |
| `redirfd` | File descriptor redirection |
| `importas` / `export` / `unexport` | Environment variable manipulation |
| `multisubstitute` | Multiple variable substitutions |
| `forx` / `forstdin` / `forbacktickx` | Looping constructs |
| `backtick` | Capture command output into a variable |
| `with-contenv` | Load container environment before exec |
| `emptyenv` | Clear environment before exec |
| `envfile` | Load env vars from a file |
| `heredoc` | Inline data injection |
| `tryexec` | Try exec, fall back on failure |
| `with-retries` | Retry a command N times |

### s6 — A Process Supervision Suite

s6 is the supervision backbone. It replaces systemd/runit/SysV init in this container.

**Core supervision tools:**

| Binary | Purpose |
|--------|---------|
| `s6-svscan` | Scans a service directory and supervises all services found |
| `s6-supervise` | Supervises a single service — restarts it if it exits |
| `s6-svc` | Send control signals to a supervised service (up/down/restart/etc.) |
| `s6-svstat` | Query the status of a supervised service |
| `s6-svwait` | Wait until a service reaches a desired state |
| `s6-svok` | Check if a service is being supervised |
| `s6-svlink` / `s6-svunlink` | Add/remove services from the supervision tree |
| `s6-svperms` | Manage service directory permissions |
| `s6-svdt` / `s6-svdt-clear` | Service dependency tree management |

**s6-rc — Service Dependency Management:**

| Binary | Purpose |
|--------|---------|
| `s6-rc` | Bring services up/down respecting dependencies |
| `s6-rc-compile` | Compile service definitions into a binary database |
| `s6-rc-init` | Initialize the s6-rc state machine |
| `s6-rc-update` | Hot-reload service definitions |
| `s6-rc-db` | Query the compiled service database |
| `s6-rc-bundle` | Manage service bundles (groups) |

**s6-linux-init — Container Init:**

| Binary | Purpose |
|--------|---------|
| `s6-linux-init` | PID 1 — sets up the supervision tree and runs rc.init |
| `s6-linux-init-shutdown` | Graceful container shutdown |
| `s6-linux-init-nuke` | Force-kill all processes |
| `s6-linux-init-hpr` | Halt/poweroff/reboot |
| `s6-linux-init-maker` | Generate init directory structure |

**Logging tools:**

| Binary | Purpose |
|--------|---------|
| `s6-log` | Structured log processor with rotation |
| `s6-socklog` | Syslog-compatible log receiver |
| `s6-logwatch` | Watch a log file |
| `logutil-service` / `logutil-newfifo` | Log pipeline helpers |
| `s6-tai64n` / `s6-tai64nlocal` | TAI64N timestamp encoding/decoding |

**IPC and file descriptor tools:**

| Binary | Purpose |
|--------|---------|
| `s6-fdholder-daemon` / `s6-fdholderd` | File descriptor passing daemon |
| `s6-fdholder-store` / `s6-fdholder-retrieve` | Store/retrieve FDs across processes |
| `s6-ipcserver` / `s6-ipcclient` | Unix domain socket server/client |
| `s6-ftrig-notify` / `s6-ftrig-listen` | FIFO-based event notification |
| `s6-mkfifodir` / `s6-cleanfifodir` | FIFO directory management |

**Networking tools:**

| Binary | Purpose |
|--------|---------|
| `s6-tcpserver` / `s6-tcpclient` | TCP server/client with access control |
| `s6-tcpserver-access` | TCP access rules enforcement |
| `s6-connlimit` | Connection rate limiting |
| `s6-tlsserver` / `s6-tlsclient` | TLS-wrapped TCP server/client |
| `s6-tlsd` / `s6-tlsc` | TLS daemon wrappers |
| `s6-ucspitlsd` / `s6-ucspitlsc` | UCSPI-TLS interface |
| `s6-ident-client` | Ident protocol client |
| `s6-randomip` | Random IP selection |

**DNS tools (skadns):**

| Binary | Purpose |
|--------|---------|
| `s6-dnsip` / `s6-dnsip4` / `s6-dnsip6` | DNS A/AAAA lookups |
| `s6-dnsmx` / `s6-dnsns` / `s6-dnstxt` | MX/NS/TXT record lookups |
| `s6-dnsname` | Reverse DNS lookup |
| `s6-dnsq` / `s6-dnsqr` | Raw DNS queries |
| `s6-dnsqualify` | FQDN qualification |
| `s6-dnssoa` / `s6-dnssrv` | SOA/SRV record lookups |
| `s6-dns-hosts-compile` | Compile /etc/hosts into CDB |
| `skadnsd` | Async DNS resolver daemon |

**System utilities:**

| Binary | Purpose |
|--------|---------|
| `s6-applyuidgid` / `s6-setuidgid` / `s6-envuidgid` | UID/GID management |
| `s6-chroot` / `s6-pivotchroot` | Chroot operations |
| `s6-softlimit` | Resource limit enforcement |
| `s6-setlock` | File locking |
| `s6-setsid` | New session creation |
| `s6-nice` | Process priority |
| `s6-pause` | Pause process execution |
| `s6-nuke` | Kill all processes in a session |
| `s6-freeramdisk` | Free a RAM disk |
| `s6-mount` / `s6-umount` / `s6-swapoff` / `s6-swapon` | Mount operations |
| `s6-sync` | Filesystem sync |
| `s6-clock` / `s6-clockview` / `s6-sntpclock` / `s6-taiclock` | Clock management |
| `s6-accessrules-cdb-from-fs` / `s6-accessrules-fs-from-cdb` | Access rule compilation |
| `s6-instance-*` | Service instance management |
| `s6-usertree-maker` | Per-user supervision tree |
| `s6-overlay-suexec` | Privilege escalation for s6-overlay |
| `s6-sudo` / `s6-sudoc` / `s6-sudod` | Privilege delegation |

**POSIX-compatible wrappers:**

| Binary | Purpose |
|--------|---------|
| `s6-cat`, `s6-echo`, `s6-grep`, `s6-head`, `s6-tail`, `s6-sort`, `s6-seq` | POSIX text tools |
| `s6-ls`, `s6-mkdir`, `s6-ln`, `s6-rename`, `s6-rmrf`, `s6-touch` | POSIX file tools |
| `s6-chmod`, `s6-chown`, `s6-hiercopy` | Permission/copy tools |
| `s6-basename`, `s6-dirname`, `s6-linkname`, `s6-uniquename` | Path tools |
| `s6-expr`, `s6-quote`, `s6-unquote`, `s6-format-filter` | String tools |
| `s6-env`, `s6-envdir`, `s6-dumpenv`, `s6-printenv` | Environment tools |
| `s6-hostname`, `s6-getservbyname` | Network info |
| `s6-ps` | Process listing |
| `s6-sleep`, `s6-maximumtime` | Timing |
| `s6-true`, `s6-false` | Boolean exit codes |
| `s6-cut` | Field extraction |
| `s6-rngseed` | RNG seeding |
| `s6-seekablepipe` | Seekable pipe creation |
| `s6-update-symlinks` | Symlink management |
| `s6-portable-utils`, `s6-linux-utils` | Utility meta-packages |
| `printcontenv` | Print a container environment variable |
| `ucspilogd` | UCSPI log daemon |

---

## The `/var_run` Directory — Runtime State Snapshot

This is a captured snapshot of `/var/run` from the live container, showing the actual runtime state.

### Service Supervision Tree (`/var/run/service/`)

Seven services are supervised by s6:

| Service | What it runs |
|---------|-------------|
| `kasmvnc` | `/bin/bash /root/setup_kasmvnc.sh` — X11 + VNC server on display `:99`, WebSocket port `6080`, RFB port `5901` |
| `browser-guard` | `python3 /app/browser_guard.py --wait-display --monitor` — waits for kasmvnc, then manages Chromium |
| `kernel-server` | `python3 /app/kernel_server.py --host 0.0.0.0 --port 8888` — waits for kasmvnc, then starts the kernel API |
| `sshd` | `/usr/sbin/sshd -D -e` — SSH daemon on port `22` |
| `socat` | `socat TCP-LISTEN:9223,reuseaddr,fork TCP:localhost:9222` — proxies CDP port `9222` to `9223` for external access |
| `s6rc-fdholder` | Internal s6 file descriptor passing service |
| `s6rc-oneshot-runner` | Internal s6 one-shot task runner |

**Dependency ordering:**
```
kasmvnc (X11/VNC)
    └── browser-guard (Chromium)
    └── kernel-server (Jupyter API)
sshd (independent)
socat (independent)
```

Both `browser-guard` and `kernel-server` use `s6-svwait -u /run/service/kasmvnc` to block until the VNC/X11 server is ready before starting.

### Container Environment (`/var/run/s6/container_environment/`)

Each file in this directory is an environment variable injected into every service via `with-contenv`. Key variables:

| Variable | Value |
|----------|-------|
| `DISPLAY` | `:99` |
| `SCREEN_RESOLUTION` | `1920x1080` |
| `TZ` | `Asia/Shanghai` |
| `PYTHON_VERSION` | `3.12.12` |
| `USE_CDP` | `1` (enables BrowserCDPGuard) |
| `WORKDIR` | `/mnt/agents` |
| `PIP_INDEX_URL` | Alibaba Cloud PyPI mirror |
| `KUBERNETES_SERVICE_HOST` | ACK API server FQDN |
| `SSH_PASSWORD` | `REDACTED` |
| `VNC_PASSWORD` | `REDACTED` |

### Init Scripts (`/var/run/s6/basedir/scripts/`)

**`rc.init`** — Stage 2 init (runs after PID 1 sets up supervision):
1. Sets container environment permissions
2. Runs optional `S6_STAGE2_HOOK` if defined
3. Compiles service definitions: `s6-rc-compile /run/s6/db /etc/s6-overlay/s6-rc.d`
4. Initializes s6-rc state: `s6-rc-init -c /run/s6/db /run/service`
5. Brings all services up: `s6-rc -u -t 5000 -- change <top>`
6. If a CMD was specified in the Dockerfile, runs it and halts on exit

**`rc.shutdown`** — Graceful shutdown:
- Runs `s6-rc -bda change` to bring all services down in reverse dependency order

### Kubernetes Service Account (`/var/run/secrets/kubernetes.io/serviceaccount/`)

| File | Contents |
|------|---------|
| `token` | JWT signed by Alibaba Cloud ACK — `system:serviceaccount:default:default` |
| `ca.crt` | Cluster CA certificate (Issuer: `alibaba cloud / kubernetes`, valid until 2056) |
| `namespace` | `default` |

The token grants the pod identity within the cluster. The `default` service account has no RBAC permissions to list pods or other resources (403 on API calls) — standard least-privilege configuration.

---

## Network Architecture

```
External
    │
    ├── :22   SSH (sshd)
    ├── :6080  VNC WebSocket (KasmVNC)
    ├── :5901  VNC RFB (KasmVNC)
    ├── :8888  Jupyter Kernel API (kernel_server.py)
    └── :9223  CDP proxy (socat → :9222)
                              │
                         :9222 Chromium CDP
                         (localhost only)

Internal cluster:
    └── 192.168.0.1:443  Kubernetes API (HTTPS)
    └── 192.168.0.10:53  CoreDNS
```

The container has no outbound internet access — all external TCP connections time out. DNS resolution works for both external names (via cluster DNS forwarding) and internal cluster names (`kubernetes.default.svc.cluster.local`).

---

## Process Map (Live)

| PID | User | Process |
|-----|------|---------|
| 1 | root | `s6-svscan` (PID 1 / init) |
| 47 | root | `sshd` |
| 48 | kimi | `python3 /app/kernel_server.py` |
| 49 | root | `/bin/bash /root/setup_kasmvnc.sh` |
| 50 | root | `socat TCP-LISTEN:9223 → :9222` |
| 52 | kimi | `python3 /app/browser_guard.py` |
| 110 | root | `Xvnc :99 -websocketPort 6080 -rfbport 5901` |
| 133 | kimi | `python3 -m ipykernel_launcher` (kernel instance 1) |
| 142 | kimi | `playwright/driver/node` |
| 330 | kimi | `chromium --remote-debugging-port=9222` |
| 362 | kimi | `python3 -m ipykernel_launcher` (kernel instance 2) |

---

## Infrastructure Context

- **Cloud:** Alibaba Cloud Container Service for Kubernetes (ACK), `cn-beijing`
- **Node type:** `virtual-kubelet-cn-beijing-i` (Elastic Container Instance / serverless)
- **Pod name pattern:** `k<numeric-id>` (e.g., `k2047731327130877957`)
- **Namespace:** `default`
- **Service account:** `default` (unprivileged)
- **Base OS:** Debian/Ubuntu-like Linux with standard FHS layout
- **Python:** 3.12.12 (system) + 3.11 (source in `/usr/src`)
- **Init system:** s6-overlay 3.1.6.2
- **Display:** Xvnc at 1920×1080 on `:99`
- **Writable paths:** `/app`, `/home/kimi`, `/mnt/agents`, `/tmp`, `/workspace`

---

## Key Technical Patterns Worth Noting

**s6-overlay as container init** — Instead of running a single process per container (the Docker ideal), this container runs a full supervision tree. s6-overlay is the standard way to do this correctly: it handles signal forwarding, service restarts, dependency ordering, and graceful shutdown — things that naive shell scripts in `CMD` get wrong.

**CDP over Playwright** — The `USE_CDP=1` flag switches from Playwright's high-level browser API to raw Chrome DevTools Protocol. This gives finer control over window state (minimize/maximize detection) and avoids Playwright's process management overhead when Chromium is already running as a system service.

**Kernel-per-session isolation** — The kernel server supports reset and interrupt operations, allowing the AI agent to recover from stuck or crashed code execution without restarting the entire container.

**execline service scripts** — All s6 service `run` files use `#!/command/with-contenv bash` as the shebang, which loads the container environment (from `/run/s6/container_environment/`) before executing. This ensures every service sees the same environment regardless of how it was started.

**socat CDP proxy** — Chromium's CDP is bound to `localhost:9222` for security. The socat service proxies it to `0.0.0.0:9223`, making it accessible from outside the container (e.g., from the Playwright driver running in a different process or pod).

- Note: Sensitive values have been redacted intentionally from this repository.No credentials or tokens are included.
