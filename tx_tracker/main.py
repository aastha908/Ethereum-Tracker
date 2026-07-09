import argparse
import asyncio

from tx_tracker.config.networks import load_network_config
from tx_tracker.database.db import Database
from tx_tracker.tracker.rpc_client import RPCClient
from tx_tracker.tracker.pending_listener import PendingTransactionListener
from tx_tracker.tracker.receipt_monitor import ReceiptMonitor
from tx_tracker.tracker.confirmation_monitor import ConfirmationMonitor
from tx_tracker.tracker.block_listener import BlockListener
from tx_tracker.tracker.consensus_client import BeaconClient
from tx_tracker.tracker.consensus_monitor import ConsensusMonitor


async def main(network_name: str):
    network_config = load_network_config(network_name)

    print(
        f"Starting tracker for {network_config.name} (chain_id={network_config.chain_id})"
    )
    print(f"Database path: {network_config.db_path}")

    rpc_client = RPCClient(rpc_url=network_config.rpc_url)
    database = Database(db_path=network_config.db_path)
    database.initialize_database()

    listener = PendingTransactionListener(
        ws_url=network_config.ws_url,
        rpc_client=rpc_client,
        database=database,
    )
    monitor = ReceiptMonitor(rpc_client=rpc_client, database=database)
    confirmation_monitor = ConfirmationMonitor(rpc_client=rpc_client, database=database)
    block_listener = BlockListener(rpc_client=rpc_client, database=database)

    coroutines = [
        listener.subscribe(),
        monitor.start(),
        confirmation_monitor.start(),
        block_listener.start(),
    ]

    if network_config.beacon_url:
        beacon_client = BeaconClient(beacon_url=network_config.beacon_url)
        consensus_monitor = ConsensusMonitor(
            beacon_client=beacon_client,
            database=database,
        )
        coroutines.append(consensus_monitor.start())
        print("Consensus monitoring: enabled")
    else:
        print("Consensus monitoring: disabled (no beacon_url for this network)")

    await asyncio.gather(*coroutines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ethereum transaction tracker")
    parser.add_argument(
        "--network",
        choices=["mainnet", "testnet"],
        required=True,
        help="Network to run against",
    )
    args = parser.parse_args()
    asyncio.run(main(args.network))
