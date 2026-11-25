# xrplme-mcp-client

> **Status: LIVE.** The MCP server is publicly available at
> `https://api.xrplme.online/mcp` — anonymous, no token required for the free
> discovery tier. Premium country routes settle per query via **x402** on the
> XRP Ledger, Solana, or Base.

Example clients and integration guides for the **XRPLME Country Data** MCP server —
130-country economic and policy data for AI agents, with a free discovery tier and
x402 pay-per-query premium routes.

---

## What this is

AI agents are good at reasoning and bad at *access*. Reliable, current, per-country
economic data (GDP, inflation, unemployment, trade, policy) is scattered across
dozens of national statistics offices, central banks and multilateral databases —
each with its own format, cadence and availability. Agents that need it end up
either scraping fragile HTML or reasoning from stale training data.

XRPLME exposes that data as a **Model Context Protocol (MCP) server**, so any
MCP-capable client (Claude Desktop, Cursor, custom agents) can query it as a
first-class tool. Payments for premium routes use **x402** — HTTP-native,
pay-per-query, settled on the XRP Ledger, Solana, or Base. No accounts, no API-key sales.

- **Transport:** streamable HTTP
- **Endpoint:** `https://api.xrplme.online/mcp` *(live, anonymous)*
- **Coverage:** 130 countries, plus deep verified records for 13 of them
- **Auth:** none for the free discovery tier
- **Premium:** x402 — 1 XRP standard / 5 XRP AI-enhanced (1 / 7 USDC on Solana and Base); deep 2 XRP / $2.00
- **Agent intent registry:** post free, $1 paid-to-query, $19/month Pro
- **Also available over plain HTTP (not MCP tools yet):** Investigate — screening
  `/wc/screen/bot` ($2), company look-up `/wc/entity/lookup/bot` ($1) and
  ownership chains `/wc/entity/ownership/bot` ($5). Append `-solana` or `-evm`
  for USDC. Machine-readable pricing: https://xrplme.online/llms.txt

---

## Quickstart

### 1. Point a client at the server

No token needed. The fastest path is `mcp-remote`, which lets any stdio-only MCP
client talk to a remote HTTP server:

```json
{
  "mcpServers": {
    "xrplme-country-data": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://api.xrplme.online/mcp"]
    }
  }
}
```

See [`examples/`](./examples) for Claude Desktop / Cursor, Python and Node clients.

### 2. Ask a question

> "Using the xrplme tools, compare inflation and unemployment for Thailand,
> Vietnam and Indonesia over the last available year."

The agent calls `xrplme_get_country_data` under the hood and answers with cited,
timestamped figures.

---

## Available surface

**Resources** (read-only, addressable):

| URI | Returns |
|---|---|
| `xrplme://countries` | The 130 supported country slugs |
| `xrplme://status` | Coverage status + data freshness per country |

**Tools** (11, all read-only except the optional survey submit):

| Tool | Purpose |
|---|---|
| `xrplme_list_countries` | Enumerate the 130 slugs, with freshness state |
| `xrplme_get_country_status` | Per-country freshness + availability status |
| `xrplme_get_pricing` | Pricing lookup (no upstream call) |
| `xrplme_get_country_data` | Fetch a country's latest validated records |
| `xrplme_get_country_schema` | Record schema for a country |
| `xrplme_get_survey_questions` | Retrieve the data-quality survey questions |
| `xrplme_submit_survey` | Submit survey responses |
| `xrplme_get_survey_stats` | Aggregate survey statistics |
| `xrplme_screen` | Sanctions / watchlist screening of a person or business (paid) |
| `xrplme_entity_lookup` | Company look-up: legal name, status, jurisdiction, entity ID (paid) |
| `xrplme_entity_ownership` | Ownership tree to ultimate parent and subsidiaries (paid) |

Every response carries freshness metadata: `age_hours`, `state`
(`fresh` / `overdue` / `stale_beyond_max`), and `scraped_at`. Datasets are
refreshed on a regular schedule; `state` and `scraped_at` tell you exactly how
recent the figures you are looking at are.

---

## Paying with x402 (premium routes)

Some routes return `402 Payment Required` with x402 headers. Your client pays and
retries with proof-of-payment — no signup. Three settlement rails are supported:
XRP Ledger, Solana, and Base.

### XRP Ledger

Routes live under `/wc/v1/<slug>/` — `/bot` (standard) and `/bot/ai`
(AI-enhanced). Solana equivalents are `/bot-solana` and `/bot-solana/ai`, Base
equivalents are `/bot-evm` and `/bot-evm/ai`.

```
POST /wc/v1/thailand/bot → 402  (accepts[]: amount, asset, payTo, extra.invoiceId)
         ↓ pay 1 XRP standard / 5 XRP AI tier on XRPL
POST /wc/v1/thailand/bot + X-PAYMENT-SIGNATURE → 200 OK
```

The `402` body carries the x402 challenge — read `accepts[0]` for `amount`,
`payTo` and `extra.invoiceId`, and bind the payment to that invoice id so it
cannot be replayed against a different query.

