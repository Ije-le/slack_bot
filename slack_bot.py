import os
import re
import json
import requests
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SLACK_TOKEN = os.environ.get('SLACK_API_TOKEN')
CHANNEL = "slack-bots"
API_URL = "https://opendata.maryland.gov/resource/nigh-m2sg.json"
COUNTY = "Prince George's"
SEEN_FILE = "seen.json"

client = WebClient(token=SLACK_TOKEN)


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return json.load(f)
    return {}


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f)


def is_since_2026(closure):
    created = closure.get("created", "")
    return bool(re.search(r"\d{2}/\d{2}/202[6-9]", created))


def fetch_closures():
    try:
        response = requests.get(API_URL, params={"county": COUNTY, "$limit": 1000}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return []


def closure_id(closure):
    return f"{closure.get('incident')}|{closure.get('lat')}|{closure.get('long')}"


def format_message(closure, updated=False):
    incident = closure.get("incident", "No details available")
    direction = closure.get("direction", "")
    lanes = closure.get("lanes", "")
    updated_time = closure.get("updated", "")

    prefix = ":arrows_counterclockwise: *Road Closure Update - Prince George's County*" if updated else ":rotating_light: *New Road Closure - Prince George's County*"
    lines = [prefix, f"*Incident:* {incident}"]
    if direction:
        lines.append(f"*Direction:* {direction}")
    if lanes:
        lines.append(f"*Lanes:* {lanes}")
    if updated_time:
        lines.append(f"*Updated:* {updated_time}")
    return "\n".join(lines)


def post_message(text):
    try:
        client.chat_postMessage(channel=CHANNEL, text=text)
        print("Posted to Slack.")
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}")


def main():
    print(f"Running at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    seen = load_seen()
    closures = fetch_closures()
    first_run = len(seen) == 0

    posted = 0
    for closure in closures:
        cid = closure_id(closure)
        current_updated = closure.get("updated")

        if first_run:
            # First run: post all closures since 2026
            if is_since_2026(closure):
                post_message(format_message(closure))
                posted += 1
            seen[cid] = current_updated
        elif cid not in seen:
            # New closure
            post_message(format_message(closure))
            seen[cid] = current_updated
            posted += 1
        elif seen[cid] != current_updated:
            # Updated closure
            post_message(format_message(closure, updated=True))
            seen[cid] = current_updated
            posted += 1

    save_seen(seen)
    print(f"Done. Posted {posted} message(s).")


if __name__ == "__main__":
    main()
