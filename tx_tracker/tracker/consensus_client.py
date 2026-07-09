import requests


class BeaconClient:
    def __init__(self, beacon_url: str):
        self.beacon_url = beacon_url

    def get_head_header(self):
        response = requests.get(
            f"{self.beacon_url}/eth/v1/beacon/headers/head",
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["data"]

    def get_finality_checkpoints(self):
        response = requests.get(
            f"{self.beacon_url}/eth/v1/beacon/states/head/finality_checkpoints",
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["data"]
