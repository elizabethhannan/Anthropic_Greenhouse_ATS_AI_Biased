"""Read-only Dewey catalog discovery via its documented MCP endpoint."""
import json
import os
import httpx


class DeweyCatalog:
    def __init__(self):
        self.client = httpx.Client(
            base_url="https://api.deweydata.io", timeout=90,
            headers={"X-API-KEY": os.environ["DEWEY_API_KEY"],
                     "Accept": "application/json, text/event-stream"},
        )
        self.seq = 0
        result = self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "anthropic-person-discovery", "version": "1.0"}})
        self.client.headers["MCP-Protocol-Version"] = result.get("protocolVersion", "2024-11-05")
        self.client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).raise_for_status()

    def rpc(self, method, params):
        self.seq += 1
        response = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": self.seq, "method": method, "params": params})
        response.raise_for_status()
        if response.headers.get("mcp-session-id"):
            self.client.headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
        if "text/event-stream" in response.headers.get("content-type", ""):
            messages = [json.loads(line[5:].strip()) for line in response.text.splitlines() if line.startswith("data:")]
            message = next(item for item in messages if item.get("id") == self.seq)
        else:
            message = response.json()
        if "error" in message:
            raise RuntimeError(message["error"])
        return message["result"]

    def call(self, name, arguments):
        return self.rpc("tools/call", {"name": name, "arguments": arguments})

    def close(self):
        self.client.close()


if __name__ == "__main__":
    catalog = DeweyCatalog()
    try:
        print(json.dumps(catalog.rpc("tools/list", {}), indent=2))
    finally:
        catalog.close()
