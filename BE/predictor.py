from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import uvicorn
import requests
import time
import random
from typing import Optional, Dict, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AQI PM2.5 Forecasting API",
    description="API for predicting air quality (PM2.5 & PM10) for current time, +3h, +6h",
    version="3.0.0"
)

# Load models and artifacts at startup
print("Loading models...")
try:
    model_pm25 = joblib.load('saved_models/xgboost_pm25_model.pkl')
    model_pm10 = joblib.load('saved_models/xgboost_pm10_model.pkl')
    scaler = joblib.load('saved_models/scaler.pkl')
    feature_names = joblib.load('saved_models/feature_names.pkl')
    label_encoder = joblib.load('saved_models/label_encoder_province.pkl')
    metadata = joblib.load('saved_models/model_metadata.pkl')
    print("✅ Models loaded successfully!")
except Exception as e:
    print(f"❌ Error loading models: {e}")
    raise

# Province coordinates mapping
VN_PROVINCES_COORDS = {
    "Ha Noi": (21.0285, 105.8542),
    "Hai Phong": (20.8449, 106.6881),
    "Da Nang": (16.0471, 108.2068),
    "Binh Dinh": (13.7820, 109.2197),
    "Can Tho": (10.0452, 105.7469),
    "Ho Chi Minh": (10.8231, 106.6297),
    "An Giang": (10.5216, 105.1259),
    "Ben Tre": (10.2410, 106.3750),
    "Bac Lieu": (9.2941, 105.7278),
    "Bac Giang": (21.2730, 106.1946),
    "Bac Kan": (22.1470, 105.8348),
    "Ba Ria - Vung Tau": (10.5417, 107.2429),
    "Lao Cai": (22.4800, 103.9700),
    "Nghe An": (19.2340, 104.9200),
    "Ninh Thuan": (11.5670, 108.9900),
    "Gia Lai": (13.8070, 108.1090),
    "Ca Mau": (9.1833, 105.1524)
}

# Weather cache
weather_cache = {}
CACHE_EXPIRY_MINUTES = 30

# PM history cache (in production, use Redis or PostgreSQL)
pm_history = {}  # {province: [(timestamp, pm2.5, pm10), ...]}

# User agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
]

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class PredictionRequest(BaseModel):
    province: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "province": "Ha Noi"
            }
        }

class TimeStepPrediction(BaseModel):
    """Prediction at one time point"""
    timestamp: str
    pm25: float
    pm10: float
    aqi_level: str

class ForecastResponse(BaseModel):
    """Response for 3-timestep forecast"""
    province: str
    current_time: TimeStepPrediction
    forecast_3h: TimeStepPrediction
    forecast_6h: TimeStepPrediction
    weather_data: Dict
    model_info: Dict

# ============================================================================
# WEATHER DATA FETCHING
# ============================================================================

def get_random_user_agent():
    """Get random user agent"""
    return random.choice(USER_AGENTS)