The MCP surface reports the same requirement in-band: calling
`xrplme_get_country_data` unpaid returns a `payment_required` result with the
same pricing, and you resubmit with `x_payment_signature` and `x_inv_id` as
**tool arguments** rather than HTTP headers.

Full walkthrough: [`examples/demo_xrplme_paid.py`](./examples/demo_xrplme_paid.py).

### Solana USDC

```
POST /mcp → 402  (X402-Payment-Required + accepts with feePayer in extra)
         ↓ build + partial_sign Solana tx (ComputeBudget + TransferChecked USDC)
POST /mcp + X-PAYMENT-SIGNATURE (base64 V2 payload) → 200 OK
```

The 402 response includes a `feePayer` in the `accepts[0].extra` field — this
wallet pays Solana transaction fees. Your client builds a 3-instruction
transaction, partially signs it with your USDC wallet, and sends the base64
transaction in a V2 payment payload via the `X-PAYMENT-SIGNATURE` header. The
facilitator adds its fee payer signature and verifies on-chain.

Full walkthrough: [`examples/x402_payment_solana.py`](./examples/x402_payment_solana.py).

### Base USDC

```
POST /wc/v1/thailand/bot-evm → 402  (accepts[0]: network, asset, amount, payTo)
         ↓ send at least `amount` USDC on Base to `payTo`
POST /wc/v1/thailand/bot-evm + PAYMENT-SIGNATURE: {"txHash":"0x…"} → 200 OK
```

`/bot-evm` is the standard tier, `/bot-evm/ai` the AI-enhanced tier, and
`/bot-evm/custom` the bounded multi-country tier — the same three prices as the
XRP and Solana routes.

Payment is a plain USDC transfer, verified directly against Base: the server reads
the transaction receipt and checks the token, the recipient, the amount and the age
of the transfer. There is no facilitator between your payment and the data, so
nothing has to trust a third party's word that you paid.

One transfer buys one call. A replayed hash returns `409`; a transfer below the
tier price, older than one hour, on another chain, or to a different address is
rejected with `402`. The payment header takes JSON or base64-encoded JSON:

```json
{"txHash": "0x<your Base transaction hash>"}
```

For rehearsal, `/bot-evm-test` (and `/ai`, `/custom`) settles on Base Sepolia
(`eip155:84532`) at the same prices in test USDC. It verifies the payment and
returns a receipt, and serves no records — country data is only released on the
production rails.

Full walkthrough: [`examples/x402_payment_base.py`](./examples/x402_payment_base.py).

> The discovery tier is free and needs no payment. You only touch x402 for
> premium country routes. Pricing is discoverable without paying via
> `xrplme_get_pricing`.

---

## Examples

| File | What it shows |
|---|---|
| [`examples/claude_desktop_config.json`](./examples/claude_desktop_config.json) | Claude Desktop / Cursor configuration |
| [`examples/python_client.py`](./examples/python_client.py) | Python client via the MCP SDK |
| [`examples/node_client.js`](./examples/node_client.js) | Node.js client |
| [`examples/x402_payment.py`](./examples/x402_payment.py) | MCP surface: `payment_required` → pay XRP → retry with proof |
| [`examples/x402_payment_solana.py`](./examples/x402_payment_solana.py) | 402 → pay USDC on Solana → retry flow |
| [`examples/demo_xrplme_paid.py`](./examples/demo_xrplme_paid.py) | Full paid run on the REST surface, with on-chain TXID proof |

See [`examples/README.md`](./examples/README.md) for per-example setup.

---

## Data coverage

130 countries across APAC, Europe, Africa, the Middle East and the Americas. Each
country's dataset is refreshed on a regular schedule from that country's own
official government and financial sources, then validated before publication (a
candidate dataset is only promoted if it meets a per-country quality threshold).
`xrplme://status` reports the current freshness state of every country.

> **Freshness is explicit, never implied.** If a country's upstream source has
> been unavailable, the server keeps serving the last validated dataset and
> reports the real age — it does not silently substitute.

---

## Keeping this repo in sync with the platform

The README describes a live, changing service, so it drifts. This repo ships the gate
that catches it:

```bash
python3 scripts/verify_docs_sync.py          # 0 = in sync, 1 = drift, 2 = unreachable
```

It reads the live surface (country count, tool list, both pricing tiers, the
`payment_required` challenge) and fails with one line per stale claim. It also fails
when the fix is committed but not pushed, so an update only counts once it is public.

Install the pre-push hook once per clone:

```bash
cp scripts/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

After that a push carrying stale docs is blocked with the exact claims to fix.
An unreachable platform (offline, Cloudflare) exits `2` and **allows** the push —
being offline is not evidence that the docs are wrong. Bypass for a single push with
`git push --no-verify`.

---

## License

MIT — see [LICENSE](./LICENSE).

The data served comes from third-party public sources with their own terms and
attribution requirements; consult the `source_url` on each record.

---

## Links

- Website: https://xrplme.online
- Developers: https://xrplme.online/developers
- Issues: use this repository's issue tracker
