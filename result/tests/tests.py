#!/usr/bin/env python3
"""Exercise the voting flow through its public HTTP and Socket.IO interfaces."""

import json
import sys
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


VOTE_URL = "http://vote:8080/"
SOCKET_URL = "http://result:8080/socket.io/"
DEADLINE_SECONDS = 90


def fail(message):
    print("TEST FAILED: " + message, file=sys.stderr)
    raise SystemExit(1)


def request(opener, url, data=None, timeout=5):
    headers = {"Accept": "*/*"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        with opener.open(Request(url, data=data, headers=headers), timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(str(error)) from error


def wait_for_http(opener, url, deadline):
    last_error = "service did not respond"
    while time.monotonic() < deadline:
        try:
            request(opener, url)
            return
        except RuntimeError as error:
            last_error = str(error)
            time.sleep(1)
    fail("timed out waiting for %s: %s" % (url, last_error))


class ScoreStream:
    def __init__(self, opener):
        self.opener = opener
        self.sid = None

    def connect(self):
        handshake = request(self.opener, SOCKET_URL + "?" + urlencode({
            "EIO": "4", "transport": "polling", "t": str(time.time_ns()),
        }))
        if not handshake.startswith("0"):
            raise RuntimeError("unexpected Engine.IO handshake: " + handshake[:100])
        self.sid = json.loads(handshake[1:])["sid"]
        self.send("40")

    def send(self, payload):
        query = urlencode({"EIO": "4", "transport": "polling", "sid": self.sid, "t": str(time.time_ns())})
        request(self.opener, SOCKET_URL + "?" + query, payload.encode("utf-8"))

    def next_scores(self, deadline):
        while time.monotonic() < deadline:
            query = urlencode({"EIO": "4", "transport": "polling", "sid": self.sid, "t": str(time.time_ns())})
            try:
                payload = request(self.opener, SOCKET_URL + "?" + query, timeout=20)
            except RuntimeError:
                time.sleep(1)
                continue
            for packet in payload.split("\x1e"):
                if packet == "2":
                    self.send("3")
                    continue
                if not packet.startswith("42"):
                    continue
                event = json.loads(packet[2:])
                if event[0] != "scores":
                    continue
                scores = json.loads(event[1])
                return {"a": int(scores.get("a", 0)), "b": int(scores.get("b", 0))}
        fail("timed out waiting for a live result score event")


def wait_for_scores(stream, expected, deadline):
    last_scores = None
    while time.monotonic() < deadline:
        last_scores = stream.next_scores(deadline)
        if last_scores == expected:
            return
    fail("expected live scores %s, last received %s" % (expected, last_scores))


def submit_vote(opener, vote):
    response = request(opener, VOTE_URL, urlencode({"vote": vote}).encode("utf-8"))
    if 'var vote = "' + vote + '"' not in response:
        fail("vote service did not acknowledge vote %s" % vote)


def main():
    deadline = time.monotonic() + DEADLINE_SECONDS
    jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(jar))

    wait_for_http(opener, VOTE_URL, deadline)

    stream = ScoreStream(opener)
    last_error = "result Socket.IO endpoint did not respond"
    while time.monotonic() < deadline:
        try:
            stream.connect()
            break
        except (KeyError, ValueError, RuntimeError) as error:
            last_error = str(error)
            time.sleep(1)
    else:
        fail("could not connect to the result Socket.IO endpoint: %s" % last_error)

    baseline = stream.next_scores(deadline)
    submit_vote(opener, "a")
    wait_for_scores(stream, {"a": baseline["a"] + 1, "b": baseline["b"]}, deadline)

    # Reuse the same cookie so the worker must update one database row.
    submit_vote(opener, "b")
    wait_for_scores(stream, {"a": baseline["a"], "b": baseline["b"] + 1}, deadline)
    print("TEST PASSED: live scores reflected a vote and the same voter changed it without adding a vote")


if __name__ == "__main__":
    main()