def fetch_weather_forecast(lat: float, lon: float, forecast_hours: int = 6, 
                          max_retries: int = 3) -> Optional[Dict]:
    """
    Fetch weather forecast for now, now+3h, now+6h
    Uses forecast API instead of archive API
    
    Args:
        lat: Latitude
        lon: Longitude
        forecast_hours: Hours to forecast (6h)
        max_retries: Number of retries
    
    Returns:
        Dict containing weather data for time points
    """
    # Check cache
    cache_key = f"{lat}_{lon}_forecast_{datetime.now().strftime('%Y%m%d%H')}"
    if cache_key in weather_cache:
        cache_data, cache_time = weather_cache[cache_key]
        if datetime.now() - cache_time < timedelta(minutes=CACHE_EXPIRY_MINUTES):
            logger.info(f"Using cached forecast data for {cache_key}")
            return cache_data
    
    # Use forecast API
    url = "https://api.open-meteo.com/v1/forecast"
    
    # Weather parameters needed (matching the notebook preprocessing)
    hourly_params = [
        "temperature_2m", "relativehumidity_2m", "dewpoint_2m",
        "rain", "showers", "snowfall", "snow_depth",
        "cloudcover", "cloudcover_low", "cloudcover_mid", "cloudcover_high",
        "windspeed_10m", "winddirection_10m",
        "pressure_msl", "surface_pressure"
    ]
    
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(hourly_params),
        "timezone": "Asia/Ho_Chi_Minh",
        "forecast_days": 1
    }
    
    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                delay = random.uniform(2, 5)
                logger.info(f"Retry {attempt}, waiting {delay:.1f}s")
                time.sleep(delay)
            
            headers = {'User-Agent': get_random_user_agent()}
            
            logger.info(f"Fetching weather forecast for {lat},{lon}")
            response = requests.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
                continue
            
            response.raise_for_status()
            data = response.json()
            
            # Parse data for now, now+3h, now+6h
            if 'hourly' in data:
                hourly_data = data['hourly']
                times = pd.to_datetime(hourly_data['time'])
                
                now = datetime.now()
                # Round down to nearest hour
                current_hour = now.replace(minute=0, second=0, microsecond=0)
                
                # Find indices for 3 time points
                time_points = {
                    'now': current_hour,
                    'plus_3h': current_hour + timedelta(hours=3),
                    'plus_6h': current_hour + timedelta(hours=6)
                }
                
                weather_forecast = {}
                
                for label, target_time in time_points.items():
                    # Find nearest index
                    idx = None
                    min_diff = timedelta(days=999)
                    
                    for i, t in enumerate(times):
                        diff = abs(t - target_time)
                        if diff < min_diff:
                            min_diff = diff
                            idx = i
                    
                    if idx is not None and min_diff < timedelta(hours=2):
                        weather_at_time = {}
                        for param in hourly_params:
                            if param in hourly_data:
                                value = hourly_data[param][idx]
                                weather_at_time[param] = value if value is not None else 0.0
                        
                        weather_forecast[label] = {
                            'time': target_time,
                            'data': weather_at_time
                        }
                
                # Cache result
                weather_cache[cache_key] = (weather_forecast, datetime.now())
                
                logger.info(f"Successfully fetched forecast for 3 time points")
                return weather_forecast
            
            logger.warning(f"No forecast data found")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Attempt {attempt} failed: {str(e)}")
            if attempt == max_retries:
                logger.error(f"All attempts failed for forecast")
                return None
    
    return None

# ============================================================================
# LAG FEATURES MANAGEMENT
# ============================================================================

def get_lag_pm_from_history(province: str, target_time: datetime) -> Optional[Dict]:
    """
    Get PM2.5 and PM10 from history at time t-3h
    """
    if province not in pm_history:
        return None
    
    history = pm_history[province]
    
    # Find closest value to target_time
    closest_record = None
    min_diff = timedelta(days=999)
    
    for record_time, pm25, pm10 in history:
        diff = abs(record_time - target_time)
        if diff < min_diff:
            min_diff = diff
            closest_record = (record_time, pm25, pm10)
    
    # Only accept if difference < 6 hours
    if closest_record and min_diff < timedelta(hours=6):
        _, pm25_lag, pm10_lag = closest_record
        return {
            'pm2p5_lag1': pm25_lag,
            'pm10_lag1': pm10_lag
        }
    
    return None

def update_pm_history(province: str, timestamp: datetime, pm25: float, pm10: float):
    """Update PM2.5 and PM10 history"""
    if province not in pm_history:
        pm_history[province] = []
    
    pm_history[province].append((timestamp, pm25, pm10))
    
    # Keep maximum 72h of data
    cutoff_time = datetime.now() - timedelta(hours=72)
    pm_history[province] = [(t, p25, p10) for t, p25, p10 in pm_history[province] 
                           if t > cutoff_time]

def calculate_rolling_mean_24h(province: str, current_time: datetime) -> float:
    """Calculate 24h rolling mean"""
    if province not in pm_history:
        return 25.0  # Default
    
    history = pm_history[province]
    last_24h = [pm25 for t, pm25, _ in history 
               if current_time - timedelta(hours=24) <= t <= current_time]
    
    return np.mean(last_24h) if len(last_24h) > 0 else 25.0

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_season(month: int) -> int:
    """Get season from month (Vietnam seasons)"""
    if month in [3, 4, 5]:
        return 1  # Spring
    elif month in [6, 7, 8]:
        return 2  # Summer
    elif month in [9, 10, 11]:
        return 3  # Autumn
    else:
        return 4  # Winter

