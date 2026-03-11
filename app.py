import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OPENWEATHER_GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
OPENWEATHER_REVERSE_URL = "https://api.openweathermap.org/geo/1.0/reverse"
OPENWEATHER_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
OPENWEATHER_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
COUNTRIESNOW_STATES_URL = "https://countriesnow.space/api/v0.1/countries/states"
COUNTRIESNOW_CITIES_URL = "https://countriesnow.space/api/v0.1/countries/state/cities"
COUNTRIESNOW_CITIES_QUERY_URL = "https://countriesnow.space/api/v0.1/countries/state/cities/q"
COUNTRIESNOW_COUNTRIES_URL = "https://countriesnow.space/api/v0.1/countries/positions"
RESTCOUNTRIES_URL = "https://restcountries.com/v3.1/all?fields=name,cca2"

load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

app = Flask(__name__, static_folder=BASE_DIR, static_url_path="")


FALLBACK_COUNTRIES = [
    {"code": "NG", "name": "Nigeria"},
    {"code": "US", "name": "United States"},
    {"code": "GB", "name": "United Kingdom"},
    {"code": "CA", "name": "Canada"},
    {"code": "IN", "name": "India"},
]


def _api_key() -> str:
    return (
        os.getenv("OPENWEATHER_API_KEY", "")
        or os.getenv("OPENWEATHER_KEY", "")
        or os.getenv("\ufeffOPENWEATHER_API_KEY", "")
    ).strip()


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


def _fetch_location_by_query(query: str):
    api_key = _api_key()
    if not api_key:
        return None, _error(
            "Server is missing OPENWEATHER_API_KEY. Add it to your .env file and restart app.py.",
            500,
        )

    try:
        res = requests.get(
            OPENWEATHER_GEO_URL,
            params={"q": query, "limit": 1, "appid": api_key},
            timeout=10,
        )
    except requests.RequestException:
        return None, _error("Failed to reach OpenWeather geocoding.", 502)

    if res.status_code in (401, 403):
        return None, _error("OpenWeather API key is invalid or unauthorized.", 502)

    if res.status_code != 200:
        return None, _error("Failed to fetch location from OpenWeather.", 502)

    try:
        data = res.json()
    except ValueError:
        return None, _error("Unexpected response from OpenWeather.", 502)

    if not data:
        return None, _error("Location not found.", 404)

    return data[0], None


def _fetch_location_by_coords(lat: float, lon: float):
    api_key = _api_key()
    if not api_key:
        return None, _error(
            "Server is missing OPENWEATHER_API_KEY. Add it to your .env file and restart app.py.",
            500,
        )

    try:
        res = requests.get(
            OPENWEATHER_REVERSE_URL,
            params={"lat": lat, "lon": lon, "limit": 1, "appid": api_key},
            timeout=10,
        )
    except requests.RequestException:
        return None, _error("Failed to reach OpenWeather reverse geocoding.", 502)

    if res.status_code in (401, 403):
        return None, _error("OpenWeather API key is invalid or unauthorized.", 502)

    if res.status_code != 200:
        return None, _error("Failed to reverse geocode location.", 502)

    try:
        data = res.json()
    except ValueError:
        return None, _error("Unexpected response from OpenWeather.", 502)

    if not data:
        return None, None

    return data[0], None


def _fetch_forecast(lat: float, lon: float):
    api_key = _api_key()
    if not api_key:
        return None, _error(
            "Server is missing OPENWEATHER_API_KEY. Add it to your .env file and restart app.py.",
            500,
        )

    try:
        res_current = requests.get(
            OPENWEATHER_WEATHER_URL,
            params={"lat": lat, "lon": lon, "units": "metric", "appid": api_key},
            timeout=10,
        )
        res_forecast = requests.get(
            OPENWEATHER_FORECAST_URL,
            params={"lat": lat, "lon": lon, "units": "metric", "appid": api_key},
            timeout=10,
        )
    except requests.RequestException:
        return None, _error("Failed to reach OpenWeather forecast service.", 502)

    if res_current.status_code in (401, 403) or res_forecast.status_code in (401, 403):
        return None, _error("OpenWeather API key is invalid or unauthorized.", 502)

    if res_current.status_code != 200 or res_forecast.status_code != 200:
        return None, _error("Failed to fetch weather from OpenWeather.", 502)

    try:
        data_current = res_current.json()
        data_forecast = res_forecast.json()
    except ValueError:
        return None, _error("Unexpected response from OpenWeather.", 502)

    daily_data = {}
    for item in data_forecast.get("list", []):
        dt_txt = item.get("dt_txt", "").split(" ")[0]
        if dt_txt not in daily_data:
            daily_data[dt_txt] = {
                "dt": item.get("dt"),
                "temp_min": item.get("main", {}).get("temp_min", 0),
                "temp_max": item.get("main", {}).get("temp_max", 0),
                "weather": item.get("weather", [])
            }
        else:
            daily_data[dt_txt]["temp_min"] = min(daily_data[dt_txt]["temp_min"], item.get("main", {}).get("temp_min", 0))
            daily_data[dt_txt]["temp_max"] = max(daily_data[dt_txt]["temp_max"], item.get("main", {}).get("temp_max", 0))

    daily_list = []
    for dt_txt in sorted(daily_data.keys()):
        day_info = daily_data[dt_txt]
        daily_list.append({
            "dt": day_info["dt"],
            "temp": {"min": day_info["temp_min"], "max": day_info["temp_max"]},
            "weather": day_info["weather"]
        })

    combined_data = {
        "current": {
            "dt": data_current.get("dt", 0),
            "temp": data_current.get("main", {}).get("temp", 0),
            "feels_like": data_current.get("main", {}).get("feels_like", 0),
            "humidity": data_current.get("main", {}).get("humidity", 0),
            "wind_speed": data_current.get("wind", {}).get("speed", 0),
            "weather": data_current.get("weather", [])
        },
        "daily": daily_list
    }

    return combined_data, None


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


