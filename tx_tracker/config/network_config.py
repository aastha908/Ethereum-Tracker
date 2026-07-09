from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class NetworkConfig:
    name: str
    chain_id: int
    rpc_url: str
    ws_url: Optional[str]
    beacon_url: Optional[str]
    db_path: str