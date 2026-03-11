# SkyCast Weather App (Flask + OpenWeather + CountriesNow)

This app supports:
- live current weather
- 5-day forecast
- country selector with countries worldwide
- state selector with cities dropdown

## 1) Create virtual environment

```powershell
python -m venv .venv
```

## 2) Install dependencies (no activation required)

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## 3) Add your API key

1. Copy `.env.example` to `.env`
2. Set your key:

```text
OPENWEATHER_API_KEY=your_real_key
```

Notes:
- OpenWeather One Call 3.0 must be enabled on your plan.
- CountriesNow is used for countries, states, and cities (no key required).

## 4) Run the app

```powershell
.\.venv\Scripts\python app.py
```

Open: http://127.0.0.1:5000
