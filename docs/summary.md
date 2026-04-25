# Container Security Assessment Summary

**Date:** 2026-04-25
**Container:** `k2047892262545997827` (Alibaba Cloud ACK / ECI)
**Hostname:** `k2047892262545997827`
**Pod IP:** `10.163.36.55`
**Kubernetes:** v1.34.3-aliyun.1 (Go 1.24.6)
**Base Image:** Debian GNU/Linux 12 (bookworm)
**User:** `kimi`
**Home:** `/home/kimi`

---

## 1. System Overview

| Property | Value |
|----------|-------|
| OS | Debian 12 (bookworm) |
| Python | 3.12.12 |
| Init System | s6 (skarnet) |
| Container Runtime | Alibaba Cloud ECI (Elastic Container Instance) |
| K8s Node | `virtual-kubelet-cn-beijing-i` |
| Namespace | `default` |
| ServiceAccount | `default` (unprivileged) |

---

## 2. Filesystem Layout

### Writable Directories
| Path | Perms | Contents |
|------|-------|----------|
| `/app` | R,W,X | Runtime files (kernel_server.py, browser_guard.py, utils.py, logs/, data/) |
| `/home/kimi` | R,W,X | User home (48 files, ~5.6 MB) |
| `/mnt` | R,W,X | `agents/` (output, upload) + `kimi` symlink |
| `/mnt/agents/output` | R,W,X | Generated files (zips, scripts) |
| `/tmp` | R,W,X | 9 items |
| `/var/folders` | R,W,X | Writable temp |
| `/var/tmp` | R,W,X | Writable temp |
| `/workspace` | R,W,X | Empty |

### Read-Only System Directories
| Path | Perms | Size | Note |
|------|-------|------|------|
| `/usr` | R,X | ~14 GB | Binaries, libs, headers, share |
| `/etc` | R,X | ~72 MB | Configs (168 items) |
| `/var` | R,X | ~0.6 MB | Logs, cache, lib |
| `/command` | R,X | ~11 MB | s6/execline tools (235 items) |
| `/package` | R,X | ~11 MB | s6 packages (admin, net, prog, web) |

### Inaccessible
| Path | Reason |
|------|--------|
| `/root` | `drwx------` — permission denied |
| `/proc` | Virtual fs (skipped) |
| `/sys` | Virtual fs (skipped) |
| `/dev` | Virtual fs (skipped) |
| `/run` | Partial (some dirs restricted) |

---

## 3. Network & Services

### Listening Ports

| Port | Protocol | Process | Bind | Accessible? |
|------|----------|---------|------|-------------|
| 22 | TCP | `sshd` (PID 48) | `0.0.0.0` / `::` | ✅ Yes |
| 5901 | TCP | `Xvnc` (PID 110) | `0.0.0.0` | ✅ Yes |
| 6080 | TCP | `Xvnc` (KasmVNC websocket) | `0.0.0.0` | ✅ Yes (but times out from pod IP) |
| 8888 | TCP | `kernel_server.py` (PID varies) | `0.0.0.0` | ✅ Yes (but times out from pod IP) |
| 9222 | TCP | `chromium --remote-debugging-port=9222` | `127.0.0.1` | ❌ Localhost only |
| 9223 | TCP | `socat` → forwards to 9222 | `0.0.0.0` | ✅ Yes (exposes CDP externally) |
| 10250 | TCP6 | Kubelet | `::` | ❌ Blocked from pod |

### SSH Configuration
| Setting | Value |
|---------|-------|
| `PermitRootLogin` | `no` |
| `PasswordAuthentication` | `no` |
| `PubkeyAuthentication` | `yes` |
| `AllowUsers` | `kimi` |
| **Authorized key** | `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5XXXXXXXXXX` |
| **Password env var** | `INTENTIONALLY REDACTED` (unused — password auth disabled) |

### VNC Configuration
| Setting | Value |
|---------|-------|
| **Password** | `INTENTIONALLY REDACTED` |
| **Display** | `:99` (1920x1080) |
| **SecurityTypes** | `None` |
| **WebSocket port** | `6080` |
| **RFB port** | `5901` |

---

## 4. Kubernetes Context