def _extract_cities(payload):
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("cities"), list):
            return data.get("cities")
    return []


def _fetch_cities(country_name: str, state_name: str):
    try:
        res = requests.post(
            COUNTRIESNOW_CITIES_URL,
            json={"country": country_name, "state": state_name},
            timeout=12,
        )
    except requests.RequestException:
        res = None

    payload = None
    if res is not None and res.status_code == 200:
        try:
            payload = res.json()
        except ValueError:
            payload = None

    cities = _extract_cities(payload) if payload else []

    if cities:
        return sorted(set([str(city).strip() for city in cities if str(city).strip()])), None

    try:
        res = requests.get(
            COUNTRIESNOW_CITIES_QUERY_URL,
            params={"country": country_name, "state": state_name},
            timeout=12,
        )
    except requests.RequestException:
        return [], None

    if res.status_code != 200:
        return [], None

    try:
        payload = res.json()
    except ValueError:
        return [], None

    cities = _extract_cities(payload)
    return sorted(set([str(city).strip() for city in cities if str(city).strip()])), None


def _format_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _build_payload(location, data):
    current = data.get("current", {})
    daily = data.get("daily", [])

    forecast = []
    for day in daily[:5]:
        temp = day.get("temp", {})
        weather_list = day.get("weather", [])
        condition = weather_list[0].get("description") if weather_list else "Unknown"
        forecast.append(
            {
                "date": _format_date(day.get("dt", 0)),
                "temp_max": round(temp.get("max", 0)),
                "temp_min": round(temp.get("min", 0)),
                "condition": condition.title() if isinstance(condition, str) else "Unknown",
            }
        )

    weather_list = current.get("weather", [])
    current_condition = weather_list[0].get("description") if weather_list else "Unknown"
    wind_kmh = round((current.get("wind_speed", 0) or 0) * 3.6)

    return {
        "location": {
            "name": location.get("name", "Unknown"),
            "state": location.get("state", ""),
            "country": location.get("country", ""),
            "country_name": location.get("country", ""),
            "lat": location.get("lat"),
            "lon": location.get("lon"),
        },
        "current": {
            "timestamp": current.get("dt", 0),
            "temp": round(current.get("temp", 0)),
            "feels_like": round(current.get("feels_like", 0)),
            "humidity": current.get("humidity", 0),
            "wind_kmh": wind_kmh,
            "condition": current_condition.title()
            if isinstance(current_condition, str)
            else "Unknown",
        },
        "forecast": forecast,
    }


@app.after_request
def set_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("Unhandled error: %s", error)
    return _error("Unexpected server error. Check server logs.", 500)


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


@app.route("/api/cities")
def cities_by_state():
    country_name = (request.args.get("country_name") or "").strip()
    state_name = (request.args.get("state") or "").strip()

    if not country_name:
        return _error("Query parameter 'country_name' is required.")

    if not state_name:
        return _error("Query parameter 'state' is required.")

    cities, err = _fetch_cities(country_name, state_name)
    if err:
        return err

    return jsonify({"cities": cities})


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
    location, err = _fetch_location_by_query(query)
    if err:
        return err

    data, err = _fetch_forecast(location.get("lat"), location.get("lon"))
    if err:
        return err

    return jsonify(_build_payload(location, data))


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

    location, err = _fetch_location_by_coords(lat_val, lon_val)
    if err:
        return err

    data, err = _fetch_forecast(lat_val, lon_val)
    if err:
        return err

    location = location or {"name": "Your location", "country": ""}
    location.setdefault("lat", lat_val)
    location.setdefault("lon", lon_val)

    return jsonify(_build_payload(location, data))


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)
