import requests
from flask import Flask, jsonify, render_template

app = Flask(__name__)

API_URL = "https://opendata.maryland.gov/resource/nigh-m2sg.json"
COUNTY = "Prince George's"


def fetch_closures():
    try:
        response = requests.get(API_URL, params={"county": COUNTY}, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return []


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/closures")
def closures():
    data = fetch_closures()
    features = []
    for closure in data:
        lat = closure.get("lat")
        lon = closure.get("long")
        if not lat or not lon:
            continue
        features.append({
            "lat": float(lat),
            "lon": float(lon),
            "incident": closure.get("incident", "No details"),
            "direction": closure.get("direction", ""),
            "lanes": closure.get("lanes", ""),
            "created": closure.get("created", ""),
            "updated": closure.get("updated", ""),
        })
    return jsonify(features)


if __name__ == "__main__":
    app.run(debug=True)
