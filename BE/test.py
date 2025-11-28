import requests
import json
from datetime import datetime

# API Configuration
API_BASE_URL = "http://localhost:8000"

def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_forecast_prediction(province="Ha Noi"):
    """Test forecast prediction for a specific province"""
    print_header(f"TEST 3: Forecast Prediction for {province}")
    
    payload = {
        "province": province
    }
    
    print(f"Request Payload: {json.dumps(payload, indent=2)}")
    print("\nSending request...")
    
    response = requests.post(
        f"{API_BASE_URL}/forecast",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(data)
        
        print("\n" + "-" * 70)
        print("PREDICTION RESULTS")
        print("-" * 70)
        
        # Current time prediction
        print(f"\n📍 Province: {data['province']}")
        print(f"\n⏰ CURRENT TIME: {data['current_time']['timestamp']}")
        print(f"   PM2.5: {data['current_time']['pm25']} μg/m³")
        print(f"   PM10:  {data['current_time']['pm10']} μg/m³")
        print(f"   AQI Level: {data['current_time']['aqi_level']}")
        
        # +3h forecast
        print(f"\n⏰ FORECAST +3H: {data['forecast_3h']['timestamp']}")
        print(f"   PM2.5: {data['forecast_3h']['pm25']} μg/m³")
        print(f"   PM10:  {data['forecast_3h']['pm10']} μg/m³")
        print(f"   AQI Level: {data['forecast_3h']['aqi_level']}")
        
        # +6h forecast
        print(f"\n⏰ FORECAST +6H: {data['forecast_6h']['timestamp']}")
        print(f"   PM2.5: {data['forecast_6h']['pm25']} μg/m³")
        print(f"   PM10:  {data['forecast_6h']['pm10']} μg/m³")
        print(f"   AQI Level: {data['forecast_6h']['aqi_level']}")
        
        # Weather data
        print(f"\n🌤️  WEATHER DATA (Current):")
        weather = data['weather_data']['current']
        print(f"   Dewpoint: {weather['dewpoint']}°C")
        print(f"   Humidity: {weather['humidity']}%")
        print(f"   Wind Speed: {weather['wind_speed']} m/s")
        print(f"   Pressure: {weather['pressure']} hPa")
        
        # Model info
        print(f"\n🤖 MODEL INFO:")
        model_info = data['model_info']
        print(f"   Model Type: {model_info['model_type']}")
        print(f"   Train Date: {model_info['train_date']}")
        print(f"   PM2.5 Test R²: {model_info['test_r2_pm25']}")
        print(f"   PM10 Test R²: {model_info['test_r2_pm10']}")
        print(f"\n   Initial Lag Features:")
        lag = model_info['initial_lag']
        print(f"   - PM2.5 lag (t-3h): {lag['pm2.5_lag_3h']} μg/m³")
        print(f"   - PM10 lag (t-3h): {lag['pm10_lag_3h']} μg/m³")
        print(f"   - PM2.5 rolling 24h: {lag['pm2.5_rolling_24h']} μg/m³")
        
        return True
    else:
        print(f"\n❌ Error: {response.text}")
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("  AQI PM2.5 FORECASTING API - CLIENT TEST")
    print("=" * 70)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Test 3: Single forecast
    try:
        results.append(("Forecast (Ha Noi)", test_forecast_prediction("Ha Noi")))
    except Exception as e:
        print(f"\n❌ Forecast Failed: {e}")
        results.append(("Forecast (Ha Noi)", False))
    

if __name__ == "__main__":
    main()