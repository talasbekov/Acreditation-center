"""Этап E: аудит зависимостей через OSV (https://osv.dev) по закреплённым версиям.

Источники: requirements.txt, requirements-dev.txt (PyPI) и frontend/package-lock.json (npm).
Наружу уходят только пары «пакет, версия». Результат — JSON в OSV_OUT (или в stdout).
Запуск из Acreditation-center-main: python scripts/stage_e/osv_audit.py
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "https://api.osv.dev/v1"


def pypi(path, scope):
    pins = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?==([^\s;\\]+)", line)
        if m:
            pins.append(("PyPI", m.group(1).lower().replace("_", "-"), m.group(2), scope))
    return pins


def npm(path):
    lock = json.loads(path.read_text(encoding="utf-8"))
    pins = set()
    for key, meta in lock.get("packages", {}).items():
        if not key.startswith("node_modules/") or "version" not in meta:
            continue
        name = key.split("node_modules/")[-1]
        scope = "npm-dev" if meta.get("dev") else "npm-prod"
        pins.add(("npm", name, meta["version"], scope))
    return sorted(pins)


def post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json",
                                                                                    "User-Agent": "osv-audit-script"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "osv-audit-script"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def main():
    pins = (pypi(ROOT / "requirements.txt", "python-runtime") + pypi(ROOT / "requirements-dev.txt", "python-dev")
            + npm(ROOT / "frontend" / "package-lock.json"))
    seen, unique = set(), []
    for eco, name, ver, scope in pins:
        if (eco, name, ver) in seen:
            continue
        seen.add((eco, name, ver))
        unique.append((eco, name, ver, scope))
    hits = []
    for start in range(0, len(unique), 500):
        chunk = unique[start:start + 500]
        res = post(f"{API}/querybatch", {"queries": [{"package": {"ecosystem": e, "name": n}, "version": v} for e, n, v, _ in chunk]})
        for (eco, name, ver, scope), r in zip(chunk, res["results"]):
            for v in r.get("vulns", []):
                hits.append({"ecosystem": eco, "package": name, "version": ver, "scope": scope, "id": v["id"]})
    details = {}
    for vid in sorted({h["id"] for h in hits}):
        d = get(f"{API}/vulns/{vid}")
        fixed = sorted({e["fixed"] for a in d.get("affected", []) for r in a.get("ranges", []) for e in r.get("events", []) if "fixed" in e})
        sev = d.get("database_specific", {}).get("severity") or ";".join(s.get("score", "") for s in d.get("severity", []))
        details[vid] = {"summary": d.get("summary", "")[:200], "aliases": d.get("aliases", []), "severity": sev,
                        "fixed": fixed, "published": d.get("published", "")}
    for h in hits:
        h.update(details[h["id"]])
    out = {"checked": len(unique), "by_scope": {s: sum(1 for u in unique if u[3] == s) for s in sorted({u[3] for u in unique})},
           "hits": hits}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if os.environ.get("OSV_OUT"):
        Path(os.environ["OSV_OUT"]).write_text(text, encoding="utf-8")
    print(json.dumps({"checked": out["checked"], "by_scope": out["by_scope"], "hits": len(hits)}, ensure_ascii=False))
    for h in hits:
        print(f'{h["scope"]:15} {h["package"]}=={h["version"]}  {h["id"]}  sev={h["severity"]}  fixed={h["fixed"]}  {h["summary"][:90]}')


if __name__ == "__main__":
    sys.exit(main())
