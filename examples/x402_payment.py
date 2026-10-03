#!/usr/bin/env python3
"""
XRPLME premium routes — x402 payment flow example.

x402 is HTTP-native pay-per-query: the server answers 402 Payment Required with
pricing headers, you settle in XRP on the XRP Ledger, then retry the request with
proof of payment. No accounts, no subscription.

    402  ->  pay XRP  ->  retry with X-PAYMENT-SIGNATURE + X-INV-ID  ->  200

    export XRPLME_MCP_TOKEN="your-discovery-token"     # free tier, for discovery
    export XRPLME_WALLET_SEED="s...."                  # YOUR wallet. Never commit.
    python x402_payment.py

Requires:  pip install xrpl-py requests

SECURITY
--------
This script reads YOUR wallet seed from the environment so it can sign a payment.
It never prints, logs, or transmits the seed. In production, prefer a dedicated,
low-balance hot wallet, and keep the seed in a 0600 env file or a signer service —
never in shell history or source control.
"""
import os
import sys
import json
import requests

MCP_URL = os.environ.get("XRPLME_MCP_URL", "https://api.xrplme.online/mcp")
TOKEN = os.environ.get("XRPLME_MCP_TOKEN", "")
SLUG = os.environ.get("XRPLME_SLUG", "thailand")


def discover_price() -> dict:
    """Pricing is free to look up — no payment, no upstream call."""
    r = requests.post(
        MCP_URL,
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/json"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "xrplme_get_country_pricing",
                         "arguments": {"slug": SLUG}}},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def call_premium_route(payment_signature: str | None = None,
                       invoice_id: str | None = None) -> requests.Response:
    headers = {"Authorization": f"Bearer {TOKEN}",
               "Content-Type": "application/json"}
    if payment_signature:
        headers["X-PAYMENT-SIGNATURE"] = payment_signature
    if invoice_id:
        headers["X-INV-ID"] = invoice_id
    return requests.post(
        MCP_URL, headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "xrplme_get_country_data",
                         "arguments": {"slug": SLUG, "tier": "premium"}}},
        timeout=30,
    )


def sign_payment(seed: str, destination: str, drops: int, invoice_id: str) -> str:
    """Submit an XRPL Payment and return a proof string for X-PAYMENT-SIGNATURE.

    Uses the invoice id as the XRPL InvoiceID so the payment is bound to this
    specific query and cannot be replayed against a different one.
    """
    from xrpl.clients import JsonRpcClient
    from xrpl.wallet import Wallet
    from xrpl.models.transactions import Payment
    from xrpl.transaction import submit_and_wait
    from xrpl.utils import drops_to_xrp

    client = JsonRpcClient("https://xrplcluster.com")
    wallet = Wallet.from_seed(seed)          # never printed
    tx = Payment(
        account=wallet.classic_address,
        destination=destination,
        amount=str(drops),
        invoice_id=invoice_id,
    )
    resp = submit_and_wait(tx, client, wallet)
    return resp.result["hash"]


def main() -> None:
    if not TOKEN:
        sys.exit("Set XRPLME_MCP_TOKEN first.")

    print(f"1. discovering price for {SLUG} ...")
    print("   ", json.dumps(discover_price())[:300])

    print("\n2. requesting the premium route (expect 402) ...")
    resp = call_premium_route()
    print("    HTTP", resp.status_code)
    if resp.status_code != 402:
        print("    (not gated here — discovery tier or already paid)")
        print("   ", resp.text[:300])
        return

    price = resp.headers.get("X402-Price")
    asset = resp.headers.get("X402-Asset")
    pay_to = resp.headers.get("X402-Payment-Address")
    invoice_id = resp.headers.get("X-INV-ID") or resp.headers.get("X402-Invoice-Id")

    def to_drops(p):
        """Accept '0.1' XRP or '100000' drops."""
        p = str(p)
        return int(p) if p.isdigit() and len(p) > 6 else int(float(p) * 1_000_000)

    drops = to_drops(price)
    print(f"    price={price} asset={asset} pay_to={pay_to}")

    seed = os.environ.get("XRPLME_WALLET_SEED")
    if not seed:
        print("\n   Set XRPLME_WALLET_SEED to complete the payment automatically.")
        print("   Or pay manually and retry with the two headers.")
        return

    print(f"\n3. paying {drops} drops to {pay_to} ...")
    signature = sign_payment(seed, pay_to, drops, invoice_id)
    print(f"    settled, XRPL tx = {signature}")

    print("\n4. retrying with proof of payment ...")
    final = call_premium_route(signature, invoice_id)
    print("    HTTP", final.status_code)
    print("   ", final.text[:600])


if __name__ == "__main__":
    main()
