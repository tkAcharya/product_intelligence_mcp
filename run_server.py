"""
MCP Server runner — starts the product-intelligence FastMCP server using the
streamable-HTTP transport so that main.py (or any MCP client) can connect.

Usage:
    python run_server.py
    # Serves at http://127.0.0.1:8090/mcp
"""

from server import mcp

if __name__ == "__main__":
    print("Starting MCP server on http://127.0.0.1:8090/mcp ...")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8090)
