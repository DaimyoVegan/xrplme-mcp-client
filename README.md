# xrplme-mcp-client

> **Status: pre-release.** This repository documents an MCP server that is built
> and deployed but **not yet publicly enabled**. The endpoint below is gated and
> will return `404` until launch. Star/watch the repo to be notified.

Example clients and integration guides for the **XRPLME Country Data** MCP server —
30-country economic and policy data for AI agents, with a free discovery tier and
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
pay-per-query, settled on the XRP Ledger. No accounts, no API-key sales.

- **Transport:** streamable HTTP
- **Endpoint:** `https://api.xrplme.online/mcp` *(gated — 404 until launch)*
- **Coverage:** 30 countries
- **Auth:** opaque Bearer token, `read:countries` scope (free discovery tier)
- **Premium:** x402, 0.1–0.5 XRP per query

---

## Quickstart

### 1. Get a token

The discovery tier is free. During pre-release, request access at
`https://xrplme.online/developers` (page ships at launch). You will receive an
opaque bearer token scoped to `read:countries`. It is not a wallet key and grants
no ability to move funds.

Export it:

```bash
export XRPLME_MCP_TOKEN="your-token-here"
```

**Never commit your token.** Use environment variables or your client's secret store.

### 2. Point a client at the server

See [`examples/`](./examples). The fastest path is `mcp-remote`, which lets any
stdio-only MCP client talk to a remote HTTP server:

```json
{
  "mcpServers": {
    "xrplme-country-data": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote", "https://api.xrplme.online/mcp",
        "--header", "Authorization: Bearer ${XRPLME_MCP_TOKEN}"
      ]
    }
  }
}
```

### 3. Ask a question

> "Using the xrplme tools, compare inflation and unemployment for Thailand,
> Vietnam and Indonesia over the last available year."

The agent calls `xrplme_get_country_data` under the hood and answers with cited,
timestamped figures.

---

## Available surface

**Resources** (read-only, addressable):

| URI | Returns |
|---|---|
| `xrplme://countries` | The 30 supported country slugs |
| `xrplme://status` | Coverage status + data freshness per country |
| `xrplme://country/{slug}/latest` | Latest validated record set for a country |
| `xrplme://country/{slug}/pricing` | Current pricing for that country's routes |
| `xrplme://country/{slug}/schema` | Record schema for that country |

**Tools** (5, all read-only):

| Tool | Purpose |
|---|---|
| `xrplme_list_countries` | Enumerate the 30 slugs, with freshness state |
| `xrplme_get_country_data` | Fetch a country's latest validated records |
| `xrplme_get_country_pricing` | Free pricing lookup (no upstream call) |
| `xrplme_search_records` | Filter records by topic/keyword |
| `xrplme_get_status` | Server + per-country freshness status |

Every response carries freshness metadata: `age_hours`, `state`
(`fresh` / `overdue` / `stale_beyond_max`), and `scraped_at`. Data is refreshed
daily; `state` tells you whether you are looking at something recent.

---

## Paying with x402 (premium routes)

Some routes return `402 Payment Required` with x402 headers. Your client pays in
XRP and retries with proof-of-payment — no signup.

```
GET /mcp → 402  (X402-Payment-Required, X402-Price, X402-Asset, X402-Payment-Address)
        ↓ pay 0.1 XRP on XRPL
GET /mcp + X-PAYMENT-SIGNATURE + X-INV-ID → 200 OK
```

Full walkthrough: [`examples/x402_payment.py`](./examples/x402_payment.py).

> The discovery tier is free and needs no payment. You only touch x402 for
> premium country routes. Pricing is discoverable without paying via
> `xrplme_get_country_pricing`.

---

## Examples

| File | What it shows |
|---|---|
| [`examples/claude_desktop_config.json`](./examples/claude_desktop_config.json) | Claude Desktop / Cursor configuration |
| [`examples/python_client.py`](./examples/python_client.py) | Python client via the MCP SDK |
| [`examples/node_client.js`](./examples/node_client.js) | Node.js client |
| [`examples/x402_payment.py`](./examples/x402_payment.py) | 402 → pay → retry flow |

See [`examples/README.md`](./examples/README.md) for per-example setup.

---

## Data coverage

30 countries across APAC, Europe and the Americas. Each country's dataset is
refreshed daily from that country's own official government and financial
sources, then validated before publication (a candidate dataset is only promoted
if it meets a per-country quality threshold). `xrplme://status` reports the
current freshness state of every country.

> **Freshness is explicit, never implied.** If a country's upstream source has
> been unavailable, the server keeps serving the last validated dataset and
> reports the real age — it does not silently substitute.

---

## License

MIT — see [LICENSE](./LICENSE).

The data served comes from third-party public sources with their own terms and
attribution requirements; consult the `source_url` on each record.

---

## Links

- Website: https://xrplme.online
- Developers: https://xrplme.online/developers *(ships at launch)*
- Issues: use this repository's issue tracker
