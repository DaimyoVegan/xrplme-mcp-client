#!/usr/bin/env python3
"""
XRPLME premium routes — x402 payment flow example (MCP surface).

The MCP endpoint reports payment requirements *in-band*: an unpaid premium call
returns a normal JSON-RPC result whose tool output is a `payment_required`
object carrying the price on both rails. You settle in XRP on the XRP Ledger,
then resubmit the same call with proof of payment passed as tool arguments.

    tool call  ->  payment_required  ->  pay XRP  ->  retry with
                   x_payment_signature + x_inv_id  ->  data

    export XRPLME_WALLET_SEED="s...."                  # YOUR wallet. Never commit.
    python x402_payment.py

Tiers (see xrplme_get_pricing):
    standard     1 XRP   / $1.00 USDC
    AI-enhanced  5 XRP   / $7.00 USDC

The separate REST surface (/wc/v1/<slug>/bot) returns a real HTTP 402 with an
`accepts[]` challenge instead — see demo_xrplme_paid.py for that path.

Requires:  pip install xrpl-py requests

SECURITY
--------
This script reads YOUR wallet seed from the environment so it can sign a payment.
It never prints, logs, or transmits the seed. In production, prefer a dedicated,
low-balance hot wallet, and keep the seed in a 0600 env file or a signer service —
never in shell history or source control.
"""
import os
import json
import requests

MCP_URL = os.environ.get("XRPLME_MCP_URL", "https://api.xrplme.online/mcp")
SLUG = os.environ.get("XRPLME_SLUG", "thailand")

# The MCP server speaks streamable HTTP: it answers with SSE frames unless it
# knows the client accepts plain JSON. Without this header every response comes
# back as "event: message\\ndata: {...}" and .json() fails.
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def parse_mcp(resp: requests.Response) -> dict:
    """Decode an MCP response that may be plain JSON or SSE-framed."""
    text = resp.text.strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            if payload:
                return json.loads(payload)
    raise RuntimeError(f"unparseable MCP response: {text[:200]}")


def call_tool(name: str, arguments: dict) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": arguments}}


def discover_price() -> dict:
    """Pricing is free to look up — no payment, no upstream call."""
    r = requests.post(MCP_URL, headers=HEADERS,
                      json=call_tool("xrplme_get_pricing", {"slug": SLUG}),
                      timeout=30)
    r.raise_for_status()
    return parse_mcp(r)


def call_premium_route(payment_signature: str | None = None,
                       invoice_id: str | None = None) -> dict:
    args = {"slug": SLUG, "tier": "premium"}
    if payment_signature:
        args["x_payment_signature"] = payment_signature
    if invoice_id:
        args["x_inv_id"] = invoice_id
    r = requests.post(MCP_URL, headers=HEADERS,
                      json=call_tool("xrplme_get_country_data", args),
                      timeout=60)
    r.raise_for_status()
    return parse_mcp(r)


def extract_payment_challenge(result: dict) -> dict | None:
    """Pull the payment_required object out of a tool result, if present."""
    content = (result.get("result") or {}).get("content") or []
    if not content:
        return None
    text = content[0].get("text", "")
    start = text.find("{")
    if start == -1:
        return None
    try:
        inner = json.loads(text[start:])
    except json.JSONDecodeError:
        return None
    if isinstance(inner, dict) and inner.get("error") == "payment_required":
        return inner
    return None


def sign_payment(seed: str, destination: str, drops: int, invoice_id: str) -> str:
    """Submit an XRPL Payment and return a proof string for x_payment_signature.

    Uses the invoice id as the XRPL InvoiceID so the payment is bound to this
    specific query and cannot be replayed against a different one.
    """
    from xrpl.clients import JsonRpcClient
    from xrpl.wallet import Wallet
    from xrpl.models.transactions import Payment
    from xrpl.transaction import submit_and_wait

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
    print(f"1. discovering price for {SLUG} ...")
    print("   ", json.dumps(discover_price())[:300])

    print("\n2. calling the premium route unpaid (expect payment_required) ...")
    result = call_premium_route()
    challenge = extract_payment_challenge(result)
    if challenge is None:
        print("    (no payment required — free tier, or the call succeeded)")
        print("   ", json.dumps(result)[:400])
        return

    pricing = challenge.get("pricing") or {}
    drops = int(pricing.get("drops", 0))
    print(f"    price={pricing.get('xrp')} XRP ({drops} drops) "
          f"| {pricing.get('usdc')} USDC on Solana")
    print(f"    message: {challenge.get('message')}")

    pay_to = os.environ.get("XRPLME_PAY_TO")
    invoice_id = os.environ.get("XRPLME_INV_ID")
    if not pay_to or not invoice_id:
        print("\n   The XRPL destination and invoice id for this query are issued")
        print("   per-request by the REST surface (/wc/v1/<slug>/bot), which returns")
        print("   them in accepts[0].payTo and accepts[0].extra.invoiceId.")
        print("   Run demo_xrplme_paid.py for the full end-to-end paid flow.")
        return

    seed = os.environ.get("XRPLME_WALLET_SEED")
    if not seed:
        print("\n   Set XRPLME_WALLET_SEED to complete the payment automatically.")
        return

    print(f"\n3. paying {drops} drops to {pay_to} ...")
    signature = sign_payment(seed, pay_to, drops, invoice_id)
    print(f"    settled, XRPL tx = {signature}")

    print("\n4. retrying with proof of payment ...")
    final = call_premium_route(signature, invoice_id)
    print("   ", json.dumps(final)[:600])


if __name__ == "__main__":
    main()
