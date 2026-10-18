#!/usr/bin/env python3
"""
XRPLME premium routes — Solana USDC x402 payment flow example.

Works for both the MCP server (https://api.xrplme.online/mcp) and the
country bot API (https://xrplme.online/wc/v1/<country>/bot-solana).

x402 is HTTP-native pay-per-query: the server answers 402 Payment Required with
pricing headers and a Solana facilitator fee payer, you construct and partially
sign a Solana transaction, then retry with proof-of-payment:

    402  ->  partial_sign tx (ComputeBudget + TransferChecked)  ->  retry with X-PAYMENT-SIGNATURE  ->  200

The facilitator signs with its own fee payer key and simulates the transaction
on-chain for verification.

    export SOLANA_TEST_SECRET_JSON='[...]'          # your USDC wallet keypair JSON
    python x402_payment_solana.py

Requires:
    pip install xrpl requests solders solana-py spl-token

SECURITY
--------
This script reads YOUR wallet secret from the environment so it can sign a
payment. It never prints, logs, or transmits the seed. In production, prefer a
dedicated, low-balance hot wallet, and keep the seed in a 0600 env file or a
signer service — never in shell history or source control.
"""
import os
import json
import base64
import urllib.request
import urllib.error
import sys

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.message import Message
from solders.transaction import Transaction
from solders.instruction import Instruction
from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import (
    get_associated_token_address,
    transfer_checked,
    TransferCheckedParams,
)
from x402.mechanisms.svm.constants import COMPUTE_BUDGET_PROGRAM_ADDRESS

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

# MCP server endpoint (JSON-RPC over HTTP)
MCP_URL = os.environ.get("XRPLME_MCP_URL", "https://api.xrplme.online/mcp")

# Or use the direct country bot API (REST, not JSON-RPC)
# SLUG = "thailand"
# COUNTRY_BOT_URL = f"https://xrplme.online/wc/v1/{SLUG}/bot-solana"

# Solana RPC
SOLANA_RPC = "https://api.mainnet-beta.solana.com"

# USDC mint (native, Solana mainnet)
USDC_MINT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
)


def step1_get_402(url: str, payload: dict) -> tuple[dict, dict]:
    """Call the endpoint without payment, capture the 402 response."""
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": BROWSER_UA},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        print("ERROR: Expected 402, got 200. Endpoint may not require payment.")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        data_402 = json.loads(e.read().decode())
        accept = data_402["accepts"][0]
        print(f"402 received:")
        print(f"  amount:    {int(accept['amount']) / 1e6} USDC")
        print(f"  payTo:     {accept['payTo']}")
        fee_payer = accept.get("extra", {}).get("feePayer", "")
        print(f"  feePayer:  {fee_payer}")
        print(f"  network:   {accept['network']}")
        return data_402, accept


def step2_build_partial_tx(accept: dict, test_kp: Keypair) -> str:
    """Build and partially sign a Solana transaction.

    Returns base64-encoded transaction.

    Key points:
    - 3 instructions: SetComputeUnitLimit + SetComputeUnitPrice + TransferChecked
      (the facilitator requires at least 3 instructions)
    - The feePayer from the 402 response is the message's payer (not your wallet)
    - Only partial_sign with your wallet — the facilitator adds its fee payer
      signature during verification
    - Get a fresh blockhash right before signing
    """
    amount = int(accept["amount"])
    pay_to = Pubkey.from_string(accept["payTo"])
    fee_payer = Pubkey.from_string(accept["extra"]["feePayer"])
    cb_program = Pubkey.from_string(COMPUTE_BUDGET_PROGRAM_ADDRESS)
    test_pubkey = test_kp.pubkey()

    # Source and destination associated token accounts
    src_ata = get_associated_token_address(test_pubkey, USDC_MINT)
    dst_ata = get_associated_token_address(pay_to, USDC_MINT)

    # Compute budget instructions
    cu_limit_ix = Instruction(
        program_id=cb_program,
        accounts=[],
        data=bytes([2]) + (200_000).to_bytes(4, "little"),
    )
    cu_price_ix = Instruction(
        program_id=cb_program,
        accounts=[],
        data=bytes([3]) + (1_000).to_bytes(8, "little"),
    )

    # USDC transfer
    transfer_ix = transfer_checked(
        TransferCheckedParams(
            program_id=TOKEN_PROGRAM_ID,
            source=src_ata,
            mint=USDC_MINT,
            dest=dst_ata,
            owner=test_pubkey,
            amount=amount,
            decimals=6,
            signers=[test_pubkey],
        )
    )

    sol_client = Client(SOLANA_RPC)
    bh = sol_client.get_latest_blockhash().value.blockhash

    # Build message with fee_payer as the payer
    msg = Message.new_with_blockhash(
        [cu_limit_ix, cu_price_ix, transfer_ix], fee_payer, bh
    )

    tx = Transaction.new_unsigned(msg)
    # Partial sign — only your wallet signs the token transfer authorization
    tx.partial_sign([test_kp], bh)

    return base64.b64encode(bytes(tx)).decode()


def step3_retry(url: str, payload: dict, accept: dict, tx_b64: str) -> dict:
    """Retry the same request with the X-PAYMENT-SIGNATURE header."""
    payment_payload = {
        "x402Version": 2,
        "payload": {"transaction": tx_b64},
        "accepted": {
            "scheme": accept["scheme"],
            "network": accept["network"],
            "asset": accept["asset"],
            "amount": accept["amount"],
            "payTo": accept["payTo"],
            "maxTimeoutSeconds": accept.get("maxTimeoutSeconds", 300),
            "extra": accept.get("extra", {}),
        },
        "resource": None,  # set if the 402 included a resource field
    }
    b64_payment = base64.b64encode(
        json.dumps(payment_payload).encode()
    ).decode()

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": BROWSER_UA,
            "X-PAYMENT-SIGNATURE": b64_payment,
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode())
        print(f"\nSUCCESS: HTTP {resp.status}")
        print(json.dumps(result, indent=2))
        return result
    except urllib.error.HTTPError as e:
        print(f"\nHTTP {e.code}")
        print(e.read().decode()[:500])
        return {}


def main():
    # Load your Solana wallet from environment
    secret_json = os.environ.get("SOLANA_TEST_SECRET_JSON")
    if not secret_json:
        print("Set SOLANA_TEST_SECRET_JSON env var with your keypair JSON array.")
        sys.exit(1)
    test_kp = Keypair.from_bytes(bytes(json.loads(secret_json)))

    # --- Option A: MCP server (JSON-RPC) ---
    mcp_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "xrplme_get_country_data",
            "arguments": {"slug": "thailand", "tier": "premium"},
        },
    }
    url = MCP_URL
    payload = mcp_payload

    # --- Option B: Direct country bot API (REST) ---
    # url = "https://xrplme.online/wc/v1/thailand/bot-solana"
    # payload = {"message": "Thailand economic summary"}

    # Step 1: Get 402
    data_402, accept = step1_get_402(url, payload)

    # Step 2: Build and sign transaction
    tx_b64 = step2_build_partial_tx(accept, test_kp)
    print(f"\nPartially signed tx: {len(tx_b64)} chars")

    # Step 3: Retry with payment proof
    step3_retry(url, payload, accept, tx_b64)


if __name__ == "__main__":
    main()