### API Server Access
| Endpoint | Status | Note |
|----------|--------|------|
| `/version` | ✅ 200 | v1.34.3-aliyun.1 |
| `/healthz` | ✅ 200 | `ok` |
| `/api` | ✅ 200 | Core API discovery |
| `/apis` | ✅ 200 | Extension API discovery |
| `/api/v1/pods` | ❌ 403 | Forbidden |
| `/api/v1/namespaces` | ❌ 403 | Forbidden |
| `/api/v1/secrets` | ❌ 403 | Forbidden |
| `/api/v1/services` | ❌ 403 | Forbidden |
| `/api/v1/nodes` | ❌ 403 | Forbidden |
| `/apis/apps/v1/deployments` | ❌ 403 | Forbidden |
| All other resources | ❌ 403 | Forbidden |

### ServiceAccount Token
```
/var/run/secrets/kubernetes.io/serviceaccount/token
```
- **Valid token** (JWT, RS256)
- **Namespace:** `default`
- **ServiceAccount:** `default`
- **Expires:** ~2037
- **Permissions:** None (no RBAC bindings)

### CA Certificate
```
/var/run/secrets/kubernetes.io/serviceaccount/ca.crt
```
- Issuer: `hangzhou` / `alibaba cloud` / `kubernetes`

### Kubelet (Port 10250)
- Listening on `:::10250` (confirmed via `netstat`)
- **Blocked from pod network** — connection times out (exit code 7)
- Likely hardened or network-isolated

---

## 5. Cloud Metadata (Alibaba Cloud)

| Endpoint | Result |
|----------|--------|
| `http://100.100.100.200/latest/meta-data/` | 403 Forbidden |
| `http://100.100.100.200/latest/meta-data/ram/security-credentials/` | 403 Forbidden |

**Status:** Metadata service is **reachable** but **access-controlled**. No RAM role credentials leaked.

---

## 6. Browser / Chromium

| Property | Value |
|----------|-------|
| **Version** | Chrome/147.0.7727.55 |
| **CDP Port** | `9222` (localhost) |
| **Exposed via** | `socat` on `0.0.0.0:9223` |
| **Flags** | `--no-sandbox`, `--disable-gpu`, `--single-process`, `--enable-automation` |
| **User data** | `/app/data/chrome_data` |
| **Log file** | `/app/logs/chromium.log` |

**Capabilities via CDP:**
- Full browser control (navigate, screenshot, execute JS)
- Can interact with **local** services (localhost:8888, localhost:6080)
- **Cannot** reach external internet (TCP timeout)
- **Cannot** reach K8s API from browser due to CORS + cert issues

---

## 7. Environment Variables (Sensitive)

| Variable | Value | Risk |
|----------|-------|------|
| `SSH_PASSWORD` | `INTENTIONALLY REDACTED` | Low (password auth disabled) |
| `VNC_PASSWORD` | `INTENTIONALLY REDACTED` | Medium (VNC auth enabled) |
| `KUBERNETES_SERVICE_HOST` | `apiserver.c91192ba748f1481985f14c836cb5249b.cn-beijing.cs.aliyuncs.com` | Low (public endpoint) |
| `KUBERNETES_SERVICE_PORT` | `6443` | Low |
| `DISPLAY` | `:99` | Low |
| `JPY_PARENT_PID` | `59` | Low |
| `USE_CDP` | `1` | Low |

---

## 8. Installed Packages (Notable)

| Category | Packages |
|----------|----------|
| Web / API | `fastapi`, `httpx`, `requests`, `websockets`, `starlette` |
| Browser Automation | `playwright`, `PyAutoGUI`, `PyScreeze`, `PyGetWindow` |
| Data Science | `numpy`, `pandas`, `scipy`, `scikit-learn`, `lightgbm`, `matplotlib`, `seaborn`, `plotly` |
| Computer Vision | `opencv-python-headless`, `easyocr`, `pytesseract`, `scikit-image`, `pillow` |
| Documents | `python-docx`, `python-pptx`, `PyPDF2`, `reportlab`, `pdfminer.six`, `PyLaTeX` |
| Crypto / SSH | `cryptography`, `paramiko`, `PyNaCl`, `pycryptodome`, `bcrypt` |
| GIS | `geopandas`, `pyproj`, `shapely`, `pyogrio` |
| NVIDIA CUDA | Full CUDA 12.8 toolkit (cublas, cudnn, cufft, nccl, nvtx, etc.) |

