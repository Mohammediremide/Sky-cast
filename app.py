import os

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEATHERAPI_URL = "https://api.weatherapi.com/v1/forecast.json"
COUNTRIESNOW_STATES_URL = "https://countriesnow.space/api/v0.1/countries/states"
COUNTRIESNOW_COUNTRIES_URL = "https://countriesnow.space/api/v0.1/countries/positions"
RESTCOUNTRIES_URL = "https://restcountries.com/v3.1/all?fields=name,cca2"

load_dotenv()

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")


FALLBACK_COUNTRIES = [
    {"code": "NG", "name": "Nigeria"},
    {"code": "US", "name": "United States"},
    {"code": "GB", "name": "United Kingdom"},
    {"code": "CA", "name": "Canada"},
    {"code": "IN", "name": "India"},
]


def _api_key() -> str:
    return (os.getenv("WEATHERAPI_KEY", "") or os.getenv("\ufeffWEATHERAPI_KEY", "")).strip()


def _error(message: str, code: int = 400):
    return jsonify({"error": message}), code


def _countries_from_countriesnow():
    try:
        res = requests.get(COUNTRIESNOW_COUNTRIES_URL, timeout=12)
        res.raise_for_status()
        payload = res.json()
    except (requests.RequestException, ValueError):
        return []

    rows = payload.get("data", []) if isinstance(payload, dict) else []
    countries = []
    for row in rows:
        code = (row.get("iso2") or "").upper().strip()
        name = (row.get("name") or "").strip()
        if len(code) == 2 and name:
            countries.append({"code": code, "name": name})

    countries.sort(key=lambda x: x["name"])
    return countries


def _countries_from_restcountries():
    try:
        res = requests.get(RESTCOUNTRIES_URL, timeout=12)
        res.raise_for_status()
        payload = res.json()
    except (requests.RequestException, ValueError):
        return []

    countries = []
    for item in payload:
        code = (item.get("cca2") or "").upper().strip()
        name = (
            item.get("name", {}).get("common")
            or item.get("name", {}).get("official")
            or ""
        ).strip()
        if len(code) == 2 and name:
            countries.append({"code": code, "name": name})

    countries.sort(key=lambda x: x["name"])
    return countries


def _fetch_countries():
    countries = _countries_from_countriesnow()
    if countries:
        return countries

    countries = _countries_from_restcountries()
    if countries:
        return countries

    return FALLBACK_COUNTRIES


def _fetch_forecast(query: str):
    api_key = _api_key()
    if not api_key:
        return None, _error(
            "Server is missing WEATHERAPI_KEY. Add it to your .env file and restart app.py.",
            500,
        )

    res = requests.get(
        WEATHERAPI_URL,
        params={
            "key": api_key,
            "q": query,
            "days": 7,
            "aqi": "no",
            "alerts": "no",
        },
        timeout=10,
    )

    if res.status_code == 400:
        try:
            provider_message = res.json().get("error", {}).get("message")
        except ValueError:
            provider_message = None
        return None, _error(provider_message or "Location not found.", 404)

    if res.status_code in (401, 403):
        return None, _error("WeatherAPI key is invalid or unauthorized.", 502)

    if res.status_code != 200:
        return None, _error("Failed to fetch weather from WeatherAPI.", 502)

    return res.json(), None


def _fetch_states(country_name: str):
    try:
        res = requests.post(
            COUNTRIESNOW_STATES_URL,
            json={"country": country_name},
            timeout=12,
        )
    except requests.RequestException:
        return []

    if res.status_code != 200:
        return []

    try:
        payload = res.json()
    except ValueError:
        return []

    state_items = payload.get("data", {}).get("states", [])
    state_names = [item.get("name", "").strip() for item in state_items if item.get("name")]
    return sorted(set(state_names))


def _build_payload(data):
    location = data.get("location", {})
    current = data.get("current", {})
    forecast_days = data.get("forecast", {}).get("forecastday", [])

    forecast = []
    for day in forecast_days:
        day_info = day.get("day", {})
        forecast.append(
            {
                "date": day.get("date"),
                "temp_max": round(day_info.get("maxtemp_c", 0)),
                "temp_min": round(day_info.get("mintemp_c", 0)),
                "condition": day_info.get("condition", {}).get("text", "Unknown"),
            }
        )

    return {
        "location": {
            "name": location.get("name", "Unknown"),
            "country": location.get("country", ""),
            "country_name": location.get("country", ""),
            "lat": location.get("lat"),
            "lon": location.get("lon"),
        },
        "current": {
            "timestamp": current.get("last_updated_epoch", 0),
            "temp": round(current.get("temp_c", 0)),
            "feels_like": round(current.get("feelslike_c", 0)),
            "humidity": current.get("humidity", 0),
            "wind_kmh": round(current.get("wind_kph", 0)),
            "condition": current.get("condition", {}).get("text", "Unknown"),
        },
        "forecast": forecast,
    }


@app.after_request
def set_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/countries")
def countries():
    return jsonify({"countries": _fetch_countries()})


@app.route("/api/states")
def states_by_country():
    country_name = (request.args.get("country_name") or "").strip()
    if not country_name:
        return _error("Query parameter 'country_name' is required.")

    states = _fetch_states(country_name)
    return jsonify({"states": states})


@app.route("/api/weather")
def weather_by_city():
    city = (request.args.get("city") or "").strip()
    state = (request.args.get("state") or "").strip()
    country_code = (request.args.get("country") or "").strip().upper()
    country_name = (request.args.get("country_name") or "").strip()

    if not city:
        return _error("Query parameter 'city' is required.")

    location_parts = [city]
    if state:
        location_parts.append(state)
    if country_name:
        location_parts.append(country_name)
    elif country_code:
        location_parts.append(country_code)

    query = ", ".join(location_parts)

    data, err = _fetch_forecast(query)
    if err:
        return err

    return jsonify(_build_payload(data))


@app.route("/api/weather/coords")
def weather_by_coords():
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if lat is None or lon is None:
        return _error("Query parameters 'lat' and 'lon' are required.")

    try:
        lat_val = float(lat)
        lon_val = float(lon)
    except ValueError:
        return _error("Latitude and longitude must be valid numbers.")

    data, err = _fetch_forecast(f"{lat_val},{lon_val}")
    if err:
        return err

    return jsonify(_build_payload(data))


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)

