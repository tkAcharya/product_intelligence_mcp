import asyncio
import json
from fastmcp import Client

async def main():
    async with Client("http://127.0.0.1:8090/mcp") as client:
        tools = await client.list_tools()
        # tools might be a list of objects or dicts. Let's try to convert them to dicts
        out = []
        for t in tools:
            out.append({
                "name": getattr(t, "name", t.get("name") if isinstance(t, dict) else str(t)),
                "description": getattr(t, "description", t.get("description", "") if isinstance(t, dict) else ""),
                "inputSchema": getattr(t, "inputSchema", t.get("inputSchema", {}) if isinstance(t, dict) else {})
            })
        print(json.dumps(out, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
