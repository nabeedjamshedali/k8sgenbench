"""Download pinned Windows binaries of the evaluation tools into tools/bin.

Usage: python tools/install_tools.py            # latest releases, writes tools/versions.lock
       python tools/install_tools.py --locked   # reinstall exactly the versions in versions.lock
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(ROOT, "bin")
LOCK = os.path.join(ROOT, "versions.lock")

# name -> (GitHub repo, regex selecting the Windows amd64 asset, executable name inside it)
TOOLS = {
    "kind": ("kubernetes-sigs/kind", r"^kind-windows-amd64$", "kind.exe"),
    "kubeconform": ("yannh/kubeconform", r"windows-amd64\.zip$", "kubeconform.exe"),
    "kubescape": ("kubescape/kubescape", r"^kubescape(_[\d.]+)?_windows(-latest)?_amd64\.exe$|^kubescape-windows-latest$|^kubescape_windows.*amd64.*\.exe$", "kubescape.exe"),
    "trivy": ("aquasecurity/trivy", r"windows-64bit\.zip$", "trivy.exe"),
    "kube-score": ("zegl/kube-score", r"windows_amd64(\.exe|\.tar\.gz|\.zip)$", "kube-score.exe"),
    "polaris": ("FairwindsOps/polaris", r"windows_amd64\.(tar\.gz|zip)$", "polaris.exe"),
    "kube-linter": ("stackrox/kube-linter", r"^kube-linter(-windows)?(\.exe|\.zip)$|windows.*amd64.*(\.exe|\.zip)$", "kube-linter.exe"),
}


def curl(url, out=None):
    cmd = ["curl", "-sSL", "-A", "Mozilla/5.0", "-H", "Accept: application/vnd.github+json", url]
    if out:
        cmd += ["-o", out]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode:
        raise RuntimeError(res.stderr.decode(errors="ignore"))
    return res.stdout


def release(repo, tag=None):
    url = f"https://api.github.com/repos/{repo}/releases/" + (f"tags/{tag}" if tag else "latest")
    return json.loads(curl(url))


def extract(path, exe_name):
    target = os.path.join(BIN, exe_name)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            member = next(m for m in z.namelist() if m.lower().endswith(".exe"))
            with z.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as t:
            member = next(m for m in t.getmembers() if m.name.lower().endswith(".exe"))
            with t.extractfile(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
    else:
        shutil.move(path, target)
    return target


def main():
    os.makedirs(BIN, exist_ok=True)
    locked = {}
    if "--locked" in sys.argv:
        locked = dict(line.split("=", 1) for line in open(LOCK).read().split() if "=" in line)
    lock_lines = []
    for name, (repo, pattern, exe) in TOOLS.items():
        rel = release(repo, locked.get(name))
        asset = next((a for a in rel["assets"] if re.search(pattern, a["name"])), None)
        if not asset:
            print(f"{name}: no Windows asset matched in {rel['tag_name']}: {[a['name'] for a in rel['assets']]}")
            continue
        tmp = os.path.join(BIN, asset["name"] + ".download")
        curl(asset["browser_download_url"], tmp)
        extract(tmp, exe)
        if os.path.exists(tmp):
            os.remove(tmp)
        lock_lines.append(f"{name}={rel['tag_name']}")
        print(f"{name:12} {rel['tag_name']:12} <- {asset['name']}")
    kubectl_version = locked.get("kubectl") or curl("https://dl.k8s.io/release/stable.txt").decode().strip()
    curl(f"https://dl.k8s.io/release/{kubectl_version}/bin/windows/amd64/kubectl.exe", os.path.join(BIN, "kubectl.exe"))
    lock_lines.append(f"kubectl={kubectl_version}")
    print(f"{'kubectl':12} {kubectl_version}")
    if "--locked" not in sys.argv:
        with open(LOCK, "w") as f:
            f.write("\n".join(lock_lines) + "\n")


if __name__ == "__main__":
    main()
