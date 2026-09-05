"""Check the seeded local Compose stack, including email login and discovery.

Uses only the demo's loopback API and Mailpit inbox; never an external mailbox.
Run after docker compose exec backend python seed_synthetic.py.
"""
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request

API = "http://localhost:8000"
MAIL = "http://localhost:8025"
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with client.open(req, timeout=10) as response:
        return json.load(response)


def main():
    assert request(f"{API}/api/health")["status"] == "ok"
    request(f"{API}/api/auth/request", {"email": "maya@example.com"})
    message = None
    for _ in range(20):
        for item in request(f"{MAIL}/api/v1/messages").get("messages", []):
            if any(person.get("Address") == "maya@example.com" for person in item.get("To", [])):
                message = request(f"{MAIL}/api/v1/message/{item['ID']}")
                break
        if message:
            break
        time.sleep(0.5)
    assert message, "No login message arrived in the local Mailpit inbox"
    match = re.search(r"http://localhost:3000/auth/verify\?token=([^\s<>]+)", message["Text"])
    assert match, "Login message did not contain the expected local link"
    request(f"{API}/api/auth/verify?" + urllib.parse.urlencode({"token": match.group(1)}))
    assert request(f"{API}/api/auth/me")["email"] == "maya@example.com"
    groups = request(f"{API}/api/organizations")
    assert groups["total"] > 0, "Seeded groups were not discoverable"
    events = request(f"{API}/api/events")
    assert events["total"] > 0, "Seeded events were not discoverable"
    assert request(f"{API}/api/matches"), "Seeded example connections were not returned"
    print("PASS: local email login, persisted session, graph discovery, and seeded connections")


if __name__ == "__main__":
    main()