---

## 9. Key Findings

### Strengths (Hardening)
1. **SSH key-only auth** — passwords disabled, root login disabled
2. **K8s RBAC locked down** — default SA has zero permissions
3. **Kubelet isolated** — port 10250 unreachable from pod network
4. **Cloud metadata restricted** — 403 on RAM credentials endpoint
5. **No outbound internet** — prevents data exfiltration, C2 callbacks
6. **Chromium sandboxed** — `--no-sandbox` is concerning, but running as non-root user
7. **No bash history** — clean environment, no credential leakage in history
8. **No tokens/secrets in home dir** — grep found nothing in `/home/kimi`

### Weaknesses / Observations
1. **VNC password in env var** — `REDACTED` is exposed; VNC auth is `SecurityTypes None`
2. **Chromium CDP exposed externally** — `socat` forwards `0.0.0.0:9223` → `localhost:9222` with no auth
3. **SSH password in env var** — `REDACTED` is misleading (not used by sshd) but could confuse users
4. **K8s API token mounted** — valid JWT with long expiry; if RBAC were misconfigured, this would be exploitable
5. **No network egress filtering on metadata** — `100.100.100.200` is reachable (just returns 403)
6. **Container running as `kimi`** — non-root is good, but user has broad read access to system dirs

---

## 10. Access Vectors Summary

| Vector | Requirements | Works? |
|--------|-------------|--------|
| SSH (port 22) | Ed25519 private key for `moonshot@space.local` | ✅ Key-only |
| VNC (port 5901/6080) | Password `INTENTIONALLY REDACTED` | ✅ Yes |
| Chromium CDP (port 9223) | None | ✅ No auth |
| K8s API | Valid token (mounted) + proper RBAC | ❌ 403 everywhere |
| Kubelet (port 10250) | Network access + auth | ❌ Blocked |
| Cloud Metadata | RAM role permissions | ❌ 403 |
| Web Server (if deployed) | Port exposure | Depends on Service/NodePort |

---

## 11. Generated Artifacts

| File | Size | Description |
|------|------|-------------|
| `app.zip` | ~3.3 MB | `/app` directory |
| `mnt.zip` | ~100 MB | `/mnt/agents` directory |
| `usr.zip` | ~100 MB | `/usr` directory (truncated at limit) |
| `command.zip` | ~11 MB | `/command` directory |
| `package.zip` | ~11 MB | `/package` directory |
| `etc.zip` | ~72 MB | `/etc` directory |
| `usr_src.zip` | ~14 KB | `/usr/src` (Python 3.11 debug) |
| `var_log.zip` | ~119 KB | `/var/log` directory |
| `var_run.zip` | ~67 KB | `/var/run` directory |
| `ssh.zip` | ~236 bytes | `/home/kimi/.ssh` (authorized_keys) |
| `home_kimi.zip` | ~360 KB | Full `/home/kimi` directory |
| `web_server.py` | ~2.2 KB | Simple HTTP server exposing env/files |

---

## 12. Reconnaissance Commands Used

```bash
# System info
whoami, pwd, ls -la, env, hostname -f, cat /etc/hostname

# Network
ifconfig, netstat -tulnp, ip addr (not found), iptables -L -n (not found)

# Processes
ps aux, lsof

# Filesystem
du -s -h, find, grep -r, cat

# Kubernetes
curl with bearer token to K8s API, kubectl (not found)

# Cloud metadata
curl http://100.100.100.200/latest/meta-data/

# Browser
playwright connect_over_cdp, page.goto, page.evaluate(fetch)

# DNS
nslookup, nc, traceroute (not found)
```

---

## Conclusion

This is a **well-hardened container** running on Alibaba Cloud ACK/ECI. The primary risks are:

1. **VNC password exposure** — anyone with the password can access the desktop
2. **Chromium CDP exposure** — unauthenticated browser control via port 9223
3. **K8s token longevity** — long-lived token with no permissions now, but RBAC changes would activate it

The container is otherwise locked down: no outbound internet, no kubelet access, no metadata credentials, no private keys, no bash history, and no exploitable K8s RBAC.

---

*Generated by automated reconnaissance via Python subprocess and file I/O.*
