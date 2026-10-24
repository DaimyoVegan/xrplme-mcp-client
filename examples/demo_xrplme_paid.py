#!/usr/bin/env python3
"""
xrplme.online paid data demo
============================

Pays real 1 XRP (or $1 USDC) on-chain, gets back structured v1.1 JSON
with sources, facts, synthesis, and the transaction ID as proof.

Usage:
    python3 demo_xrplme_paid.py            # XRPL, standard tier (1 XRP)
    python3 demo_xrplme_paid.py --ai       # XRPL, AI tier (5 XRP)
    python3 demo_xrplme_paid.py --solana   # Solana, standard tier ($1 USDC)

Requirements: pip install requests

Author: xrplme.online (builder voice, no hype)
"""

import argparse
import json
import sys
import time

import requests

BASE_URL = "https://xrplme.online"
HEADERS = {"Content-Type": "application/json"}

def get_paid_url(country_slug: str, ai: bool, solana: bool) -> str:
    """Build the correct paid endpoint URL."""
    if solana:
        suffix = "/bot-solana/ai" if ai else "/bot-solana"
    else:
        suffix = "/bot/ai" if ai else "/bot"
    return f"{BASE_URL}/wc/v1/{country_slug}{suffix}"


def step1_get_402(url: str, session_id: str) -> dict:
    """Hit the paid endpoint and extract the 402 payment challenge."""
    payload = {"message": "visa requirements and company formation for a digital nomad", "session_id": session_id}
    resp = requests.post(url, json=payload, headers=HEADERS, timeout=15)

    if resp.status_code != 402:
        print(f"Unexpected status {resp.status_code}")
        print(resp.text[:500])
        sys.exit(1)

    # x402 v2 payment challenge — parse the accepts array
    body = resp.json()
    accepts = body.get("accepts", [])

    if not accepts:
        # Fallback: some responses put details in headers
        print("402 received but no 'accepts' in body.")
        print("Check response headers manually:")
        for k, v in resp.headers.items():
            if "payment" in k.lower() or "inv" in k.lower() or "amount" in k.lower():
                print(f"  {k}: {v}")
        sys.exit(1)

    # Show the first rail's details
    rail = accepts[0]
    print(f"\n  Invoice ID : {rail.get('extra', {}).get('invoiceId', 'N/A')}")
    amount_drops = int(rail.get("amount", 0))
    asset = rail.get("asset", "XRP")
    pay_to = rail.get("payTo", "N/A")
    qr = rail.get("qrData", "N/A")

    if asset == "XRP":
        print(f"  Amount     : {amount_drops / 1_000_000:.1f} XRP ({amount_drops} drops)")
    else:
        print(f"  Amount     : {amount_drops / 1_000_000:.2f} {asset} ({amount_drops} atoms)")

    print(f"  Pay to     : {pay_to}")
    print(f"  QR (scan)  : {qr}")

    invoice_id = rail.get("extra", {}).get("invoiceId", "")
    return {
        "invoice_id": invoice_id,
        "amount": rail.get("amount"),
        "asset": asset,
        "pay_to": pay_to,
        "qr_data": qr,
    }


def step2_get_signature(challenge: dict) -> str:
    """Ask the user to pay and paste the signed transaction blob."""
    print("\n  Open Xaman / Crossmark / Joey wallet")
    print("  Send the exact amount from the QR code")
    print("  Copy the signed transaction blob (hex string)")
    sig = input("\n  Signed tx blob: ").strip()
    if not sig:
        print("  No signature provided — aborting.")
        sys.exit(1)
    return sig


def step3_retry_with_payment(url: str, session_id: str, signature: str) -> dict:
    """Resubmit the request with payment proof to get the 200 response."""
    payload = {"message": "visa requirements and company formation for a digital nomad", "session_id": session_id}
    headers = {**HEADERS, "X-PAYMENT-SIGNATURE": signature}
    resp = requests.post(url, json=payload, headers=headers, timeout=30)

    if resp.status_code != 200:
        print(f"\nRetry failed: {resp.status_code}")
        print(resp.text[:500])
        sys.exit(1)

    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="xrplme online paid data demo")
    parser.add_argument("--country", default="thailand", help="Country slug (default: thailand)")
    parser.add_argument("--ai", action="store_true", help="Use AI-enhanced tier")
    parser.add_argument("--solana", action="store_true", help="Use Solana rail instead of XRPL")
    args = parser.parse_args()

    url = get_paid_url(args.country, args.ai, args.solana)
    session_id = f"demo-{args.country}-{int(time.time())}"

    print(f"=== xrplme paid demo ===")
    print(f"Country: {args.country}")
    print(f"Rail:    {'Solana USDC' if args.solana else 'XRPL XRP'}")
    print(f"Tier:    {'AI-enhanced' if args.ai else 'Standard'}")
    print(f"URL:     {url}")

    # Step 1: Get 402 challenge
    print("\nStep 1: Requesting data (expect 402)...")
    challenge = step1_get_402(url, session_id)

    # Step 2: Pay
    print("\nStep 2: Pay with your wallet...")
    signature = step2_get_signature(challenge)

    # Step 3: Retry with payment
    print("\nStep 3: Submitting payment proof...")
    response = step3_retry_with_payment(url, session_id, signature)

    # Extract v1.1 structured response
    v1 = response.get("v1") or response
    meta = v1.get("meta", {})
    payment = meta.get("payment", {})

    print("\n=== PAYMENT VERIFIED ===")
    print(f"  TXID       : {payment.get('txid', 'N/A')}")
    print(f"  Amount     : {payment.get('amount', 'N/A')}")
    print(f"  Rail       : {payment.get('rail', 'N/A')}")

    sources = v1.get("sources", [])
    synth = v1.get("synthesis", {})
    print(f"  Sources    : {len(sources)} verified source(s)")
    print(f"  Confidence : {synth.get('confidence_overall', 'N/A')}")

    summary = synth.get("summary", "")
    if summary:
        print(f"\n  Summary:\n  {summary[:300]}...")

    # On-chain proof link
    txid = payment.get("txid")
    if txid and payment.get("rail") == "xrpl":
        print(f"\n  Block explorer: https://livenet.xrpl.org/transactions/{txid}")
    elif txid and payment.get("rail") == "solana":
        print(f"\n  Explorer: https://solscan.io/tx/{txid}")

    # Save receipt
    receipt_file = f"receipt_{args.country}_{int(time.time())}.json"
    with open(receipt_file, "w") as f:
        json.dump(response, f, indent=2)
    print(f"\n  Full response saved to: {receipt_file}")
    print("\nDone. You just paid for real country data with on-chain proof.")


if __name__ == "__main__":
    main()
