from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkConfig:
    name: str
    chain_id: int
    rpc_url: str
    ws_url: str | None
    beacon_url: str | None
    db_path: str
