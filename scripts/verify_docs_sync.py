#!/usr/bin/env python3
"""
Verify this repo's public docs still describe the LIVE xrplme.online surface.

Run this before every commit that touches the platform (new countries, pricing,
tool changes, endpoint moves) and as the last step of any country-add or
feature-deploy checklist:

    python3 scripts/verify_docs_sync.py

Exit 0 = docs match live. Exit 1 = drift, with one line per mismatch telling you
exactly which README claim is wrong and what the live value is.

Read-only and unpaid: it only calls the free discovery surface (tools/list,
xrplme_list_countries, xrplme_get_pricing) plus one unpaid premium call to
confirm the payment challenge shape. It never pays, never writes, never deploys.

Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

MCP_URL = os.environ.get("XRPLME_MCP_URL", "https://api.xrplme.online/mcp")
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(REPO_ROOT, "README.md")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    # Cloudflare fronts the api host and returns 403 to the default
    # python-urllib User-Agent. A browser UA is required for any scripted probe.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}

failures: list[str] = []
notes: list[str] = []


def _post(payload: dict, timeout: int = 45) -> dict:
    req = urllib.request.Request(
        MCP_URL, data=json.dumps(payload).encode(), headers=HEADERS, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = r.read().decode()
    return _decode(text)


def _decode(text: str) -> dict:
    """MCP answers with SSE frames unless it believes the client takes JSON."""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload:
                return json.loads(payload)
    raise RuntimeError(f"unparseable MCP response: {text[:200]}")


def _tool_text(result: dict) -> str:
    content = (result.get("result") or {}).get("content") or []
    return content[0].get("text", "") if content else ""


def _tool_json(result: dict) -> dict:
    text = _tool_text(result)
    return json.loads(text[text.find("{"):])


def live_facts() -> dict:
    tools = _post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in tools["result"]["tools"]]

    countries = _tool_json(
        _post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
               "params": {"name": "xrplme_list_countries", "arguments": {}}})
    )["countries"]

    pricing = _tool_json(
        _post({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
               "params": {"name": "xrplme_get_pricing", "arguments": {}}})
    )["pricing"]

    # One unpaid premium call: proves the challenge shape still matches the docs.
    premium = _post({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                     "params": {"name": "xrplme_get_country_data",
                                "arguments": {"slug": countries[0]["slug"]}}})
    challenge = None
    text = _tool_text(premium)
    if "{" in text:
        try:
            inner = json.loads(text[text.find("{"):])
            if inner.get("error") == "payment_required":
                challenge = inner
        except json.JSONDecodeError:
            pass

    return {
        "tools": names,
        "country_count": len(countries),
        "slugs": [c["slug"] for c in countries],
        "standard_xrp": pricing["standard"]["xrp"],
        "ai_xrp": pricing["ai"]["xrp"],
        "standard_usdc": pricing["standard"]["usdc"],
        "ai_usdc": pricing["ai"]["usdc"],
        "challenge": challenge,
    }


def check(readme: str, live: dict) -> None:
    n = live["country_count"]

    # --- coverage -----------------------------------------------------------
    m = re.search(r"\*\*Coverage:\*\*\s*(\d+)\s+countries", readme)
    if not m:
        failures.append("README: no '**Coverage:** N countries' line found")
    elif int(m.group(1)) != n:
        failures.append(f"coverage: README says {m.group(1)} countries, live = {n}")

    for pattern, label in (
        (rf"\b({n})-country\b", f"intro must say '{n}-country'"),
        (rf"The {n} supported country slugs", f"resources table must say '{n}'"),
        (rf"Enumerate the (\d+) slugs", None),
        (rf"^(\d+) countries across", None),
    ):
        if pattern.endswith(r"(\d+) slugs"):
            mm = re.search(r"Enumerate the (\d+) slugs", readme, re.M)
            if not mm:
                failures.append("README: 'Enumerate the N slugs' row missing")
            elif int(mm.group(1)) != n:
                failures.append(f"tools table: says '{mm.group(1)} slugs', live = {n}")
        elif pattern.endswith(r"countries across"):
            mm = re.search(r"^(\d+) countries across", readme, re.M)
            if not mm:
                failures.append("README: 'N countries across' line missing")
            elif int(mm.group(1)) != n:
                failures.append(f"data coverage: says '{mm.group(1)} countries', live = {n}")

    # --- tools --------------------------------------------------------------
    m = re.search(r"\*\*Tools\*\*\s*\((\d+),", readme)
    if not m:
        failures.append("README: no '**Tools** (N, ...)' line found")
    elif int(m.group(1)) != len(live["tools"]):
        failures.append(f"tool count: README says {m.group(1)}, live = {len(live['tools'])}")

    for name in live["tools"]:
        if name not in readme:
            failures.append(f"undocumented tool in README: {name}")
    for documented in set(re.findall(r"`(xrplme_[a-z_]+)`", readme)):
        if documented not in live["tools"]:
            failures.append(f"README documents a tool that is NOT live: {documented}")

    # --- pricing ------------------------------------------------------------
    m = re.search(r"\*\*Premium:\*\*([^\n]+)", readme)
    if not m:
        failures.append("README: no '**Premium:**' line found")
    else:
        line = m.group(1)
        if str(live["standard_xrp"]) not in line:
            failures.append(
                f"pricing: standard tier is {live['standard_xrp']} XRP live, absent from Premium line")
        if str(live["ai_xrp"]) not in line:
            failures.append(
                f"pricing: AI tier is {live['ai_xrp']} XRP live, absent from Premium line")

    # Stale per-query price shapes that have burned this repo before.
    for stale in ("0.1–0.5 XRP", "0.1-0.5 XRP", "pay 0.1 XRP"):
        if stale in readme:
            failures.append(f"pricing: stale literal still present: '{stale}'")

    # --- payment challenge shape -------------------------------------------
    challenge = live["challenge"]
    if challenge is None:
        failures.append(
            "payment: unpaid premium call did not return payment_required "
            "(docs describe an in-band challenge)")
    else:
        drops = str((challenge.get("pricing") or {}).get("drops"))
        if drops and drops not in readme:
            notes.append(
                f"premium tier = {drops} drops ({challenge['pricing'].get('xrp')} XRP); "
                "README does not quote the drop count (fine, tiers are quoted in XRP)")

    # --- git: is the synced content actually pushed? ------------------------
    try:
        dirty = subprocess.run(["git", "-C", REPO_ROOT, "status", "--porcelain"],
                               capture_output=True, text=True, timeout=20).stdout.strip()
        if dirty:
            failures.append("git: working tree is dirty — commit the doc sync")
        ahead = subprocess.run(
            ["git", "-C", REPO_ROOT, "rev-list", "--count", "origin/master..HEAD"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        if ahead and ahead.isdigit() and int(ahead) > 0:
            failures.append(f"git: {ahead} commit(s) not pushed — the update is not public yet")
    except Exception as exc:  # noqa: BLE001 - git is best-effort here
        notes.append(f"git check skipped ({exc})")


def main() -> int:
    if not os.path.exists(README):
        print(f"FAIL  README not found at {README}", file=sys.stderr)
        return 1
    readme = open(README, encoding="utf-8").read()

    try:
        live = live_facts()
    except Exception as exc:  # noqa: BLE001 - report, never traceback
        print(f"FAIL  could not read live surface: {exc}", file=sys.stderr)
        return 1

    check(readme, live)

    print(f"live: {live['country_count']} countries, {len(live['tools'])} tools, "
          f"standard {live['standard_xrp']} XRP / AI {live['ai_xrp']} XRP")
    for note in notes:
        print(f"NOTE  {note}")

    if failures:
        print()
        for f in failures:
            print(f"FAIL  {f}")
        print(f"\n{len(failures)} drift(s). Update README.md, then re-run.")
        return 1

    print("PASS  README matches the live surface.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
