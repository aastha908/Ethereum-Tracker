import asyncio


class ConfirmationMonitor:
    def __init__(self, rpc_client, database):
        self.rpc_client = rpc_client
        self.database = database

    async def start(self):

        print(
            "[+] Confirmation monitor started"
        )

        while True:

            try:

                await self.process()

            except Exception as e:

                print(
                    "[CONFIRMATION ERROR]",
                    e
                )

            await asyncio.sleep(12)

    async def process(self):

        latest_block = int(
            self.rpc_client.rpc(
                "eth_blockNumber",
                []
            ),
            16
        )

        safe_block = self.rpc_client.get_safe_block()
        finalized_block = self.rpc_client.get_finalized_block()

        safe_number = (
            int(safe_block["number"], 16)
            if safe_block
            else 0
        )

        finalized_number = (
            int(finalized_block["number"], 16)
            if finalized_block
            else 0
        )

        txs = self.database.get_active_transactions()

        for tx in txs:

            if (
                tx["current_block_number"]
                is None
            ):
                continue

            confirmations = (
                latest_block
                - tx["current_block_number"]
            )

            if (
                tx["current_block_number"]
                <= safe_number
                and not self.database.has_event(
                    tx["tx_hash"],
                    "SAFE"
                )
            ):
                self.database.mark_safe(tx["tx_hash"])

            if (
                tx["current_block_number"]
                <= finalized_number
                and not self.database.has_event(
                    tx["tx_hash"],
                    "FINALIZED"
                )
            ):
                self.database.mark_finalized(tx["tx_hash"])

            previous = self.database.get_latest_confirmation(
                tx["tx_hash"]
            )

            if confirmations <= previous:
                continue

            self.database.save_confirmation(
                tx["tx_hash"],
                tx["current_block_number"],
                confirmations
            )

            self.record_milestone(
                tx["tx_hash"],
                confirmations
            )

            print(
                f"[CONFIRMATIONS] "
                f"{tx['tx_hash'][:10]} "
                f"{confirmations}"
            )

    def record_milestone(
        self,
        tx_hash,
        confirmations
    ):

        milestones = [
            1,
            2,
            3,
            5,
            10,
            12,
            25,
            50,
            64
        ]

        if confirmations in milestones:
            self.database.add_event(
                tx_hash,
                "CONFIRMED",
                f"{confirmations} confirmations"
            )
