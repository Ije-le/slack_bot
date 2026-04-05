import os
import re
import time
import requests
from slack import WebClient
from slack.errors import SlackApiError

SLACK_TOKEN = os.environ.get('SLACK_API_TOKEN')
CHANNEL = "slack-bots"
API_URL = "https://opendata.maryland.gov/resource/nigh-m2sg.json"
COUNTY = "Prince George's"
POLL_INTERVAL = 3600  # 1 hour

client = WebClient(token=SLACK_TOKEN)
seen = {}  # closure_id -> last updated timestamp


def is_since_2026(closure):
    created = closure.get("created", "")
    return bool(re.search(r"\d{2}/\d{2}/202[6-9]", created))


def fetch_closures():
    try:
        response = requests.get(API_URL, params={"county": COUNTY}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return []


def closure_id(closure):
    return (closure.get("incident"), closure.get("lat"), closure.get("long"))


def format_message(closure, updated=False):
    incident = closure.get("incident", "No details available")
    direction = closure.get("direction", "")
    lanes = closure.get("lanes", "")
    updated_time = closure.get("updated", "")

    prefix = ":arrows_counterclockwise: *Road Closure Update*" if updated else ":rotating_light: *Road Closure - Prince George's County*"
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
        print("Posted closure to Slack.")
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}")


def main():
    print("Starting road closure bot...")

    # On first run, post all April 2026 closures and track all current ones
    closures = fetch_closures()
    april_count = 0
    for closure in closures:
        cid = closure_id(closure)
        seen[cid] = closure.get("updated")
        if is_since_2026(closure):
            post_message(format_message(closure))
            april_count += 1
    print(f"Posted {april_count} PG County closure(s) since 2026. Now watching for new ones...")

    while True:
        time.sleep(POLL_INTERVAL)
        closures = fetch_closures()
        for closure in closures:
            cid = closure_id(closure)
            current_updated = closure.get("updated")
            if cid not in seen:
                seen[cid] = current_updated
                post_message(format_message(closure))
            elif seen[cid] != current_updated:
                seen[cid] = current_updated
                post_message(format_message(closure, updated=True))


if __name__ == "__main__":
    main()
