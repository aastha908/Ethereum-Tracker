import asyncio

MAX_BACKFILL_GAP = 10


class ConsensusMonitor:
    def __init__(self, beacon_client, database):
        self.beacon_client = beacon_client
        self.database = database

    async def start(self):
        await asyncio.gather(
            self._slot_loop(),
            self._epoch_loop(),
        )

    async def _slot_loop(self):
        while True:
            try:
                header = self.beacon_client.get_head_header()
                slot = int(header["header"]["message"]["slot"])
                proposer_index = int(header["header"]["message"]["proposer_index"])
                block_root = header["root"]
                epoch = slot // 32

                last_slot = self.database.get_latest_recorded_slot()
                if last_slot is not None and slot > last_slot + 1:
                    self._backfill_missed_slots(last_slot, slot)

                self.database.save_consensus_slot(
                    slot=slot,
                    epoch=epoch,
                    proposer_index=proposer_index,
                    block_root=block_root,
                    is_missed=0,
                )

            except Exception as e:
                print(
                    "[CONSENSUS SLOT ERROR]",
                    str(e)
                )

            await asyncio.sleep(12)

    def _backfill_missed_slots(self, last_slot, new_slot):
        gap = new_slot - last_slot - 1
        if gap > MAX_BACKFILL_GAP:
            print(
                f"[CONSENSUS] Gap of {gap} slots between {last_slot} and "
                f"{new_slot} exceeds backfill threshold - likely a tracker restart, "
                "not treating as missed slots"
            )
            return

        for slot in range(last_slot + 1, new_slot):
            self.database.save_consensus_slot(
                slot=slot,
                epoch=slot // 32,
                proposer_index=None,
                block_root=None,
                is_missed=1,
            )

    async def _epoch_loop(self):
        while True:
            try:
                checkpoints = self.beacon_client.get_finality_checkpoints()
                finalized_epoch = int(checkpoints["finalized"]["epoch"])
                self.database.save_epoch_finality(
                    epoch=finalized_epoch,
                    justified=1,
                    finalized=1,
                )

            except Exception as e:
                print(
                    "[CONSENSUS EPOCH ERROR]",
                    str(e)
                )

            await asyncio.sleep(384)
