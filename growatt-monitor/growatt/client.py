import asyncio
import hashlib
import logging
import random
import threading
import time
from typing import Awaitable, Callable, Optional

import requests

log = logging.getLogger(__name__)

# Confirmed from a real browser session: this account lives on openapi.growatt.com.
BASE_URL = "https://openapi.growatt.com"
LOGIN_PATH = "/login"
# Verified 2026-11-21 against the live web dashboard: the SPF 6000 ES PLUS is
# served by the "storage" panel endpoints (devicePage/storage5000.js), which
# require plantId as a query param. The /panel/spf/* paths return 404.
DEVICE_DATA_PATH = "/panel/storage/getStorageStatusData"
DEVICE_ENERGY_PATH = "/panel/storage/getStorageEnergyDayChart"
DEVICE_TOTALS_PATH = "/panel/storage/getStorageTotalData"

LOGIN_PAGE_MARKERS = ("<title>Login", 'name="account"', "loginAction")

# Treat these as a hard-stop: bad credentials. Do NOT keep retrying — repeated
# failed logins trigger the captcha lockout (result: -1) which then locks out
# even a correct password.
FATAL_LOGIN_RESULTS = {-2, "-2"}
# Soft-stop: captcha / rate limit. Back off long, do not blindly re-login.
LOCKED_LOGIN_RESULTS = {-1, "-1"}
# After a lockout, no call may try to log in again for this long.
LOCKOUT_COOLDOWN_SECONDS = 600


class GrowattAPIError(Exception):
    pass


class GrowattDeviceOffline(GrowattAPIError):
    """Device is not currently reporting to Growatt (e.g. inverter offline)."""


class GrowattAuthError(GrowattAPIError):
    """Recoverable auth failure (e.g. session expired)."""


class GrowattAuthFatal(GrowattAuthError):
    """Non-recoverable auth failure — wrong credentials. Stop trying."""


class GrowattAuthLocked(GrowattAuthError):
    """Account is temporarily locked / captcha required. Long backoff."""


