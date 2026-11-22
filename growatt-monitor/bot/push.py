import asyncio
import json
import logging

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

log = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TOPIC = "alerts"
CHANNEL_ID = "alerts"

TITLES = {
    "grid_down": "Grid down",
    "grid_up": "Grid back",
    "battery_low": "Battery low",
    "battery_full": "Battery full",
    "overload": "Inverter overload",
    "fault": "Inverter fault",
    "solar_stopped": "Solar stopped",
    "unreachable": "Growatt unreachable",
}


def build_message(kind: str, text: str) -> dict:
    return {
        "message": {
            "topic": TOPIC,
            "notification": {"title": TITLES.get(kind, "Growatt alert"), "body": text},
            "data": {"kind": kind},
            "android": {
                "priority": "HIGH",
                "notification": {"channel_id": CHANNEL_ID},
            },
        }
    }


class FcmPusher:
    """Sends alerts to the FCM `alerts` topic the Android app subscribes to."""

    def __init__(self, service_account_json: str, timeout: float = 15):
        info = json.loads(service_account_json)
        self.project_id = info["project_id"]
        self.credentials = service_account.Credentials.from_service_account_info(
            info, scopes=[SCOPE]
        )
        self.timeout = timeout
        self.session = requests.Session()

    def _send_sync(self, kind: str, text: str) -> None:
        if not self.credentials.valid:
            self.credentials.refresh(Request(session=self.session))
        resp = self.session.post(
            f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send",
            headers={"Authorization": f"Bearer {self.credentials.token}"},
            json=build_message(kind, text),
            timeout=self.timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"FCM returned HTTP {resp.status_code}: {resp.text[:300]}")

    async def push(self, kind: str, text: str) -> None:
        try:
            await asyncio.get_running_loop().run_in_executor(None, self._send_sync, kind, text)
        except Exception as e:
            log.error("Failed to send %s push: %s", kind, e)
