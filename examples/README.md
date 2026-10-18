# Examples

All examples target `https://api.xrplme.online/mcp`, overridable with
`XRPLME_MCP_URL`. The endpoint is public and anonymous — no token required.

## Setup

Nothing to configure for the free discovery tier. The payment examples additionally
need wallet credentials — a dedicated low-balance wallet, kept in a 0600 env file.

```bash
# XRPL payment example
export XRPLME_WALLET_SEED="s..."   # payment example only. Never commit.

# Solana USDC payment example
export SOLANA_TEST_SECRET_JSON='[...]'   # your USDC wallet keypair JSON
```

## Files

| File | Runtime | Install |
|---|---|---|
| `claude_desktop_config.json` | Claude Desktop / Cursor | none (uses `npx mcp-remote`) |
| `python_client.py` | Python 3.10+ | `pip install mcp` |
| `node_client.js` | Node 18+ | `npm install @modelcontextprotocol/sdk` |
| `x402_payment.py` | Python 3.10+ | `pip install xrpl-py requests` |
| `x402_payment_solana.py` | Python 3.10+ | `pip install requests solders solana-py spl-token xrpl` |

## Run

```bash
python python_client.py
node node_client.js
python x402_payment.py
python x402_payment_solana.py
```

## What each example shows

- **claude_desktop_config.json** — wiring a remote HTTP MCP server into a
  stdio-only client via `mcp-remote`. No auth header required.
- **python_client.py** — connecting with the official Python SDK, then
  `list_tools` / `list_resources` / `call_tool` against real endpoints.
- **node_client.js** — the same flow with the TypeScript SDK.
- **x402_payment.py** — the full 402 → pay XRP → retry loop, including invoice-bound
  payment so a proof cannot be replayed against a different query.
- **x402_payment_solana.py** — the full 402 → pay USDC on Solana → retry loop,
  including building the 3-instruction transaction (ComputeBudget +
  TransferChecked), partial-signing with your wallet, and letting the facilitator
  add its fee payer signature.

## Notes

- Discovery tools (`xrplme_list_countries`, `xrplme_get_country_status`,
  `xrplme_get_pricing`, `xrplme_get_country_data`, `xrplme_get_country_schema`)
  are **free** and need no payment.
- Every data response includes `age_hours`, `state` and `scraped_at` so you can
  decide for yourself whether the data is fresh enough.
- Do not print or log wallet seeds. The payment examples read the seed from the
  environment and never echo it.
