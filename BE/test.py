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

def test_health_check():
    """Test API health check"""
    print_header("TEST 1: Health Check")
    
    response = requests.get(f"{API_BASE_URL}/")
    
    print(f"Status Code: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))
    
    return response.status_code == 200

def test_get_provinces():
    """Test get provinces endpoint"""
    print_header("TEST 2: Get Supported Provinces")
    
    response = requests.get(f"{API_BASE_URL}/provinces")
    
    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Total Provinces: {data['total']}")
    print(f"Provinces: {', '.join(data['provinces'][:5])}... (showing first 5)")
    
    return response.status_code == 200

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

def test_model_info():
    """Test get model info endpoint"""
    print_header("TEST 4: Get Model Information")
    
    response = requests.get(f"{API_BASE_URL}/model-info")
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nModel Type: {data['model_type']}")
        print(f"Targets: {', '.join(data['targets'])}")
        print(f"Train Date: {data['train_date']}")
        print(f"\nPM2.5 Metrics:")
        print(f"  - Test R²: {data['metrics']['pm2.5']['test_r2']}")
        print(f"  - Test RMSE: {data['metrics']['pm2.5']['test_rmse']}")
        print(f"  - Test MAE: {data['metrics']['pm2.5']['test_mae']}")
        print(f"\nNumber of Features: {data['n_features']}")
        print(f"Feature Names (first 10): {', '.join(data['feature_names'][:10])}...")
        
        return True
    else:
        print(f"\n❌ Error: {response.text}")
        return False

def test_multiple_provinces():
    """Test predictions for multiple provinces"""
    print_header("TEST 5: Multiple Province Predictions")
    
    provinces = ["Ha Noi", "Ho Chi Minh", "Da Nang", "Can Tho"]
    results = []
    
    for province in provinces:
        print(f"\n🔄 Testing {province}...")
        
        response = requests.post(
            f"{API_BASE_URL}/forecast",
            json={"province": province}
        )
        
        if response.status_code == 200:
            data = response.json()
            results.append({
                "province": province,
                "current_pm25": data['current_time']['pm25'],
                "current_pm10": data['current_time']['pm10'],
                "aqi_level": data['current_time']['aqi_level']
            })
            print(f"   ✅ Success: PM2.5={data['current_time']['pm25']}, AQI={data['current_time']['aqi_level']}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    
    # Summary
    print("\n" + "-" * 70)
    print("SUMMARY")
    print("-" * 70)
    for result in results:
        print(f"{result['province']:15} | PM2.5: {result['current_pm25']:6.2f} | PM10: {result['current_pm10']:6.2f} | AQI: {result['aqi_level']}")
    
    return len(results) == len(provinces)

def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("  AQI PM2.5 FORECASTING API - CLIENT TEST")
    print("=" * 70)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Test 1: Health check
    try:
        results.append(("Health Check", test_health_check()))
    except Exception as e:
        print(f"\n❌ Health Check Failed: {e}")
        results.append(("Health Check", False))
    
    # Test 2: Get provinces
    try:
        results.append(("Get Provinces", test_get_provinces()))
    except Exception as e:
        print(f"\n❌ Get Provinces Failed: {e}")
        results.append(("Get Provinces", False))
    
    # Test 3: Single forecast
    try:
        results.append(("Forecast (Ha Noi)", test_forecast_prediction("Ha Noi")))
    except Exception as e:
        print(f"\n❌ Forecast Failed: {e}")
        results.append(("Forecast (Ha Noi)", False))
    
    # Test 4: Model info
    try:
        results.append(("Model Info", test_model_info()))
    except Exception as e:
        print(f"\n❌ Model Info Failed: {e}")
        results.append(("Model Info", False))
    
    # Test 5: Multiple provinces
    try:
        results.append(("Multiple Provinces", test_multiple_provinces()))
    except Exception as e:
        print(f"\n❌ Multiple Provinces Failed: {e}")
        results.append(("Multiple Provinces", False))
    
    # Final summary
    print_header("TEST SUMMARY")
    total = len(results)
    passed = sum(1 for _, success in results if success)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name:25} | {status}")
    
    print("\n" + "-" * 70)
    print(f"Total Tests: {total} | Passed: {passed} | Failed: {total - passed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    print("=" * 70)

if __name__ == "__main__":
    main()