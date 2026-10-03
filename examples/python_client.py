#!/usr/bin/env python3
"""
XRPLME Country Data — Python MCP client example.

Talks to the remote streamable-HTTP MCP server using the official Python SDK.
The endpoint is public and anonymous — no token required.

    python python_client.py

Requires:  pip install mcp

Override the endpoint (e.g. for a local test server):
    export XRPLME_MCP_URL="http://127.0.0.1:48200/mcp"
"""
import asyncio
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("XRPLME_MCP_URL", "https://api.xrplme.online/mcp")


async def main() -> None:
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(f"connected to {MCP_URL}\n")

            # --- 1. Discover the surface -------------------------------------
            tools = await session.list_tools()
            print("tools:")
            for t in tools.tools:
                print(f"  - {t.name}")
            print()

            resources = await session.list_resources()
            print("resources:")
            for r in resources.resources:
                print(f"  - {r.uri}")
            print()

            # --- 2. Which countries are covered, and how fresh are they? ------
            status = await session.call_tool("xrplme_get_country_status", {})
            print("status:", status.content[0].text[:400], "\n")

            # --- 3. Fetch one country's data ---------------------------------
            data = await session.call_tool(
                "xrplme_get_country_data",
                {"slug": "thailand"},
            )
            text = data.content[0].text
            print("thailand (truncated):", text[:600])

            # --- 4. Free pricing lookup (no payment, no upstream call) -------
            pricing = await session.call_tool(
                "xrplme_get_pricing",
                {"slug": "thailand"},
            )
            print("\npricing:", pricing.content[0].text[:300])


if __name__ == "__main__":
    asyncio.run(main())