class GrowattClient:
    """Sync requests-based Growatt client. Wrap calls with `run_in_executor`
    when invoking from async code (see `acall`)."""

    def __init__(self, username: str, password: str, device_sn: str, plant_id: str):
        self.username = username
        self.password = password
        self.device_sn = device_sn
        self.plant_id = plant_id
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/147.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": BASE_URL,
                "Referer": BASE_URL + "/login",
            }
        )
        self._logged_in = False
        # Jobs call in from executor threads at the same time; this keeps it to
        # one login per session instead of one per job.
        self._login_lock = threading.Lock()
        self._login_attempts = 0
        self._locked_until = 0.0
        self._fatal_auth = False  # latched: stop calling once we know creds are bad
        self._consecutive_failures = 0
        self.unreachable_callback: Optional[Callable[[], Awaitable[None]]] = None
        self.fatal_auth_callback: Optional[Callable[[str], Awaitable[None]]] = None
        self._unreachable_alerted = False
        self._fatal_alerted = False
        # Called with None after a call Growatt answered, or the exception after
        # a failed attempt. Must be quick and must not block.
        self.call_listener: Optional[Callable[[Optional[Exception]], None]] = None

    def _notify_listener(self, error: Optional[Exception]) -> None:
        if self.call_listener is None:
            return
        try:
            self.call_listener(error)
        except Exception:
            log.exception("call_listener failed")

    # ---------- auth ----------

    @staticmethod
    def _md5(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def login(self) -> None:
        if self._fatal_auth:
            raise GrowattAuthFatal("Login disabled — credentials previously rejected")

        log.info("Logging into Growatt as %s", self.username)
        # Field shape mirrors the real browser request to openapi.growatt.com/login:
        # account, password (empty), validateCode (empty), isReadPact=0, passwordCrc (md5).
        pwd_md5 = self._md5(self.password)
        resp = self.session.post(
            BASE_URL + LOGIN_PATH,
            data={
                "account": self.username,
                "password": "",
                "validateCode": "",
                "isReadPact": "0",
                "passwordCrc": pwd_md5,
            },
            allow_redirects=False,
            timeout=20,
        )
        if resp.status_code not in (200, 302):
            raise GrowattAuthError(f"Login HTTP {resp.status_code}")

        if resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError:
                if any(m in resp.text for m in LOGIN_PAGE_MARKERS):
                    raise GrowattAuthError("Login failed: still on login page")
                self._logged_in = True
                log.info("Growatt login successful (non-JSON 200)")
                return

            result = data.get("result")
            if result in FATAL_LOGIN_RESULTS:
                self._fatal_auth = True
                raise GrowattAuthFatal(f"Login rejected (bad credentials): {data}")
            if result in LOCKED_LOGIN_RESULTS:
                raise GrowattAuthLocked(f"Login locked / captcha required: {data}")
            if result not in (1, "1", True):
                raise GrowattAuthError(f"Login rejected: {data}")

        self._logged_in = True
        log.info("Growatt login successful")

    def _ensure_login(self, seen_attempts: int) -> None:
        """Log in, unless another call already tried since `seen_attempts`.

        A caller that waited on the lock while someone else logged in reuses
        that result, success or failure, rather than making its own attempt.
        """
        with self._login_lock:
            if self._fatal_auth:
                raise GrowattAuthFatal("Login disabled — credentials previously rejected")
            if self._login_attempts != seen_attempts:
                if self._logged_in:
                    return
                raise GrowattAuthError("Login attempted by another call and failed")
            if time.monotonic() < self._locked_until:
                raise GrowattAuthLocked("Login cooling down after a lockout")
            self._logged_in = False
            try:
                self.login()
            except GrowattAuthLocked:
                self._locked_until = time.monotonic() + LOCKOUT_COOLDOWN_SECONDS
                raise
            finally:
                # Bumped only once the attempt is over, so a thread that read
                # the counter mid-login still sees it change and reuses this.
                self._login_attempts += 1

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
        if self._fatal_auth:
            raise GrowattAuthFatal("Skipping request — credentials previously rejected")
        seen = self._login_attempts
        if not self._logged_in:
            self._ensure_login(seen)

        url = BASE_URL + path
        kwargs.setdefault("timeout", 20)
        kwargs.setdefault("allow_redirects", False)

        seen = self._login_attempts
        resp = self.session.request(method, url, **kwargs)

        if self._looks_like_login_page(resp):
            log.warning("Session expired for %s — re-logging in", path)
            self._ensure_login(seen)
            resp = self.session.request(method, url, **kwargs)
            if self._looks_like_login_page(resp):
                raise GrowattAuthError(f"Re-login did not restore session for {path}")

        # A 404 means a wrong path, not an offline inverter: let it count as a
        # failure so the unreachable alert fires instead of masking the bug.
        if resp.status_code >= 400:
            raise GrowattAPIError(f"{path} HTTP {resp.status_code}")

        try:
            return resp.json()
        except ValueError:
            raise GrowattAPIError(f"{path} returned non-JSON response")

    # ---------- public endpoints ----------

    @staticmethod
    def _check_result(path: str, payload: dict) -> dict:
        if not isinstance(payload, dict) or payload.get("result") not in (1, "1"):
            raise GrowattAPIError(f"{path} returned result={payload.get('result') if isinstance(payload, dict) else payload!r}")
        return payload

    def get_device_status(self) -> dict:
        payload = self._check_result(DEVICE_DATA_PATH, self._request(
            "POST",
            DEVICE_DATA_PATH,
            params={"plantId": self.plant_id},
            data={"storageSn": self.device_sn},
        ))
        # Assumption (not yet observed live): an inverter that is not reporting
        # comes back with an empty obj.
        if not payload.get("obj"):
            raise GrowattDeviceOffline(f"{DEVICE_DATA_PATH} returned no live data")
        return payload

    def get_device_totals(self) -> dict:
        """Today and lifetime kWh counters, as on the web dashboard."""
        return self._check_result(DEVICE_TOTALS_PATH, self._request(
            "POST",
            DEVICE_TOTALS_PATH,
            params={"plantId": self.plant_id},
            data={"storageSn": self.device_sn},
        ))

    def get_energy_day_chart(self, date: str) -> dict:
        # date format: "YYYY-MM-DD"
        return self._check_result(DEVICE_ENERGY_PATH, self._request(
            "POST",
            DEVICE_ENERGY_PATH,
            data={"plantId": self.plant_id, "storageSn": self.device_sn, "date": date},
        ))

    # ---------- async wrapper with backoff + alerting ----------

    async def acall(self, fn_name: str, *args, **kwargs):
        """Call a sync method by name on this client from async code, with
        exponential backoff on transient errors. Auth-fatal errors are
        latched and surfaced once, then all subsequent calls fail fast."""
        if self._fatal_auth:
            raise GrowattAuthFatal("Credentials previously rejected; not retrying")

        loop = asyncio.get_running_loop()
        delay = 5.0
        max_delay = 300.0
        # Captcha lockouts deserve a much longer wait — start at 10 min.
        locked_delay = 600.0
        locked_max = 3600.0
        attempt = 0
        while True:
            attempt += 1
            try:
                fn = getattr(self, fn_name)
                result = await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
                self._consecutive_failures = 0
                self._unreachable_alerted = False
                self._notify_listener(None)
                return result
            except GrowattAuthFatal as e:
                log.error("Fatal auth error: %s", e)
                self._notify_listener(e)
                if not self._fatal_alerted and self.fatal_auth_callback is not None:
                    self._fatal_alerted = True
                    try:
                        await self.fatal_auth_callback(str(e))
                    except Exception:
                        log.exception("fatal_auth_callback failed")
                raise
            except GrowattDeviceOffline as e:
                log.info("Growatt %s: %s", fn_name, e)
                self._consecutive_failures = 0
                self._unreachable_alerted = False
                self._notify_listener(None)
                return None
            except GrowattAuthLocked as e:
                self._notify_listener(e)
                log.warning(
                    "Account locked (attempt %d): %s — sleeping %.0fs",
                    attempt, e, locked_delay,
                )
                await asyncio.sleep(locked_delay)
                locked_delay = min(locked_delay * 2, locked_max)
                continue
            except (requests.RequestException, GrowattAPIError, GrowattAuthError) as e:
                self._consecutive_failures += 1
                self._notify_listener(e)
                log.error(
                    "Growatt %s failed (attempt %d, consecutive failures %d): %s",
                    fn_name, attempt, self._consecutive_failures, e,
                )
                if (
                    self._consecutive_failures >= 10
                    and not self._unreachable_alerted
                    and self.unreachable_callback is not None
                ):
                    self._unreachable_alerted = True
                    try:
                        await self.unreachable_callback()
                    except Exception:
                        log.exception("unreachable_callback failed")
                jitter = random.uniform(0, delay * 0.1)
                await asyncio.sleep(delay + jitter)
                delay = min(delay * 2, max_delay)
