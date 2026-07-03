import asyncio


class ReceiptMonitor:
    def __init__(self, rpc_client, database):
        self.rpc_client = rpc_client
        self.database = database

    async def start(self):

        print(
            "[+] Receipt monitor started"
        )

        while True:

            try:

                await self.check_pending()

            except Exception as e:

                print(
                    "[RECEIPT ERROR]",
                    str(e)
                )

            await asyncio.sleep(5)

    async def check_pending(self):

        pending_txs = self.database.get_pending_transactions()

        if not pending_txs:
            return

        print(
            f"[CHECKING] {len(pending_txs)} pending txs"
        )

        for tx in pending_txs:

            await self.process_tx(
                tx["tx_hash"]
            )

    async def process_tx(
        self,
        tx_hash
    ):

        try:

            receipt = self.rpc_client.rpc(
                "eth_getTransactionReceipt",
                [tx_hash]
            )

            if receipt is None:
                return

            block_number = int(receipt["blockNumber"], 16)
            tx_index = int(receipt["transactionIndex"], 16)
            gas_used = int(receipt["gasUsed"], 16)
            status = int(receipt["status"], 16)

            self.database.save_receipt(
                tx_hash=tx_hash,
                block_number=block_number,
                block_hash=receipt["blockHash"],
                transaction_index=tx_index,
                gas_used=gas_used,
                effective_gas_price=receipt.get("effectiveGasPrice", "0x0"),
                status=status,
                contract_address=receipt.get("contractAddress"),
            )

            self.database.mark_transaction_mined(
                tx_hash,
                block_number,
                receipt["blockHash"],
            )

            self.database.mark_transaction_result(
                tx_hash,
                status,
            )

            print(
                f"[MINED] {tx_hash}"
            )

        except Exception as e:

            print(
                "[TX ERROR]",
                tx_hash,
                str(e)
            )