def categorize_aqi_pm25(pm25: float) -> str:
    """Categorize AQI from PM2.5"""
    if pm25 <= 12:
        return "Good"
    elif pm25 <= 35.4:
        return "Moderate"
    elif pm25 <= 55.4:
        return "Unhealthy for Sensitive Groups"
    elif pm25 <= 150.4:
        return "Unhealthy"
    else:
        return "Very Unhealthy"

def normalize_province_name(province: str) -> str:
    """Normalize province name"""
    province_mapping = {
        "Ha Noi": "Ha Noi",
        "Hải Phòng": "Hai Phong",
        "Đà Nẵng": "Da Nang",
        "Bình Định": "Binh Dinh",
        "Cần Thơ": "Can Tho",
        "Hồ Chí Minh": "Ho Chi Minh",
        "TP. Hồ Chí Minh": "Ho Chi Minh",
        "An Giang": "An Giang",
        "Bến Tre": "Ben Tre",
        "Bạc Liêu": "Bac Lieu",
        "Bắc Giang": "Bac Giang",
        "Bắc Kạn": "Bac Kan",
        "Bà Rịa - Vũng Tàu": "Ba Ria - Vung Tau",
        "Lào Cai": "Lao Cai",
        "Nghệ An": "Nghe An",
        "Ninh Thuận": "Ninh Thuan",
        "Gia Lai": "Gia Lai",
        "Cà Mau": "Ca Mau"
    }
    return province_mapping.get(province, province)

def normalize_province_name2(province: str) -> str:
    """Normalize province name from space to underscore"""
    province_mapping = {
        "Ha Noi": "Ha_Noi",
        "Hai Phong": "Hai_Phong",
        "Da Nang": "Da_Nang",
        "Binh Dinh": "Binh_Dinh",
        "Can Tho": "Can_Tho",
        "Ho Chi Minh": "Ho_Chi_Minh",
        "An Giang": "An_Giang",
        "Ben Tre": "Ben_Tre",
        "Bac Lieu": "Bac_Lieu",
        "Bac Giang": "Bac_Giang",
        "Bac Kan": "Bac_Kan",
        "Ba Ria - Vung Tau": "Ba_Ria_-_Vung_Tau",
        "Lao Cai": "Lao_Cai",
        "Nghe An": "Nghe_An",
        "Ninh Thuan": "Ninh_Thuan",
        "Gia Lai": "Gia_Lai",
        "Ca Mau": "Ca_Mau"
    }
    return province_mapping.get(province, province)


# ============================================================================
# FEATURE ENGINEERING (Following notebook preprocessing exactly)
# ============================================================================

