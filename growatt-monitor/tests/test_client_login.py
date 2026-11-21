import json
import pathlib
import sys
import threading
import time

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from growatt.client import GrowattAuthLocked, GrowattClient  # noqa: E402

STATUS = json.loads((pathlib.Path(__file__).parent / "fixtures" / "storage_status.json").read_text())


class Resp:
    def __init__(self, body=None, status_code=200, html=None):
        self.status_code = status_code
        self._body = body
        self.text = html or json.dumps(body)
        self.headers = {"Content-Type": "text/html" if html else "application/json"}

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


LOGIN_PAGE = Resp(html="<html><title>Login</title></html>")


class FakeSession:
    """Slow login so concurrent callers overlap; data requests return the
    login page until a login has happened after `expire()`."""

    def __init__(self, login_result=1):
        self.headers = {}
        self.login_result = login_result
        self.logins = 0
        self.valid = False
        self.lock = threading.Lock()

    def post(self, url, data, allow_redirects, timeout):
        time.sleep(0.2)
        with self.lock:
            self.logins += 1
            if self.login_result == 1:
                self.valid = True
        return Resp({"result": self.login_result})

    def request(self, method, url, **kwargs):
        return Resp(STATUS) if self.valid else LOGIN_PAGE

    def expire(self):
        self.valid = False


def client(session):
    c = GrowattClient("user", "pw", "SN", "PLANT")
    c.session = session
    return c


def call_concurrently(fn, n=3):
    errors, results = [], []

    def worker():
        try:
            results.append(fn())
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results, errors


def test_concurrent_first_calls_share_one_login():
    s = FakeSession()
    c = client(s)
    results, errors = call_concurrently(c.get_device_status)
    assert errors == []
    assert len(results) == 3
    assert s.logins == 1


def test_concurrent_session_expiry_relogs_once():
    s = FakeSession()
    c = client(s)
    c.get_device_status()
    s.expire()
    results, errors = call_concurrently(c.get_device_status)
    assert errors == []
    assert len(results) == 3
    assert s.logins == 2


def test_lockout_blocks_further_logins():
    s = FakeSession(login_result=-1)
    c = client(s)
    _, errors = call_concurrently(c.get_device_status)
    assert s.logins == 1
    assert len(errors) == 3
    # The cooldown stops a later call from hitting the login endpoint again.
    with pytest.raises(GrowattAuthLocked):
        c.get_device_status()
    assert s.logins == 1
