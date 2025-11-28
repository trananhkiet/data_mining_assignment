# API

## 1. Run Back End
1. Install virtual environment
Open cmd
```
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
``` 

2. Run app
```$ cd BE
$ python predictor.py
```

## 2. API
Endpoint: forecast_pm25
=> Check bellow section to see input and output example


## 2. Example Input
```
payload = {
    "province": "Ha Noi"
}
```

## 3. Example Output
```
{
  "province": "Ha Noi",
  "current_time": {
    "timestamp": "2024-11-28 14:00:00",
    "pm25": 28.45,
    "pm10": 42.3,
    "aqi_level": "Moderate"
  },
  "forecast_3h": {
    "timestamp": "2024-11-28 17:00:00",
    "pm25": 32.1,
    "pm10": 45.8,
    "aqi_level": "Moderate"
  },
  "forecast_6h": {
    "timestamp": "2024-11-28 20:00:00",
    "pm25": 35.6,
    "pm10": 48.9,
    "aqi_level": "Unhealthy for Sensitive Groups"
  },
  "weather_data": {
    "current": {
      "dewpoint": 20.5,
      "humidity": 75.0,
      "wind_speed": 3.2,
      "pressure": 1013.5
    },
    "forecast_3h": {
      "dewpoint": 21.0,
      "humidity": 78.0
    },
    "forecast_6h": {
      "dewpoint": 21.5,
      "humidity": 80.0
    }
  },
  "model_info": {
    "model_type": "XGBoost",
    "train_date": "2024-11-28 10:30:45",
    "test_r2_pm25": 0.8542,
    "test_r2_pm10": 0.8123,
    "initial_lag": {
      "pm2.5_lag_3h": 26.5,
      "pm10_lag_3h": 40.2,
      "pm2.5_rolling_24h": 27.8
    }
  }
}
```