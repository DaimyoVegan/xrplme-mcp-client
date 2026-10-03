# Examples

All examples target `https://api.xrplme.online/mcp`, overridable with
`XRPLME_MCP_URL`. **Pre-launch the endpoint is gated and returns 404.**

## Setup

```bash
export XRPLME_MCP_TOKEN="your-discovery-token"   # free tier
```

Never commit the token. For the payment example you also need
`XRPLME_WALLET_SEED` — a dedicated low-balance wallet, kept in a 0600 env file.

## Files

| File | Runtime | Install |
|---|---|---|
| `claude_desktop_config.json` | Claude Desktop / Cursor | none (uses `npx mcp-remote`) |
| `python_client.py` | Python 3.10+ | `pip install mcp` |
| `node_client.js` | Node 18+ | `npm install @modelcontextprotocol/sdk` |
| `x402_payment.py` | Python 3.10+ | `pip install xrpl-py requests` |

## Run

```bash
python python_client.py
node node_client.js
python x402_payment.py
```

## What each example shows

- **claude_desktop_config.json** — wiring a remote HTTP MCP server into a
  stdio-only client via `mcp-remote`, with the bearer header.
- **python_client.py** — connecting with the official Python SDK, then
  `list_tools` / `list_resources` / `call_tool` against real endpoints.
- **node_client.js** — the same flow with the TypeScript SDK.
- **x402_payment.py** — the full 402 → pay → retry loop, including invoice-bound
  payment so a proof cannot be replayed against a different query.

## Notes

- Discovery tools (`xrplme_list_countries`, `xrplme_get_status`,
  `xrplme_get_country_pricing`, `xrplme_search_records`) are **free** and need no
  payment.
- Every data response includes `age_hours`, `state` and `scraped_at` so you can
  decide for yourself whether the data is fresh enough.
- Do not print or log wallet seeds. The payment example reads the seed from the
  environment and never echoes it.
