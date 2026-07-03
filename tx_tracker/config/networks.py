import os
from pathlib import Path

from tx_tracker.config.network_config import NetworkConfig


def load_network_config(name: str) -> NetworkConfig:
    if name not in ("mainnet", "testnet"):
        raise ValueError(
            f"Unknown network '{name}', expected 'mainnet' or 'testnet'"
        )

    env_path = Path(__file__).resolve().parent.parent.parent / "networks" / f"{name}.env"

    if not env_path.exists():
        raise FileNotFoundError(
            f"Network config file not found: {env_path}"
        )

    values = {}
    with env_path.open("r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()

    if name == "mainnet":
        if "ALCHEMY_API_KEY" not in os.environ:
            raise EnvironmentError(
                "ALCHEMY_API_KEY must be set in the environment for mainnet"
            )

    rpc_url = values.get("RPC_URL", "")
    ws_url = values.get("WS_URL", "")
    beacon_url = values.get("BEACON_URL", "")
    chain_id = int(values.get("CHAIN_ID", "0"))
    db_path = values.get("DB_PATH", "")

    if "${ALCHEMY_API_KEY}" in rpc_url:
        rpc_url = rpc_url.replace(
            "${ALCHEMY_API_KEY}",
            os.environ["ALCHEMY_API_KEY"],
        )

    if "${ALCHEMY_API_KEY}" in ws_url:
        ws_url = ws_url.replace(
            "${ALCHEMY_API_KEY}",
            os.environ["ALCHEMY_API_KEY"],
        )

    # Resolve relative database paths from the repository root.
    if db_path and not os.path.isabs(db_path):
        repo_root = env_path.parent.parent
        db_path = str((repo_root / db_path).resolve())

    return NetworkConfig(
        name=name,
        chain_id=chain_id,
        rpc_url=rpc_url,
        ws_url=None if ws_url == "" else ws_url,
        beacon_url=None if beacon_url == "" else beacon_url,
        db_path=db_path,
    )
