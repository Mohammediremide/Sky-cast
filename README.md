# SkyCast Weather App (Flask + WeatherAPI)

This app supports:
- live current weather
- 7-day forecast
- country selector with countries worldwide

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
WEATHERAPI_KEY=your_real_key
```

Get a free key from: https://www.weatherapi.com/

## 4) Run the app

```powershell
.\.venv\Scripts\python app.py
```

Open: http://127.0.0.1:5000