def create_feature_vector(province: str, target_time: datetime, 
                         weather_data: Dict, pm25_lag: float, pm10_lag: float,
                         pm25_rolling: float) -> pd.DataFrame:
    """
    Create feature vector from real data
    Following the exact preprocessing from the notebook
    """
    province_normalized = normalize_province_name(province)
    
    try:
        province_encoded = label_encoder.transform([normalize_province_name2(province_normalized)])[0]
    except:
        logger.warning(f"Province {province_normalized} not in encoder, using default")
        province_encoded = 0
    
    # Temporal features
    year = target_time.year
    month = target_time.month
    day = target_time.day
    hour = target_time.hour
    day_of_week = target_time.weekday()
    is_weekend = 1 if day_of_week >= 5 else 0
    season = get_season(month)
    
    # Location cluster mapping (from notebook clustering)
    location_cluster_map = {
        "Ha Noi": 0, "Hai Phong": 0, "Bac Giang": 0, "Bac Kan": 0,
        "Da Nang": 1, "Binh Dinh": 1, "Nghe An": 1,
        "Ho Chi Minh": 2, "Can Tho": 2, "Ben Tre": 2,
        "An Giang": 3, "Bac Lieu": 3, "Ca Mau": 3,
        "Ba Ria - Vung Tau": 4, "Lao Cai": 4, "Ninh Thuan": 4, "Gia Lai": 4
    }
    location_cluster = location_cluster_map.get(province_normalized, 0)
    
    # Weather features (use dewpoint_2m instead of temperature_2m as per notebook)
    dewpoint_2m = weather_data.get('dewpoint_2m', 20.0)
    relativehumidity_2m = weather_data.get('relativehumidity_2m', 70.0)
    rain = weather_data.get('rain', 0.0)
    showers = weather_data.get('showers', 0.0)
    snowfall = weather_data.get('snowfall', 0.0)
    snow_depth = weather_data.get('snow_depth', 0.0)
    cloudcover = weather_data.get('cloudcover', 50.0)
    cloudcover_low = weather_data.get('cloudcover_low', 30.0)
    cloudcover_mid = weather_data.get('cloudcover_mid', 20.0)
    cloudcover_high = weather_data.get('cloudcover_high', 10.0)
    windspeed_10m = weather_data.get('windspeed_10m', 3.5)
    winddirection_10m = weather_data.get('winddirection_10m', 180.0)
    pressure_msl = weather_data.get('pressure_msl', 1013.0)
    surface_pressure = weather_data.get('surface_pressure', 1010.0)
    
    # Engineered feature (from notebook: wind_pressure only)
    wind_pressure = windspeed_10m * pressure_msl
    
    # Create dictionary matching exact feature order from notebook
    features_dict = {
        'dewpoint_2m': dewpoint_2m,
        'relativehumidity_2m': relativehumidity_2m,
        'rain': rain,
        'showers': showers,
        'snowfall': snowfall,
        'snow_depth': snow_depth,
        'cloudcover': cloudcover,
        'cloudcover_low': cloudcover_low,
        'cloudcover_mid': cloudcover_mid,
        'cloudcover_high': cloudcover_high,
        'windspeed_10m': windspeed_10m,
        'winddirection_10m': winddirection_10m,
        'pressure_msl': pressure_msl,
        'surface_pressure': surface_pressure,
        'year': year,
        'month': month,
        'day': day,
        'hour': hour,
        'day_of_week': day_of_week,
        'is_weekend': is_weekend,
        'season': season,
        'province_encoded': province_encoded,
        'location_cluster': location_cluster,
        'wind_pressure': wind_pressure,
        'pm2p5_lag1': pm25_lag,
        'pm10_lag1': pm10_lag,
        'pm2p5_rolling_mean_24h': pm25_rolling
    }
    
    df = pd.DataFrame([features_dict])
    df = df[feature_names]
    
    return df

# ============================================================================
# CASCADING PREDICTION
# ============================================================================

def predict_cascading(province: str, weather_forecast: Dict, 
                     initial_lag_pm25: float, initial_lag_pm10: float,
                     initial_rolling_mean: float) -> Dict:
    """
    Cascading prediction: now → now+3h → now+6h
    
    Args:
        province: Province name
        weather_forecast: Dict containing weather data for 3 time points
        initial_lag_pm25: PM2.5 at t-3h
        initial_lag_pm10: PM10 at t-3h
        initial_rolling_mean: Initial 24h rolling mean
    
    Returns:
        Dict containing predictions for 3 time points
    """
    predictions = {}
    
    # Variables to track lag features across steps
    current_pm25_lag = initial_lag_pm25
    current_pm10_lag = initial_lag_pm10
    current_rolling_mean = initial_rolling_mean
    
    time_steps = ['now', 'plus_3h', 'plus_6h']
    
    for step in time_steps:
        if step not in weather_forecast:
            logger.error(f"Missing weather data for {step}")
            continue
        
        target_time = weather_forecast[step]['time']
        weather_data = weather_forecast[step]['data']
        
        # Create features
        features_df = create_feature_vector(
            province, 
            target_time,
            weather_data,
            current_pm25_lag,
            current_pm10_lag,
            current_rolling_mean
        )
        
        # Scale features
        features_scaled = scaler.transform(features_df)
        
        # Predict
        pm25_pred = model_pm25.predict(features_scaled)[0]
        pm10_pred = model_pm10.predict(features_scaled)[0]
        
        # Save prediction
        predictions[step] = {
            'timestamp': target_time.strftime('%Y-%m-%d %H:%M:%S'),
            'pm25': float(pm25_pred),
            'pm10': float(pm10_pred),
            'aqi_level': categorize_aqi_pm25(pm25_pred)
        }
        
        # Update lag features for next step
        # Lag of next step = prediction of current step
        current_pm25_lag = pm25_pred
        current_pm10_lag = pm10_pred
        
        # Update rolling mean (simplified - in practice need full history)
        current_rolling_mean = (current_rolling_mean * 0.9 + pm25_pred * 0.1)
        
        logger.info(f"Predicted {step}: PM2.5={pm25_pred:.2f}, PM10={pm10_pred:.2f}")
    
    return predictions

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "message": "AQI PM2.5 Forecasting API v3.0",
        "status": "running",
        "features": "Cascading forecast (now → +3h → +6h)",
        "model_trained": metadata['train_date'],
        "test_r2_pm25": metadata['model_pm25_metrics']['test_r2'],
        "test_r2_pm10": metadata['model_pm10_metrics']['test_r2']
    }

