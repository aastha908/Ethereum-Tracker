import asyncio
import time
from collections import deque
from datetime import datetime, timezone


class BlockListener:
    def __init__(self, rpc_client, database):
        self.rpc_client = rpc_client
        self.database = database
        self.block_history = {}
        self.max_history = 20
        self.history_queue = deque()

    async def start(self):
        print("[+] Block listener started")

        while True:
            try:
                await self.process_latest_block()
            except Exception as e:
                print("[BLOCK ERROR]", e)

            await asyncio.sleep(12)

    async def process_latest_block(self):
        block = self.rpc_client.rpc("eth_getBlockByNumber", ["latest", True])

        number = int(block["number"], 16)
        hash_ = block["hash"]
        parent = block["parentHash"]
        gas_used = int(block["gasUsed"], 16)
        gas_limit = int(block["gasLimit"], 16)
        base_fee = block.get("baseFeePerGas", "0x0")
        tx_count = len(block["transactions"])
        size = int(block["size"], 16)
        is_empty = 1 if tx_count == 0 else 0

        if number in self.block_history and self.block_history[number]["hash"] == hash_:
            return

        self._detect_reorg(number, hash_, parent)

        self.block_history[number] = {
            "hash": hash_,
            "parent": parent,
        }
        self.history_queue.append(number)

        while len(self.history_queue) > self.max_history:
            old = self.history_queue.popleft()
            self.block_history.pop(old, None)

        timestamp = datetime.now(timezone.utc).isoformat()
        self.database.save_block(
            block_number=number,
            block_hash=hash_,
            parent_hash=parent,
            timestamp=timestamp,
            is_canonical=1,
            gas_used=gas_used,
            gas_limit=gas_limit,
            base_fee_per_gas=base_fee,
            transaction_count=tx_count,
            block_size=size,
            is_empty=is_empty,
        )

    def _detect_reorg(self, number, hash_, parent) -> bool:
        if number in self.block_history and self.block_history[number]["hash"] != hash_:
            depth = self._calculate_reorg_depth(number, parent)
            reorg_group_id = f"{number}-{int(time.time())}"
            old_hash = self.block_history[number]["hash"]
            self.database.save_reorg(
                block_number=number,
                old_block_hash=old_hash,
                new_block_hash=hash_,
                reorg_group_id=reorg_group_id,
                depth=depth,
            )
            print(
                f"[REORG] hash mismatch at block {number} depth={depth}"
            )
            return True

        if (number - 1) in self.block_history:
            expected_parent = self.block_history[number - 1]["hash"]
            if parent != expected_parent:
                depth = self._calculate_reorg_depth(number, parent)
                reorg_group_id = f"{number}-{int(time.time())}"
                old_hash = self.block_history[number - 1]["hash"]
                self.database.save_reorg(
                    block_number=number,
                    old_block_hash=old_hash,
                    new_block_hash=hash_,
                    reorg_group_id=reorg_group_id,
                    depth=depth,
                )
                print(
                    f"[REORG] parent mismatch at block {number} depth={depth}"
                )
                return True

        return False

    def _calculate_reorg_depth(self, block_number, new_parent):
        depth = 0
        current_parent = new_parent
        current_number = block_number - 1

        while current_number in self.block_history:
            old_block = self.block_history[current_number]

            if old_block["hash"] == current_parent:
                break

            depth += 1
            current_parent = old_block["parent"]
            current_number -= 1

        return depth
