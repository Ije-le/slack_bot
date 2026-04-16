import os
import re
import json
import requests
from datetime import datetime, timezone, timedelta
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


def parse_created_date(created_str):
    """Parse created date string to datetime object."""
    if not created_str:
        return None
    match = re.search(r"(\d{2}/\d{2}/\d{4} \d{1,2}:\d{2} [AP]M)", created_str)
    if not match:
        return None
    try:
        dt = datetime.strptime(match.group(1), "%m/%d/%Y %I:%M %p")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def format_datetime(dt):
    """Format datetime object as 'Thursday, April 16 at 11:20 a.m.'"""
    if not isinstance(dt, datetime):
        return None
    formatted = dt.strftime("%A, %B %d at %I:%M %p")
    # Convert to lowercase and format AM/PM with periods
    formatted = formatted.replace("AM", "a.m.").replace("PM", "p.m.")
    return formatted


def is_created_recently(closure, hours=2):
    created = closure.get("created")
    if not isinstance(created, datetime):
        return False
    now = datetime.now(timezone.utc)
    return (now - created) <= timedelta(hours=hours)


def fetch_closures():
    try:
        response = requests.get(API_URL, params={"county": COUNTY, "$limit": 1000}, timeout=10)
        response.raise_for_status()
        closures = response.json()
        # Convert created and updated fields to datetime objects
        for closure in closures:
            if "created" in closure:
                closure["created"] = parse_created_date(closure["created"])
            if "updated" in closure:
                closure["updated"] = parse_created_date(closure["updated"])
        return closures
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return []


def closure_id(closure):
    return f"{closure.get('incident')}|{closure.get('lat')}|{closure.get('long')}"


def format_message(closure, updated=False):
    incident = closure.get("incident", "No details available")
    direction = closure.get("direction", "")
    lanes = closure.get("lanes", "")
    updated_time = closure.get("updated")
    formatted_time = format_datetime(updated_time) if updated_time else ""

    prefix = ":arrows_counterclockwise: *Road Closure Update - Prince George's County*" if updated else ":rotating_light: *New Road Closure - Prince George's County*"
    lines = [prefix, f"*Incident:* {incident}"]
    if direction:
        lines.append(f"*Direction:* {direction}")
    if lanes:
        lines.append(f"*Lanes:* {lanes}")
    if formatted_time:
        lines.append(f"*Updated:* {formatted_time}")
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

    posted = 0
    for closure in closures:
        cid = closure_id(closure)
        current_updated = closure.get("updated")

        if cid not in seen:
            # New closure — only post if created in the last 2 hours
            seen[cid] = current_updated
            if is_created_recently(closure):
                post_message(format_message(closure))
                posted += 1
        elif seen[cid] != current_updated:
            # Existing closure that was updated
            seen[cid] = current_updated
            post_message(format_message(closure, updated=True))
            posted += 1

    save_seen(seen)
    print(f"Done. Posted {posted} message(s).")


if __name__ == "__main__":
    main()
