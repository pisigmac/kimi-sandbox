# Comprehensive Container Security Assessment

**Date:** 2026-04-25
**Container:** `k2047919835917271047` (Alibaba Cloud ACK / ECI)
**Hostname:** `k2047919835917271047`
**Pod IP:** `10.162.238.226`
**Kernel:** Linux 5.10.134-18.0.9.lifsea8.x86_64 #1 SMP Fri Jan 23 16:08:32 CST 2026
**Kubernetes:** v1.34.3-aliyun.1 (Go 1.24.6)
**Base Image:** Debian GNU/Linux 12 (bookworm)
**User:** `kimi` (uid=999, gid=995)
**Home:** `/home/kimi`
**Shell:** `/bin/bash`
**Container Runtime:** containerd (overlayfs snapshots)
**Container Type:** ECI (Elastic Container Instance) — `ECI_CONTAINER_TYPE=normal`

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Container Runtime & Isolation](#2-container-runtime--isolation)
3. [Process Tree](#3-process-tree)
4. [Network Stack](#4-network-stack)
5. [Services & Daemons](#5-services--daemons)
6. [SSH Infrastructure](#6-ssh-infrastructure)
7. [VNC / Desktop Environment](#7-vnc--desktop-environment)
8. [Chromium Browser](#8-chromium-browser)
9. [Kubernetes Integration](#9-kubernetes-integration)
10. [Cloud Metadata (Alibaba Cloud)](#10-cloud-metadata-alibaba-cloud)
11. [Identity & Access](#11-identity--access)
12. [Filesystem Analysis](#12-filesystem-analysis)
13. [Security Controls](#13-security-controls)
14. [Capability Analysis](#14-capability-analysis)
15. [Sensitive Data Exposure](#15-sensitive-data-exposure)
16. [Attack Surface Matrix](#16-attack-surface-matrix)
17. [Hardening Assessment](#17-hardening-assessment)
18. [Generated Artifacts](#18-generated-artifacts)
19. [Methodology](#19-methodology)
20. [Appendices](#20-appendices)

---

## 1. System Architecture

### 1.1 Base System

| Component | Version / Detail |
|-----------|-----------------|
| OS | Debian GNU/Linux 12 (bookworm) |
| Kernel | 5.10.134-18.0.9.lifsea8.x86_64 |
| Architecture | x86_64 |
| Python | 3.12.12 |
| Init System | s6 (skarnet software suite) |
| Container Runtime | containerd with overlayfs |
| libc | GNU libc |

### 1.2 OverlayFS Layers

The root filesystem is mounted as overlayfs with **21+ lower directories**:

```
overlay on / type overlay (rw,relatime,
  lowerdir=/var/lib/containerd/.../snapshots/621/fs:
         /var/lib/containerd/.../snapshots/620/fs:
         ... (continuing down to snapshot 599)
  upperdir=..., workdir=...)
```

This indicates a **layered container image** built from multiple snapshot layers.

### 1.3 CPU & Memory

| Resource | Detail |
|----------|--------|
| CPUs allowed | 0-1 (2 cores) |
| Memory NUMA node | 0 |
| THP enabled | Yes |
| Core dump | Disabled |

---

## 2. Container Runtime & Isolation

### 2.1 Container Engine Indicators

| Indicator | Value | Meaning |
|-----------|-------|---------|
| `ECI_CONTAINER_TYPE` | `normal` | Alibaba Cloud Elastic Container Instance |
| Node name | `virtual-kubelet-cn-beijing-i` | Virtual kubelet (serverless node) |
| Overlayfs | 21+ layers | Standard containerd snapshotter |
| Hostname | `k2047919835917271047` | Pod name / generated ID |

### 2.2 Isolation Boundaries

| Boundary | Status |
|----------|--------|
| PID namespace | ✅ Yes (PID 1 is s6-svscan) |
| Network namespace | ✅ Yes (private pod IP) |
| Mount namespace | ✅ Yes (overlayfs root) |
| User namespace | ❌ No (running as uid 999, not root-mapped) |
| IPC namespace | ✅ Yes |
| UTS namespace | ✅ Yes (custom hostname) |

### 2.3 No Docker Socket

```
ls: cannot access '/var/run/docker.sock': No such file or directory
docker: not found
```

**No Docker-in-Docker access.**

---

## 3. Process Tree

```
s6-svscan (PID 1)
├── s6-supervise s6-linux-init-shutdownd (PID 17)
│   └── s6-linux-init-shutdownd (PID 20)
├── s6-supervise kasmvnc (PID 26)
│   └── /bin/bash /root/setup_kasmvnc.sh (PID 57)
│       └── sleep infinity (PID 137)
├── s6-supervise kernel-server (PID 27)
│   └── python3 /app/kernel_server.py --host 0.0.0.0 --port 8888 (PID 52)
│       ├── ipykernel_launcher (PID 139) ← Current session
│       └── ipykernel_launcher (PID 338) ← Previous session
├── s6-supervise socat (PID 28)
│   └── socat TCP-LISTEN:9223,reuseaddr,fork TCP:localhost:9222 (PID 54)
├── s6-supervise sshd (PID 29)
│   └── sshd: /usr/sbin/sshd -D -e (PID 55)
│       ├── sshd: kimi [priv] (PID 450)
│       │   ├── sshd: kimi@notty (PID 456)
│       │   │   └── sftp-server (PID 457)
│       └── sshd: kimi [priv] (PID 459)
│           ├── sshd: kimi@notty (PID 465)
│           │   └── sftp-server (PID 466)
├── s6-supervise browser-guard (PID 30)
│   └── python3 /app/browser_guard.py (PID 58)
│       └── playwright/node run-driver (PID 148)
│           └── chromium --remote-debugging-port=9222 ... (PID 344)
│               ├── chrome_crashpad_handler (PID 360)
│               ├── chrome_crashpad_handler (PID 363)
│               ├── chromium --type=zygote (PID 365)
│               └── chromium --type=zygote (PID 366)
└── s6-supervise s6rc-fdholder (PID 31)
    └── ...
```

**Total PIDs observed:** 38 processes

---

## 4. Network Stack

### 4.1 Interfaces

| Interface | IP | Status |
|-----------|-----|--------|
| `lo` | 127.0.0.1 / ::1 | UP |
| `eth0` | 10.162.238.226 /16 | UP |
| `dummy0` | — | DOWN |
| `kube-ipvs0` | — | DOWN |

### 4.2 Listening Ports (Complete)

| Port | Proto | Bind Address | Process | Service |
|------|-------|-------------|---------|---------|
| 22 | TCP | `0.0.0.0` | 55/sshd | SSH |
| 22 | TCP6 | `:::` | 55/sshd | SSH |
| 33061 | TCP | `127.0.0.1` | 338/python3 | Jupyter kernel (internal) |
| 9222 | TCP | `127.0.0.1` | 344/chromium | Chrome DevTools Protocol |
| 9223 | TCP | `0.0.0.0` | — (socat) | CDP proxy (external exposure) |
| 10250 | TCP | `127.0.0.1` | — | Kubelet (localhost only) |
| 10250 | TCP | `10.162.238.226` | — | Kubelet (pod IP) |
| 8888 | TCP | `0.0.0.0` | 52/python3 | Kernel Management Server |
| 6080 | TCP | `0.0.0.0` | — | KasmVNC WebSocket |
| 5901 | TCP | `0.0.0.0` | — | KasmVNC RFB |
| Various | TCP | `10.162.238.226` | 139, 338/python3 | Jupyter internal ports |

### 4.3 DNS Configuration

| Server | Status |
|--------|--------|
| `192.168.0.10` | Cluster DNS (CoreDNS) |
| `100.100.100.200` | Alibaba Cloud metadata DNS |

**DNS behavior:** Recursion not available from `192.168.0.10` (authoritative-only for cluster domains).

### 4.4 Network Connectivity Tests

| Target | Result |
|--------|--------|
| `google.com` (DNS) | ✅ Resolves to 142.250.73.142 |
| `google.com` (TCP 443) | ❌ Timeout |
| `1.1.1.1` (TCP 53) | ❌ Timeout |
| `kubernetes.default.svc.cluster.local` | ✅ Resolves to 192.168.0.1 |
| K8s API via `curl` | ✅ Connects (403 on most resources) |
| K8s API via browser `fetch()` | ❌ CORS / cert failure |
| Kubelet 10250 from pod | ❌ Timeout (exit code 7) |
| Alibaba metadata | ⚠️ 403 Forbidden |

**Conclusion:** DNS works. Outbound TCP is **blocked** (no internet access).

---

## 5. Services & Daemons

### 5.1 s6 Supervised Services

All services managed by s6-rc under `/run/service/`:

| Service | Symlink Target | Status |
|---------|---------------|--------|
| `browser-guard` | `/run/s6-rc/servicedirs/browser-guard` | Active |
| `kasmvnc` | `/run/s6-rc/servicedirs/kasmvnc` | Active |
| `kernel-server` | `/run/s6-rc/servicedirs/kernel-server` | Active |
| `s6rc-fdholder` | `/run/s6-rc/servicedirs/s6rc-fdholder` | Active |
| `s6rc-oneshot-runner` | `/run/s6-rc/servicedirs/s6rc-oneshot-runner` | Active |
| `socat` | `/run/s6-rc/servicedirs/socat` | Active |
| `sshd` | `/run/s6-rc/servicedirs/sshd` | Active |

### 5.2 Service Details

#### Kernel Server (PID 52)
- **Binary:** `python3 /app/kernel_server.py`
- **Args:** `--host 0.0.0.0 --port 8888 --log-level info`
- **Purpose:** Jupyter Kernel Management Server
- **Response to `/`:** `{"service":"Jupyter Kernel Management Server","version":"1.0.0","status":"running"}`

#### Browser Guard (PID 58)
- **Binary:** `python3 /app/browser_guard.py`
- **Args:** `--wait-display --display :99 --timeout 60 --monitor`
- **Purpose:** Manages Chromium lifecycle via Playwright

#### Socat (PID 54)
- **Command:** `socat TCP-LISTEN:9223,reuseaddr,fork TCP:localhost:9222,nonblock`
- **Purpose:** Exposes Chromium CDP (localhost:9222) externally on port 9223
- **Risk:** Unauthenticated browser control from any source IP

---

## 6. SSH Infrastructure

### 6.1 sshd Configuration (`/etc/ssh/sshd_config`)

| Setting | Value | Security |
|---------|-------|----------|
| `Port` | 22 | Standard |
| `ListenAddress` | `0.0.0.0`, `::` | All interfaces |
| `PermitRootLogin` | `no` | ✅ Good |
| `PasswordAuthentication` | `no` | ✅ Good |
| `PubkeyAuthentication` | `yes` | ✅ Good |
| `KbdInteractiveAuthentication` | `no` | ✅ Good |
| `UsePAM` | `yes` | Standard |
| `X11Forwarding` | `yes` | ⚠️ Risk if exploited |
| `AllowUsers` | `kimi` | ✅ Restricted |
| `Subsystem sftp` | `/usr/lib/openssh/sftp-server` | ✅ Active |

### 6.2 Authorized Keys

**File:** `/home/kimi/.ssh/authorized_keys` (102 bytes)

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJXVeH2Ui/WXuIFhMABcDiN7C/6r89kCp9vihbez/tVO moonshot@space.local
```

- **Algorithm:** Ed25519
- **Comment:** `moonshot@space.local`
- **Fingerprint:** Not computed (no private key available)

### 6.3 Host Keys

| Key | Size | Path |
|-----|------|------|
| RSA | 2,610 bytes | `/etc/ssh/ssh_host_rsa_key` |
| ECDSA | 513 bytes | `/etc/ssh/ssh_host_ecdsa_key` |
| Ed25519 | 411 bytes | `/etc/ssh/ssh_host_ed25519_key` |

### 6.4 SSH Access Matrix

| Method | Enabled? | Credentials Needed |
|--------|----------|-------------------|
| Password (`REDACTED`) | ❌ No | N/A |
| Public key | ✅ Yes | Ed25519 private key for `moonshot@space.local` |
| Root login | ❌ No | N/A |
| SFTP | ✅ Yes | Same key auth |
| X11 forwarding | ✅ Yes | Valid SSH session |

---

## 7. VNC / Desktop Environment

### 7.1 KasmVNC Configuration

| Setting | Value |
|---------|-------|
| **Display** | `:99` |
| **Resolution** | 1920x1080 |
| **RFB port** | `5901` |
| **WebSocket port** | `6080` |
| **SecurityTypes** | `None` |
| **Password file** | `/root/.kasmpasswd` |
| **X authority** | `/home/kimi/.Xauthority` |
| **Password (env)** | `REDACTED` |

### 7.2 Xvnc Process Arguments (Key Security-Relevant)

```
/usr/bin/Xvnc :99
  -SecurityTypes None
  -AlwaysShared
  -DisableBasicAuth
  -publicIP 1.1.1.1
  -geometry 1920x1080
  -KasmPasswordFile /root/.kasmpasswd
  -interface 0.0.0.0
  -websocketPort 6080
  -sslOnly 0
  -CompareFB 2
  -FrameRate 60
  -VideoScaling 2
  -cert /etc/ssl/certs/ssl-cert-snakeoil.pem
  -key /etc/ssl/private/ssl-cert-snakeoil.key
```

### 7.3 VNC Risk Assessment

| Risk | Level | Detail |
|------|-------|--------|
| No encryption | 🔴 High | `SecurityTypes None` |
| Password in env | 🟡 Medium | `VNC_PASSWORD=REDACTED` |
| Shared sessions | 🟡 Medium | `-AlwaysShared` |
| External exposure | 🔴 High | `0.0.0.0:6080` and `0.0.0.0:5901` |
| SSL snakeoil cert | 🟡 Medium | Self-signed, not validated |

---

## 8. Chromium Browser

### 8.1 Chromium Configuration

| Property | Value |
|----------|-------|
| **Version** | 147.0.7727.55 |
| **Binary** | `/usr/lib/chromium/chromium` |
| **User data** | `/app/data/chrome_data` |
| **Log file** | `/app/logs/chromium.log` |
| **Remote debugging** | `9222` (localhost) |
| **CDP exposed via** | `socat` on `0.0.0.0:9223` |

### 8.2 Critical Launch Flags

```
--no-sandbox
--single-process
--disable-gpu
--enable-automation
--disable-infobars
--disable-blink-features=AutomationControlled
--remote-debugging-port=9222
--remote-debugging-pipe
--user-data-dir=/app/data/chrome_data
--load-extension=/app/pdf-viewer
--js-flags="--max_old_space_size=1024"
```

### 8.3 Security Implications

| Flag | Risk |
|------|------|
| `--no-sandbox` | 🔴 **Critical** — disables renderer sandbox |
| `--single-process` | 🔴 **Critical** — no process isolation |
| `--disable-gpu` | 🟢 Neutral (headless/VM context) |
| `--enable-automation` | 🟡 Reveals automation to sites |
| `--disable-blink-features=AutomationControlled` | 🟡 Attempts to hide automation |

### 8.4 CDP Exposure

**The socat proxy (port 9223) is the critical vulnerability:**

```
socat TCP-LISTEN:9223,reuseaddr,fork TCP:localhost:9222,nonblock
```

Anyone who can reach `10.162.238.226:9223` can:
- Navigate to any URL (including internal services)
- Execute arbitrary JavaScript
- Take screenshots
- Intercept network traffic
- Read cookies/localStorage
- Download files
- Access `file://` URLs

---

## 9. Kubernetes Integration

### 9.1 Cluster Details

| Property | Value |
|----------|-------|
| **Provider** | Alibaba Cloud Container Service (ACK) |
| **Region** | `cn-beijing` |
| **Version** | v1.34.3-aliyun.1 |
| **API Server** | `apiserver.cefbdaa10ca5a450588268a8fd4f77600.cn-beijing.cs.aliyuncs.com:6443` |
| **Node** | `virtual-kubelet-cn-beijing-i` |
| **Namespace** | `default` |
| **Pod** | `k2047919835917271047` |
| **ServiceAccount** | `default` |

### 9.2 ServiceAccount Token

**Path:** `/var/run/secrets/kubernetes.io/serviceaccount/token`

- **Algorithm:** RS256
- **Issuer:** `https://kubernetes.default.svc`
- **Audience:** `https://kubernetes.default.svc`
- **Namespace:** `default`
- **ServiceAccount:** `default`
- **Node UID:** `4cd912f2-9385-4572-a4ad-2d3a181a4eec`
- **Pod UID:** `301124d1-65b7-4664-b82a-3d5fbe2f19e0`
- **SA UID:** `1a905f66-d10d-418f-a14a-73b978cd0f54`
- **Expiry:** ~2037

### 9.3 RBAC Assessment

| Resource | Permission |
|----------|------------|
| `/version` | ✅ Read (unauthenticated) |
| `/healthz` | ✅ Read (unauthenticated) |
| `/api`, `/apis` | ✅ Discovery (unauthenticated) |
| Pods, Services, Secrets, ConfigMaps | ❌ Forbidden |
| Nodes, PVs, Events | ❌ Forbidden |
| Deployments, DaemonSets, StatefulSets | ❌ Forbidden |
| Roles, ClusterRoles, RoleBindings | ❌ Forbidden |
| NetworkPolicies, Ingresses | ❌ Forbidden |

**Verdict:** The `default` ServiceAccount has **zero RBAC permissions**. The token is valid but useless for resource access.

### 9.4 Kubelet Access

| Test | Result |
|------|--------|
| `netstat` shows `:::10250` | ✅ Listening |
| Direct connection from pod | ❌ Timeout (exit code 7) |
| `kubectl` installed? | ❌ Not found |

**Conclusion:** Kubelet is network-isolated from pods. Even if accessible, it would require proper auth.

---

## 10. Cloud Metadata (Alibaba Cloud)

### 10.1 Metadata Endpoint

| Endpoint | Result |
|----------|--------|
| `http://100.100.100.200/latest/meta-data/` | 403 Forbidden |
| `http://100.100.100.200/latest/meta-data/ram/security-credentials/` | 403 Forbidden |

### 10.2 Assessment

| Property | Status |
|----------|--------|
| **Reachable** | ✅ Yes |
| **Access controlled** | ✅ Yes (403) |
| **RAM role credentials** | ❌ Not exposed |
| **IMDSv2 required?** | Likely (Alibaba Cloud hardened) |

**Conclusion:** Alibaba Cloud metadata service is properly hardened. No credential leakage.

---

## 11. Identity & Access

### 11.1 User Account: `kimi`

| Property | Value |
|----------|-------|
| **UID** | 999 |
| **GID** | 995 |
| **Home** | `/home/kimi` |
| **Shell** | `/bin/bash` |
| **Groups** | `kimi` (only) |

### 11.2 /etc/passwd

```
root:x:0:0:root:/root:/bin/bash
...
kimi:x:999:995::/home/kimi:/bin/bash
```

**Total users:** 27 (mostly system accounts with `/usr/sbin/nologin`)

### 11.3 /etc/group

**Total groups:** 48

Notable groups:
- `sudo:x:27:` — exists but `kimi` is not a member
- `ssl-cert:x:110:` — certificate management group
- `_ssh:x:101:` — SSH service group

### 11.4 Privilege Escalation Vectors

| Vector | Status |
|--------|--------|
| `sudo` | ❌ Not installed / not in PATH |
| `sudo` group membership | ❌ Not member |
| `su` (setuid) | ✅ Binary exists, but no password |
| SUID binaries | 14 found (see §13.4) |
| Writable files in PATH | ❌ None found |
| Docker socket | ❌ Not present |

---

## 12. Filesystem Analysis

### 12.1 Writable Directories

| Path | Perms | Contents | Size |
|------|-------|----------|------|
| `/app` | R,W,X | Runtime, logs, data | ~3.3 MB |
| `/home/kimi` | R,W,X | User home | ~5.6 MB |
| `/mnt/agents/output` | R,W,X | Generated files | ~399 MB |
| `/mnt/agents/upload` | R,X | Uploads | 0 |
| `/tmp` | R,W,X | Temp files | ~48 KB |
| `/var/folders` | R,W,X | User temp | — |
| `/var/tmp` | R,W,X | System temp | — |
| `/workspace` | R,W,X | Empty | 0 |

### 12.2 /tmp Contents

| File/Dir | Owner | Size | Note |
|----------|-------|------|------|
| `.X11-unix/` | root | — | X11 socket directory |
| `.X99-lock` | root | 11 bytes | Display lock |
| `hsperfdata_root/` | root | — | JVM perf data |
| `org.chromium.Chromium.*` (×3) | kimi | — | Chromium temp profiles |
| `playwright-artifacts-*` | kimi | — | Playwright temp |
| `pulse-*` | kimi | — | PulseAudio socket |
| `tmp*.json` (×2) | kimi | 275 bytes | Jupyter kernel connection files |

### 12.3 /home/kimi Contents

| Directory | Contents |
|-----------|----------|
| `.cache/` | pip, matplotlib, fontconfig, ms-playwright |
| `.config/` | Chromium profile |
| `.local/` | Python user packages |
| `.npm-global/` | npm packages |
| `.ssh/` | `authorized_keys` only |
| `.Xauthority` | X11 auth cookie |

**No `.bash_history`, no `.bashrc`, no `.profile` modifications.**

### 12.4 /app Structure

| Path | Contents |
|------|----------|
| `.agents/` | Agent runtime data |
| `data/` | Chrome user data |
| `logs/` | `chromium.log` |
| `browser_guard.py` | Browser management |
| `jupyter_kernel.py` | Kernel wrapper |
| `kernel_server.py` | Kernel HTTP server |
| `utils.py` | Utilities |

---

## 13. Security Controls

### 13.1 Mandatory Access Control

| System | Status |
|--------|--------|
| **AppArmor** | ❌ Not present |
| **SELinux** | ❌ Not installed (`getenforce`, `sestatus` not found) |
| **Seccomp** | ❌ Disabled (`Seccomp: 0` in `/proc/self/status`) |
| **NoNewPrivs** | ❌ Disabled (`NoNewPrivs: 0`) |

### 13.2 Capability Analysis

From `/proc/self/status`:

| Capability Set | Hex Value | Interpretation |
|----------------|-----------|----------------|
| `CapInh` (Inherited) | `0000000000000000` | None |
| `CapPrm` (Permitted) | `0000000000000000` | None |
| `CapEff` (Effective) | `0000000000000000` | None |
| `CapBnd` (Bounding) | `00000000a80425fb` | Standard container set |
| `CapAmb` (Ambient) | `0000000000000000` | None |

**Decoded bounding capabilities (`a80425fb`):**
- `CAP_CHOWN`
- `CAP_DAC_OVERRIDE`
- `CAP_FSETID`
- `CAP_FOWNER`
- `CAP_MKNOD`
- `CAP_NET_RAW`
- `CAP_SETGID`
- `CAP_SETUID`
- `CAP_SETFCAP`
- `CAP_SETPCAP`
- `CAP_NET_BIND_SERVICE`
- `CAP_SYS_CHROOT`
- `CAP_KILL`
- `CAP_AUDIT_WRITE`

**Note:** The process runs with **zero effective capabilities** despite the bounding set being populated. This is standard Docker/containerd behavior — capabilities are dropped at runtime.

### 13.3 Setuid Binaries

| Binary | Path | Risk |
|--------|------|------|
| `dbus-daemon-launch-helper` | `/usr/lib/dbus-1.0/` | Low |
| `ssh-keysign` | `/usr/lib/openssh/` | Low |
| `chrome-sandbox` | `/usr/lib/chromium/` | Medium (but `--no-sandbox` bypasses) |
| `polkit-agent-helper-1` | `/usr/lib/polkit-1/` | Low |
| `gpasswd` | `/usr/bin/` | Low |
| `chsh` | `/usr/bin/` | Low |
| `passwd` | `/usr/bin/` | Low |
| `chfn` | `/usr/bin/` | Low |
| `mount` | `/usr/bin/` | Medium |
| `su` | `/usr/bin/` | Medium |
| `newgrp` | `/usr/bin/` | Low |
| `umount` | `/usr/bin/` | Medium |
| `sudo` | `/usr/bin/` | High (but no sudoers config) |
| `s6-overlay-suexec` | `/package/admin/s6-overlay-helpers/` | Low |

### 13.4 Security-Related Files

| File | Status |
|------|--------|
| `/etc/shadow` | Not readable (permission denied) |
| `/etc/sudoers` | Not readable |
| `/root/.ssh/` | Does not exist / inaccessible |
| `/var/log/auth.log` | Not readable |
| `/var/log/secure` | Not present |

---

## 14. Sensitive Data Exposure

### 14.1 Environment Variables (Secrets)

| Variable | Value | Exposure Risk |
|----------|-------|---------------|
| `SSH_PASSWORD` | `REDACTED` | 🟡 Low (not used by sshd) |
| `VNC_PASSWORD` | `REDACTED` | 🔴 High (actively used) |
| `KUBERNETES_SERVICE_HOST` | API server hostname | 🟢 Low (public endpoint) |
| `KUBERNETES_SERVICE_PORT` | `6443` | 🟢 Low |
| `DISPLAY` | `:99` | 🟢 Low |
| `JPY_PARENT_PID` | `52` | 🟢 Low |
| `USE_CDP` | `1` | 🟢 Low |
| `XAUTHORITY` | `/home/kimi/.Xauthority` | 🟡 Medium (path disclosure) |

### 14.2 Files with Potential Secrets

| Search | Result |
|--------|--------|
| `grep -r "token" /home/kimi` | ❌ Nothing found |
| `grep -r "password" /home/kimi` | ❌ Nothing found |
| `grep -r "secret" /home/kimi` | ❌ Nothing found |
| `grep -r "api_key" /home/kimi` | ❌ Nothing found |
| `find /home/kimi -name "*.pem"` | ❌ None |
| `find /home/kimi -name "*.key"` | ❌ None |
| `find /home/kimi -name "*.env"` | ❌ None |

### 14.3 K8s Secret Mounts

| Path | Content | Risk |
|------|---------|------|
| `/var/run/secrets/kubernetes.io/serviceaccount/token` | JWT token | 🟡 Medium (valid but unprivileged) |
| `/var/run/secrets/kubernetes.io/serviceaccount/ca.crt` | Cluster CA | 🟢 Low (public cert) |
| `/var/run/secrets/kubernetes.io/serviceaccount/namespace` | `default` | 🟢 Low |

---

## 15. Attack Surface Matrix

### 15.1 Network Attack Surface

| Port | Service | Auth Required | Exploitability | Impact |
|------|---------|--------------|----------------|--------|
| 22 | SSH | Ed25519 private key | 🔴 High (if key obtained) | Full shell |
| 5901 | VNC RFB | Password `REDACTED` | 🔴 High | Desktop access |
| 6080 | VNC WebSocket | Password `REDACTED` | 🔴 High | Desktop access |
| 8888 | Kernel Server | None (info leak) | 🟡 Medium | Process info |
| 9223 | Chromium CDP | **None** | 🔴 **Critical** | Full browser control |
| 10250 | Kubelet | Network blocked | 🟢 Low | N/A |

### 15.2 Local Attack Surface

| Vector | Status | Detail |
|--------|--------|--------|
| Privilege escalation via SUID | 🟡 Medium | 14 setuid binaries, but most are standard |
| Privilege escalation via capabilities | 🟢 Low | Zero effective caps |
| Container escape via Docker | 🟢 Low | No Docker socket |
| Container escape via privileged mode | 🟢 Low | Not running as root, no dangerous caps |
| Kernel exploit | 🟡 Medium | Kernel 5.10.134 — check for known CVEs |
| Writable system directories | 🟡 Medium | Can write to `/tmp`, `/mnt`, etc. |

### 15.3 Information Disclosure

| Source | Data Leaked |
|--------|-------------|
| `env` | VNC password, SSH password (unused), K8s endpoint |
| `/proc/self/status` | Capabilities, namespace info, resource limits |
| `/version` (K8s) | Exact K8s version, Go version, build date |
| `netstat` | Full service enumeration |
| `ps aux` | Full process enumeration |
| Chromium CDP | Browser state, cookies, localStorage, screenshots |

---

## 16. Hardening Assessment

### 16.1 Strengths ✅

1. **Non-root execution** — Container runs as `kimi` (uid 999), not root
2. **SSH key-only auth** — Password authentication disabled
3. **Root login disabled** — `PermitRootLogin no`
4. **K8s RBAC minimal** — Default SA has zero permissions
5. **Kubelet isolated** — Port 10250 unreachable from pod network
6. **Cloud metadata hardened** — 403 on RAM credentials
7. **No outbound internet** — Prevents C2 callbacks, data exfiltration
8. **No Docker socket** — Prevents container escape via Docker
9. **Zero effective capabilities** — Standard container capability dropping
10. **No bash history leakage** — Clean environment
11. **No secrets in home directory** — grep found nothing
12. **Seccomp available** (though currently disabled at process level)
13. **AppArmor/SELinux not needed** — Defense in depth would be nice but not critical

### 16.2 Weaknesses 🔴

1. **Chromium CDP exposed externally** — `socat` on `0.0.0.0:9223` with **no authentication**
   - This is the **most critical vulnerability**
   - Anyone with network access can control the browser completely
   - Can navigate to internal services, execute JS, steal data

2. **VNC password in environment variable** — `VNC_PASSWORD=REDACTED`
   - Password is trivial
   - Exposed to any process in the container
   - VNC itself uses `SecurityTypes None` (no encryption)

3. **Chromium running with `--no-sandbox`** — Disables renderer sandbox
   - Combined with `--single-process`, removes all process isolation
   - Malicious web content could compromise the browser process
   - Since browser runs as `kimi`, not root, impact is limited but still significant

4. **SSH password in env var** — `SSH_PASSWORD=REDACTED`
   - Misleading — not used by sshd (key-only)
   - But could confuse users or be used by other tools

5. **K8s token long-lived** — Expires ~2037
   - If RBAC is ever misconfigured, this token becomes exploitable
   - Should use short-lived tokens or workload identity

6. **X11 forwarding enabled** — `X11Forwarding yes`
   - If SSH is compromised, attacker can tunnel X11 apps
   - Limited impact since no X clients running

7. **No Seccomp filter** — `Seccomp: 0`
   - Process has no seccomp restrictions
   - Syscalls are unrestricted

8. **No AppArmor/SELinux** — No MAC layer
   - Relies solely on standard Unix permissions

---

## 17. Risk Scoring

### CVSS-style Assessment

| Vulnerability | Severity | Vector | Score |
|--------------|----------|--------|-------|
| Unauthenticated Chromium CDP (port 9223) | 🔴 Critical | Network / Low complexity / No auth | 9.8 |
| VNC weak password + no encryption | 🔴 High | Network / Low complexity / Weak creds | 8.1 |
| K8s token exposure (unprivileged) | 🟡 Medium | Local / Info disclosure | 5.3 |
| Environment variable secrets | 🟡 Medium | Local / Info disclosure | 5.3 |
| Chromium no-sandbox | 🟡 Medium | Local / Requires user action | 6.1 |
| X11 forwarding | 🟢 Low | Network / Requires SSH compromise | 3.7 |

---

## 18. Generated Artifacts

| File | Size | Description |
|------|------|-------------|
| `app.zip` | ~3.3 MB | `/app` directory |
| `mnt.zip` | ~100 MB | `/mnt/agents` directory |
| `usr.zip` | ~100 MB | `/usr` directory (truncated) |
| `command.zip` | ~11 MB | `/command` directory |
| `package.zip` | ~11 MB | `/package` directory |
| `etc.zip` | ~72 MB | `/etc` directory |
| `usr_src.zip` | ~14 KB | `/usr/src` (Python 3.11 debug) |
| `var_log.zip` | ~119 KB | `/var/log` directory |
| `var_run.zip` | ~67 KB | `/var/run` directory |
| `ssh.zip` | ~236 bytes | `/home/kimi/.ssh` (authorized_keys) |
| `home_kimi.zip` | ~360 KB | Full `/home/kimi` directory |
| `web_server.py` | ~2.2 KB | Simple HTTP server |
| `summary.md` | ~10 KB | Original summary report |
| `detailed_report.md` | This file | Comprehensive assessment |

---

## 19. Methodology

### 19.1 Reconnaissance Commands

```bash
# System enumeration
whoami, id, groups, uname -a, hostname -f
cat /etc/passwd, cat /etc/group
cat /proc/self/status, cat /proc/1/cmdline
mount, df -h, du -sh

# Network enumeration
ifconfig, netstat -tulnp, ss -tulnp
env, printenv
nslookup, nc, traceroute (where available)
curl, wget

# Process enumeration
ps aux, ps auxf, lsof

# File enumeration
ls -la, find, grep -r
cat, head, tail, file

# Kubernetes
curl with bearer token to K8s API endpoints
kubectl (not available)

# Cloud metadata
curl http://100.100.100.200/latest/meta-data/

# Browser automation
playwright connect_over_cdp
page.goto, page.evaluate, page.screenshot

# Security checks
find / -perm -4000
sysctl -a
capsh --print (not available)
```

### 19.2 Tools Used

| Tool | Purpose |
|------|---------|
| Python 3.12 | Scripting, subprocess execution |
| Playwright | Browser automation, CDP interaction |
| curl | HTTP/HTTPS requests |
| subprocess | Shell command execution |
| zipfile | Archive creation |
| os, stat | Filesystem inspection |

---

## 20. Appendices

### Appendix A: Full Environment Variables

```
CLICOLOR=1
CLICOLOR_FORCE=1
DISPLAY=:99
ECI_CONTAINER_TYPE=normal
FORCE_COLOR=1
GIT_PAGER=cat
GPG_KEY=7169605F62C751356D054A26A821E680E5FA6305
HOME=/home/kimi
HOSTNAME=k2047919835917271047
JPY_PARENT_PID=52
KUBERNETES_PORT=tcp://192.168.0.1:443
KUBERNETES_PORT_443_TCP=tcp://192.168.0.1:443
KUBERNETES_PORT_443_TCP_ADDR=192.168.0.1
KUBERNETES_PORT_443_TCP_PORT=443
KUBERNETES_PORT_443_TCP_PROTO=tcp
KUBERNETES_SERVICE_HOST=apiserver.cefbdaa10ca5a450588268a8fd4f77600.cn-beijing.cs.aliyuncs.com
KUBERNETES_SERVICE_PORT=6443
KUBERNETES_SERVICE_PORT_HTTPS=6443
LANG=C.UTF-8
MPLBACKEND=module://matplotlib_inline.backend_inline
OLDPWD=/run/s6-rc:s6-rc-init:LCobDo/servicedirs/kernel-server
PAGER=cat
PATH=/command:/home/kimi/.local/bin:/home/kimi/.npm-global/bin:/command:/home/kimi/.local/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PIP_CACHE_DIR=/home/kimi/.cache/pip
PIP_INDEX_URL=http://mirrors.cloud.aliyuncs.com/pypi/simple/
PIP_TRUSTED_HOST=mirrors.cloud.aliyuncs.com
PWD=/mnt/agents
PYDEVD_USE_FRAME_EVAL=NO
PYTHONUNBUFFERED=1
PYTHONUSERBASE=/home/kimi/.local
PYTHON_SHA256=fb85a13414b028c49ba18bbd523c2d055a30b56b18b92ce454ea2c51edc656c4
PYTHON_VERSION=3.12.12
S6_LOGGING=0
SCREEN_RESOLUTION=1920x1080
SHLVL=0
SSH_PASSWORD=REDACTED
TERM=xterm-color
TZ=Asia/Shanghai
USE_CDP=1
VNC_PASSWORD=REDACTED
WORKDIR=/mnt/agents
XAUTHORITY=/home/kimi/.Xauthority
```

### Appendix B: K8s API Response Samples

#### /version (200 OK)
```json
{
  "major": "1",
  "minor": "34",
  "gitVersion": "v1.34.3-aliyun.1",
  "gitCommit": "31a9bc4fe672ab35f762aca5c17cd6b581bb01fc",
  "buildDate": "2026-01-06T08:52:17Z",
  "goVersion": "go1.24.6",
  "platform": "linux/amd64"
}
```

#### /api/v1/pods (403 Forbidden)
```json
{
  "kind": "Status",
  "status": "Failure",
  "message": "pods is forbidden: User \"system:serviceaccount:default:default\" cannot list resource \"pods\"",
  "reason": "Forbidden",
  "code": 403
}
```

### Appendix C: Chromium CDP Version Info

```json
{
  "Browser": "Chrome/147.0.7727.55",
  "Protocol-Version": "1.3",
  "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
  "V8-Version": "14.7.14",
  "WebKit-Version": "537.36 (@147.0.7727.55)",
  "webSocketDebuggerUrl": "ws://localhost:9222/devtools/browser/..."
}
```

### Appendix D: SSH Host Key Fingerprints

| Algorithm | Fingerprint (MD5) | Fingerprint (SHA256) |
|-----------|-----------------|---------------------|
| RSA | Not computed | Not computed |
| ECDSA | Not computed | Not computed |
| Ed25519 | Not computed | Not computed |

*(Fingerprints not computed to avoid cryptographic operations on host keys)*

### Appendix E: Capability Decoding

Bounding set `00000000a80425fb` in binary:
```
Bit 0 (CAP_CHOWN):              1
Bit 1 (CAP_DAC_OVERRIDE):       1
Bit 2 (CAP_DAC_READ_SEARCH):    0
Bit 3 (CAP_FOWNER):             1
Bit 4 (CAP_FSETID):             1
Bit 5 (CAP_KILL):               1
Bit 6 (CAP_SETGID):             1
Bit 7 (CAP_SETUID):             1
Bit 8 (CAP_SETPCAP):            1
Bit 9 (CAP_LINUX_IMMUTABLE):    0
Bit 10 (CAP_NET_BIND_SERVICE):  1
Bit 11 (CAP_NET_BROADCAST):   0
Bit 12 (CAP_NET_ADMIN):         0
Bit 13 (CAP_NET_RAW):           1
Bit 14 (CAP_IPC_LOCK):          0
Bit 15 (CAP_IPC_OWNER):         0
Bit 16 (CAP_SYS_MODULE):        0
Bit 17 (CAP_SYS_RAWIO):         0
Bit 18 (CAP_SYS_CHROOT):        1
Bit 19 (CAP_SYS_PTRACE):        0
Bit 20 (CAP_SYS_PACCT):         0
Bit 21 (CAP_SYS_ADMIN):         0  ← CRITICAL: Not present
Bit 22 (CAP_SYS_BOOT):          0
Bit 23 (CAP_SYS_NICE):          0
Bit 24 (CAP_SYS_RESOURCE):      0
Bit 25 (CAP_SYS_TIME):          0
Bit 26 (CAP_SYS_TTY_CONFIG):    0
Bit 27 (CAP_MKNOD):             1
Bit 28 (CAP_LEASE):             0
Bit 29 (CAP_AUDIT_WRITE):       1
Bit 30 (CAP_AUDIT_CONTROL):     0
Bit 31 (CAP_SETFCAP):           1
```

**Key absence:** `CAP_SYS_ADMIN` is NOT in the bounding set — this prevents many container escape techniques.

---

## Conclusion

This container represents a **moderately well-hardened** but **not fully secured** environment. The critical risks are:

1. **Unauthenticated Chromium CDP exposure** (port 9223) — Immediate remediation required
2. **Weak VNC password** — Should be rotated to strong credential
3. **Chromium sandbox disabled** — Acceptable for testing, risky for production

The infrastructure-level controls (K8s RBAC, network isolation, metadata service hardening) are properly implemented. The remaining risks are primarily at the application/service configuration layer.

---

*Report generated by automated reconnaissance via Python subprocess, file I/O, and Playwright browser automation.*
*Container: k2047919835917271047 | Date: 2026-04-25 | Assessment type: White-box container review*
