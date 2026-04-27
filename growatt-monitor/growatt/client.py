import asyncio
import hashlib
import logging
import random
from typing import Any, Awaitable, Callable, Optional

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://server.growatt.com"
LOGIN_PATH = "/login"
DEVICE_DATA_PATH = "/panel/spf/getSPFStatusData"
DEVICE_ENERGY_PATH = "/panel/spf/getSPFEnergyDayChart"

LOGIN_PAGE_MARKERS = ("<title>Login", "name=\"account\"", "loginAction")


class GrowattAPIError(Exception):
    pass


class GrowattAuthError(GrowattAPIError):
    pass


class GrowattClient:
    """Sync requests-based Growatt client. Wrap calls with `run_in_executor`
    when invoking from async code (see `acall`)."""

    def __init__(self, username: str, password: str, device_sn: str):
        self.username = username
        self.password = password
        self.device_sn = device_sn
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                )
            }
        )
        self._logged_in = False
        self._consecutive_failures = 0
        self.unreachable_callback: Optional[Callable[[], Awaitable[None]]] = None
        self._unreachable_alerted = False

    # ---------- auth ----------

    @staticmethod
    def _md5(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def login(self) -> None:
        log.info("Logging into Growatt as %s", self.username)
        resp = self.session.post(
            BASE_URL + LOGIN_PATH,
            data={
                "account": self.username,
                "password": self._md5(self.password),
                "validateCode": "",
            },
            allow_redirects=False,
            timeout=20,
        )
        if resp.status_code not in (200, 302):
            raise GrowattAuthError(f"Login HTTP {resp.status_code}")
        # 302 to /index is success; 200 with JSON {result:1} also success
        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("result") not in (1, "1", True):
                    raise GrowattAuthError(f"Login rejected: {data}")
            except ValueError:
                # Non-JSON 200 — likely still on login page
                if any(m in resp.text for m in LOGIN_PAGE_MARKERS):
                    raise GrowattAuthError("Login failed: still on login page")
        self._logged_in = True
        log.info("Growatt login successful")

    # ---------- request with auto re-login ----------

    def _looks_like_login_page(self, resp: requests.Response) -> bool:
        if resp.status_code in (301, 302):
            loc = resp.headers.get("Location", "")
            if "login" in loc.lower():
                return True
        ctype = resp.headers.get("Content-Type", "")
        if "text/html" in ctype and any(m in resp.text for m in LOGIN_PAGE_MARKERS):
            return True
        return False

    def _request(self, method: str, path: str, **kwargs) -> dict:
        if not self._logged_in:
            self.login()

        url = BASE_URL + path
        kwargs.setdefault("timeout", 20)
        kwargs.setdefault("allow_redirects", False)

        resp = self.session.request(method, url, **kwargs)

        if self._looks_like_login_page(resp):
            log.warning("Session expired for %s — re-logging in", path)
            self._logged_in = False
            self.login()
            resp = self.session.request(method, url, **kwargs)
            if self._looks_like_login_page(resp):
                raise GrowattAuthError(f"Re-login did not restore session for {path}")

        if resp.status_code >= 400:
            raise GrowattAPIError(f"{path} HTTP {resp.status_code}")

        try:
            return resp.json()
        except ValueError:
            raise GrowattAPIError(f"{path} returned non-JSON response")

    # ---------- public endpoints ----------

    def get_device_status(self) -> dict:
        # SPF status endpoint — confirmed via community OSS clients (e.g. PyPi growattServer).
        # Returns current PV / load / battery / grid metrics. Exact key names — see parsers.py TODOs.
        return self._request(
            "POST",
            DEVICE_DATA_PATH,
            data={"storageSn": self.device_sn},
        )

    def get_energy_day_chart(self, date: str) -> dict:
        # date format: "YYYY-MM-DD"
        return self._request(
            "POST",
            DEVICE_ENERGY_PATH,
            data={"storageSn": self.device_sn, "date": date},
        )

    # ---------- async wrapper with backoff + unreachable alerting ----------

    async def acall(self, fn_name: str, *args, **kwargs):
        """Call a sync method by name on this client from async code, with
        exponential backoff on network errors and unreachable-alerting."""
        loop = asyncio.get_running_loop()
        delay = 5.0
        max_delay = 300.0
        attempt = 0
        while True:
            attempt += 1
            try:
                fn = getattr(self, fn_name)
                result = await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
                self._consecutive_failures = 0
                self._unreachable_alerted = False
                return result
            except GrowattAuthError:
                # auth errors are not network-transient; surface immediately
                raise
            except (requests.RequestException, GrowattAPIError) as e:
                self._consecutive_failures += 1
                log.error(
                    "Growatt %s failed (attempt %d, consecutive failures %d): %s",
                    fn_name,
                    attempt,
                    self._consecutive_failures,
                    e,
                )
                if (
                    self._consecutive_failures >= 10
                    and not self._unreachable_alerted
                    and self.unreachable_callback is not None
                ):
                    self._unreachable_alerted = True
                    try:
                        await self.unreachable_callback()
                    except Exception as cb_err:
                        log.exception("unreachable_callback failed: %s", cb_err)
                jitter = random.uniform(0, delay * 0.1)
                await asyncio.sleep(delay + jitter)
                delay = min(delay * 2, max_delay)
