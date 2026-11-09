#!/usr/bin/env python3
"""Pay an xrplme.online country query with USDC on Base. Standard library only.

The RailBase flow is three steps and this script does all of them:

  1. POST the route with no payment  -> 402 challenge (payTo, amount, chain)
  2. send that much USDC on Base to payTo from any wallet  (done by you)
  3. POST again with {"txHash": "0x..."} in PAYMENT-SIGNATURE -> 200 + data

Usage
-----
  # what do I have to pay?
  python3 x402_payment_base.py --country thailand

  # attach a transfer you already sent
  python3 x402_payment_base.py --country thailand --tx 0xabc...

  # rehearse on Base Sepolia (test USDC, returns a receipt, no records)
  python3 x402_payment_base.py --country thailand --test --tx 0xabc...

Tiers: --tier std (default) | ai | custom
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

BASE = "https://xrplme.online/wc/v1"
UA = "xrplme-base-example/1.0 (+https://xrplme.online)"


def route(country: str, tier: str, test: bool) -> str:
    suffix = "bot-evm-test" if test else "bot-evm"
    if tier == "ai":
        suffix += "/ai"
    elif tier == "custom":
        suffix += "/custom"
    return f"{BASE}/{country}/{suffix}"


def post(url: str, body: dict, payment_header: str | None = None) -> tuple[int, dict, dict]:
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": UA}
    if payment_header:
        headers["PAYMENT-SIGNATURE"] = payment_header
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw[:400]}
        return e.code, dict(e.headers), payload


def money(micro: str, decimals: int = 6) -> str:
    return f"{int(micro) / 10 ** decimals:.{decimals}f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--country", default="thailand", help="country slug (default: thailand)")
    ap.add_argument("--tier", default="std", choices=["std", "ai", "custom"], help="pricing tier")
    ap.add_argument("--message", default="recent policy changes", help="your question")
    ap.add_argument("--tx", help="Base transaction hash of your USDC transfer to payTo")
    ap.add_argument("--test", action="store_true", help="use the Base Sepolia rehearsal rail")
    args = ap.parse_args()

    url = route(args.country, args.tier, args.test)
    print(f"route: {url}\n")

    status, _, body = post(url, {"message": args.message})
    if status != 402:
        print(f"expected a 402 challenge, got {status}: {json.dumps(body)[:300]}")
        return 1

    accept = (body.get("accepts") or [{}])[0]
    pay_to = accept.get("payTo", "?")
    amount = accept.get("amount", "0")
    network = accept.get("network", "?")
    asset = accept.get("asset", "?")
    qr = accept.get("qrData", "")

    print("payment required")
    print(f"  network : {network}")
    print(f"  asset   : {asset}")
    print(f"  amount  : {money(amount)}  ({amount} micro-USDC)")
    print(f"  payTo   : {pay_to}")
    if accept.get("extra", {}).get("testnet"):
        print("  testnet : yes - payment is verified, no country records are returned")
    if qr:
        print(f"  pay URI : {qr}")

    if not args.tx:
        print("\nSend the amount above as USDC on this network to payTo, then re-run with --tx <hash>.")
        return 0

    print(f"\nattaching transaction: {args.tx}")
    status, _, body = post(url, {"message": args.message},
                           payment_header=json.dumps({"txHash": args.tx}))

    if status == 200:
        print(f"\n200 OK")
        if "status" in body and body.get("status") == "payment_verified":
            print(json.dumps(body, indent=2))
        else:
            print(body.get("response", json.dumps(body)[:800]))
            print(f"\nsession_id: {body.get('session_id', '-')}")
        return 0

    print(f"\n{status}: {json.dumps(body)[:400]}")
    if status == 409:
        print("that transaction was already used - one transfer buys one call.")
    elif status == 402:
        print("payment not accepted (wrong token, recipient, amount, or too old).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
