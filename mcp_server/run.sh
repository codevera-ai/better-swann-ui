#!/bin/sh
# Start the Swann MCP server. It needs the app running: `make run`.
# Its own virtual environment, because the MCP library wants a newer
# Starlette than FastAPI allows.
here=$(cd "$(dirname "$0")" && pwd)
exec "$here/../.venv-mcp/bin/python" "$here/swann_mcp.py"
