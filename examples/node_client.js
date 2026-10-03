/**
 * XRPLME Country Data — Node.js MCP client example.
 *
 *   node node_client.js
 *
 * Requires:  npm install @modelcontextprotocol/sdk
 *
 * The endpoint is public and anonymous — no token required.
 */
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const MCP_URL = process.env.XRPLME_MCP_URL ?? "https://api.xrplme.online/mcp";

const transport = new StreamableHTTPClientTransport(new URL(MCP_URL));

const client = new Client({ name: "xrplme-example", version: "1.0.0" });

await client.connect(transport);
console.log(`connected to ${MCP_URL}\n`);

// --- 1. Discover the surface ---------------------------------------------
const { tools } = await client.listTools();
console.log("tools:", tools.map((t) => t.name).join(", "), "\n");

const { resources } = await client.listResources();
console.log("resources:", resources.map((r) => r.uri).join(", "), "\n");

// --- 2. Coverage + freshness ---------------------------------------------
const status = await client.callTool({ name: "xrplme_get_country_status", arguments: {} });
console.log("status:", status.content[0].text.slice(0, 400), "\n");

// --- 3. One country's data -----------------------------------------------
const data = await client.callTool({
  name: "xrplme_get_country_data",
  arguments: { slug: "thailand" },
});
console.log("thailand (truncated):", data.content[0].text.slice(0, 600));

await client.close();
