import requests


class RPCClient:
    def __init__(self, rpc_url: str):
        self.rpc_url = rpc_url

    def rpc(self, method: str, params: list | None = None):
        if params is None:
            params = []

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        response = requests.post(
            self.rpc_url,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        result = response.json()

        if "error" in result:
            raise Exception(result["error"])

        return result["result"]

    def get_safe_block(self):
        return self.rpc("eth_getBlockByNumber", ["safe", False])

    def get_finalized_block(self):
        return self.rpc("eth_getBlockByNumber", ["finalized", False])
