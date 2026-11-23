"""Watch HiBid lots and email when a new bid lands.

Runs once and exits (GitHub Actions calls it every 5 minutes).
The lots to watch are in lots.txt (one URL per line). Run: python watch.py
Secrets come from environment variables (GitHub repo secrets):
  RESEND_API_KEY  - from resend.com (free)
  ALERT_TO        - where alerts go
Without RESEND_API_KEY the alert is printed instead of emailed.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---- settings -------------------------------------------------------------

LOTS_FILE = Path(__file__).parent / "lots.txt"
STATE_FILE = Path(__file__).parent / "state.json"
ALERT_ON_CLOSE = True          # one email when a lot closes, with the final price
ALERT_ENDING_SOON_MIN = 60     # one email when a lot has this many minutes left (0 = off)
HISTORY_KEEP = 50              # bid changes kept per lot (shown on the dashboard)
EMAIL_FROM = "Bid Watcher <onboarding@resend.dev>"  # Resend test sender: only delivers to your Resend account email

# ---------------------------------------------------------------------------

QUERY = """
query Q($lotId: ID!, $countAsView: Boolean = false) {
  lot(input: $lotId, countAsView: $countAsView) {
    lot {
      lead
      lotNumber
      featuredPicture { thumbnailLocation }
      auction { currencyAbbreviation bidCloseDateTime eventName auctioneer { name } }
      lotState { bidCount highBid minBid isClosed status timeLeftSeconds priceRealized }
    }
  }
}
"""

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"


def read_lots():
    urls = []
    for line in LOTS_FILE.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line and line not in urls:
            urls.append(line)
    return urls


def fetch_lot(url):
    m = re.search(r"https://([^/]+)/lot/(\d+)", url)
    if not m:
        raise ValueError("not a HiBid lot URL (expected https://<site>.hibid.com/lot/<number>/...)")
    host, lot_id = m.groups()
    body = json.dumps({"query": QUERY, "variables": {"lotId": lot_id}}).encode()
    req = urllib.request.Request(
        f"https://{host}/graphql",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": UA,
                 "Origin": f"https://{host}", "Referer": url},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    lot = (((data.get("data") or {}).get("lot") or {}).get("lot"))
    if not lot:
        raise RuntimeError(f"no lot data: {str(data)[:300]}")
    s = lot["lotState"]
    auction = lot.get("auction") or {}
    return {
        "id": lot_id,
        "title": lot["lead"],
        "lot_number": lot["lotNumber"],
        "image": (lot.get("featuredPicture") or {}).get("thumbnailLocation") or "",
        "auction": auction.get("eventName") or "",
        "auctioneer": (auction.get("auctioneer") or {}).get("name") or "",
        "auction_close": auction.get("bidCloseDateTime") or "",  # auctioneer's local time
        "currency": auction.get("currencyAbbreviation") or "",
        "bids": s["bidCount"] or 0,
        "high": s["highBid"] or 0,
        "next_min": s["minBid"] or 0,
        "closed": bool(s["isClosed"]),
        "seconds_left": s["timeLeftSeconds"] or 0,
        "final": s.get("priceRealized") or 0,
    }


def send_email(subject, text):
    key = os.environ.get("RESEND_API_KEY", "").strip()
    to = os.environ.get("ALERT_TO", "").strip()
    if not key or not to:
        print(f"[no RESEND_API_KEY/ALERT_TO, printing instead]\n{subject}\n{text}\n")
        return
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps({"from": EMAIL_FROM, "to": [to], "subject": subject, "text": text}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "bid-watcher"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"emailed: {subject} ({r.status})")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend refused the email: {e.code} {e.read().decode()[:300]}")


def money(amount, cur):
    return f"{amount:,.2f} {cur}".strip()


def fmt_left(seconds):
    if seconds <= 0:
        return "unknown"
    d, rem = divmod(int(seconds), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return " ".join(p for p in (f"{d}d" if d else "", f"{h}h" if h else "", f"{m}m") if p)


def check(url, old, stamp):
    now = fetch_lot(url)
    cur = now["currency"]
    name = f"Lot {now['lot_number']}: {now['title']}"
    print(f"{name} | bids {now['bids']} | high {money(now['high'], cur)} | closed {now['closed']}")

    history = list((old or {}).get("history") or [])
    if old and not history:  # state saved before history existed: seed it with the old values
        history.append({"t": old.get("checked") or stamp, "high": old.get("high", 0), "bids": old.get("bids", 0)})
    if old is None:
        print("  first look, saving baseline (no email)")
        history.append({"t": stamp, "high": now["high"], "bids": now["bids"]})
    else:
        if now["bids"] > old["bids"] or now["high"] > old["high"]:
            history.append({"t": stamp, "high": now["high"], "bids": now["bids"]})
            send_email(
                f"New bid: {money(now['high'], cur)} on {now['title'][:60]}",
                f"{name}\n\n"
                f"High bid: {money(old['high'], cur)} -> {money(now['high'], cur)}\n"
                f"Bids: {old['bids']} -> {now['bids']} ({now['bids'] - old['bids']} new)\n"
                f"Next bid at least: {money(now['next_min'], cur)}\n"
                f"Time left: {fmt_left(now['seconds_left'])}\n\n{url}\n",
            )
        if ALERT_ON_CLOSE and now["closed"] and not old.get("closed"):
            final = now["final"] or now["high"]
            send_email(
                f"Closed: {now['title'][:60]} at {money(final, cur)}",
                f"{name}\n\nAuction closed. Final: {money(final, cur)} after {now['bids']} bids.\n\n{url}\n",
            )
        warned = bool(old.get("warned_soon"))
        soon = ALERT_ENDING_SOON_MIN * 60
        if soon and not warned and not now["closed"] and 0 < now["seconds_left"] <= soon:
            send_email(
                f"Ending soon ({fmt_left(now['seconds_left'])}): {now['title'][:60]}",
                f"{name}\n\nHigh bid {money(now['high'], cur)}, {now['bids']} bids.\n"
                f"Next bid at least {money(now['next_min'], cur)}.\n\n{url}\n",
            )
            warned = True
        now["warned_soon"] = warned

    now["history"] = history[-HISTORY_KEEP:]
    now["url"] = url
    now["added"] = (old or {}).get("added") or stamp
    now["checked"] = stamp
    now["error"] = ""
    return now


def main():
    previous = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    urls = read_lots()
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state, failures = {}, 0
    for url in urls:
        lot_id = (re.search(r"/lot/(\d+)", url) or [None, url])[1]
        old = previous.get(lot_id)
        try:
            state[lot_id] = check(url, old, stamp)
        except Exception as e:  # one bad lot shouldn't stop the others
            print(f"ERROR {url}: {e}", file=sys.stderr)
            failures += 1
            keep = dict(old) if old else {"id": lot_id, "url": url, "title": url, "added": stamp}
            keep["error"] = str(e)[:200]
            state[lot_id] = keep
    # lots removed from lots.txt drop out of state.json

    # 'checked'/'seconds_left' change every run; only write when something real changed,
    # so the repo isn't spammed with a commit every 5 minutes
    def core(s):
        return {k: {f: v for f, v in lot.items() if f not in ("checked", "seconds_left")} for k, lot in s.items()}
    if core(state) != core(previous):
        STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
        print("state.json updated")
    if urls and failures == len(urls):
        sys.exit(1)  # every lot failed: make the GitHub run go red so you notice


if __name__ == "__main__":
    main()