@app.get("/provinces")
def get_provinces():
    """Get list of supported provinces"""
    provinces = list(VN_PROVINCES_COORDS.keys())
    return {
        "provinces": provinces,
        "total": len(provinces)
    }

@app.post("/forecast", response_model=ForecastResponse)
def forecast_pm25(request: PredictionRequest):
    """
    Predict PM2.5 and PM10 for 3 time points: current, +3h, +6h
    
    **Process:**
    1. Crawl weather data for now, now+3h, now+6h
    2. Get lag PM2.5 and PM10 at t-3h from history
    3. Cascading prediction:
       - Predict(now) → using lag from t-3h
       - Predict(now+3h) → using result of Predict(now) as lag
       - Predict(now+6h) → using result of Predict(now+3h) as lag
    
    Parameters:
    - province: Province name
    
    Returns:
    - PM2.5, PM10 predictions for 3 time points
    """
    try:
        # 1. Normalize province name
        province_normalized = normalize_province_name(request.province)
        
        # 2. Validate province
        if province_normalized not in VN_PROVINCES_COORDS:
            raise HTTPException(
                status_code=400,
                detail=f"Province '{request.province}' not supported. Available: {list(VN_PROVINCES_COORDS.keys())}"
            )
        
        # 3. Get coordinates
        lat, lon = VN_PROVINCES_COORDS[province_normalized]
        
        logger.info(f"Starting forecast for {province_normalized}")
        
        # 4. Fetch weather forecast for now, now+3h, now+6h
        logger.info("Fetching weather forecast...")
        weather_forecast = fetch_weather_forecast(lat, lon, forecast_hours=6)
        
        if weather_forecast is None or len(weather_forecast) < 3:
            raise HTTPException(
                status_code=503,
                detail="Failed to fetch weather forecast. Please try again."
            )
        
        # 5. Get lag PM from history (t-3h)
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        lag_time = now - timedelta(hours=3)
        
        logger.info(f"Looking for lag PM at {lag_time}")
        lag_pm = get_lag_pm_from_history(province_normalized, lag_time)
        
        if lag_pm is None:
            logger.warning("No lag PM in history, using defaults")
            # If no history, use default values
            pm25_lag = 25.0
            pm10_lag = 35.0
        else:
            pm25_lag = lag_pm['pm2p5_lag1']
            pm10_lag = lag_pm['pm10_lag1']
        
        # 6. Calculate 24h rolling mean
        rolling_mean = calculate_rolling_mean_24h(province_normalized, now)
        
        logger.info(f"Initial lag: PM2.5={pm25_lag:.2f}, PM10={pm10_lag:.2f}, Rolling={rolling_mean:.2f}")
        
        # 7. Cascading prediction
        predictions = predict_cascading(
            province_normalized,
            weather_forecast,
            pm25_lag,
            pm10_lag,
            rolling_mean
        )
        
        # 8. Update PM history with prediction results
        for step in ['now', 'plus_3h', 'plus_6h']:
            if step in predictions:
                pred = predictions[step]
                pred_time = datetime.strptime(pred['timestamp'], '%Y-%m-%d %H:%M:%S')
                update_pm_history(
                    province_normalized,
                    pred_time,
                    pred['pm25'],
                    pred['pm10']
                )
        
        # 9. Prepare response
        return ForecastResponse(
            province=request.province,
            current_time=TimeStepPrediction(
                timestamp=predictions['now']['timestamp'],
                pm25=round(predictions['now']['pm25'], 2),
                pm10=round(predictions['now']['pm10'], 2),
                aqi_level=predictions['now']['aqi_level']
            ),
            forecast_3h=TimeStepPrediction(
                timestamp=predictions['plus_3h']['timestamp'],
                pm25=round(predictions['plus_3h']['pm25'], 2),
                pm10=round(predictions['plus_3h']['pm10'], 2),
                aqi_level=predictions['plus_3h']['aqi_level']
            ),
            forecast_6h=TimeStepPrediction(
                timestamp=predictions['plus_6h']['timestamp'],
                pm25=round(predictions['plus_6h']['pm25'], 2),
                pm10=round(predictions['plus_6h']['pm10'], 2),
                aqi_level=predictions['plus_6h']['aqi_level']
            ),
            weather_data={
                "current": {
                    "dewpoint": round(weather_forecast['now']['data'].get('dewpoint_2m', 0), 1),
                    "humidity": round(weather_forecast['now']['data'].get('relativehumidity_2m', 0), 1),
                    "wind_speed": round(weather_forecast['now']['data'].get('windspeed_10m', 0), 1),
                    "pressure": round(weather_forecast['now']['data'].get('pressure_msl', 0), 1)
                },
                "forecast_3h": {
                    "dewpoint": round(weather_forecast['plus_3h']['data'].get('dewpoint_2m', 0), 1),
                    "humidity": round(weather_forecast['plus_3h']['data'].get('relativehumidity_2m', 0), 1),
                },
                "forecast_6h": {
                    "dewpoint": round(weather_forecast['plus_6h']['data'].get('dewpoint_2m', 0), 1),
                    "humidity": round(weather_forecast['plus_6h']['data'].get('relativehumidity_2m', 0), 1),
                }
            },
            model_info={
                "model_type": "XGBoost",
                "train_date": metadata['train_date'],
                "test_r2_pm25": round(metadata['model_pm25_metrics']['test_r2'], 4),
                "test_r2_pm10": round(metadata['model_pm10_metrics']['test_r2'], 4),
                "initial_lag": {
                    "pm2.5_lag_3h": round(pm25_lag, 2),
                    "pm10_lag_3h": round(pm10_lag, 2),
                    "pm2.5_rolling_24h": round(rolling_mean, 2)
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forecast error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Forecast error: {str(e)}")

@app.get("/model-info")
def get_model_info():
    """Get model information"""
    return {
        "model_type": "XGBoost",
        "targets": ["PM2.5", "PM10"],
        "train_date": metadata['train_date'],
        "metrics": {
            "pm2.5": {
                "test_r2": round(metadata['model_pm25_metrics']['test_r2'], 4),
                "test_rmse": round(metadata['model_pm25_metrics']['test_rmse'], 2),
                "test_mae": round(metadata['model_pm25_metrics']['test_mae'], 2)
            },
            "pm10": {
                "test_r2": round(metadata['model_pm10_metrics']['test_r2'], 4),
                "test_rmse": round(metadata['model_pm10_metrics']['test_rmse'], 2),
                "test_mae": round(metadata['model_pm10_metrics']['test_mae'], 2)
            }
        },
        "n_features": metadata['n_features'],
        "feature_names": feature_names
    }

@app.get("/history/{province}")
def get_province_history(province: str):
    """Get PM history for a province"""
    province_normalized = normalize_province_name(province)
    
    if province_normalized not in pm_history:
        return {"province": province, "history": [], "message": "No history available"}
    
    history = pm_history[province_normalized]
    
    return {
        "province": province,
        "total_records": len(history),
        "history": [
            {
                "timestamp": t.strftime('%Y-%m-%d %H:%M:%S'),
                "pm25": round(pm25, 2),
                "pm10": round(pm10, 2)
            }
            for t, pm25, pm10 in sorted(history, key=lambda x: x[0], reverse=True)[:20]
        ]
    }

if __name__ == "__main__":
    uvicorn.run(
        "predictor:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )