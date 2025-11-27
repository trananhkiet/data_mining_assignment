# 🔍 Predict AQI - Dự đoán Chất lượng Không khí

Dự án phân tích và dự đoán chất lượng không khí (AQI) dựa trên dữ liệu thời tiết sử dụng kỹ thuật Pattern Mining (FP-Growth) và Machine Learning.

## 📋 Mô tả

Dự án này sử dụng thuật toán FP-Growth để khai thác các quy luật kết hợp (association rules) từ dữ liệu lịch sử về thời tiết và chất lượng không khí. Hệ thống có thể:

- Phân tích mối quan hệ giữa các yếu tố thời tiết và mức độ ô nhiễm không khí
- Dự đoán nguy cơ ô nhiễm dựa trên điều kiện thời tiết hiện tại
- Tích hợp với API OpenWeatherMap để lấy dữ liệu thời tiết real-time
- Hiển thị kết quả phân tích qua giao diện web trực quan

## ✨ Tính năng

- **Pattern Mining**: Sử dụng thuật toán FP-Growth để tìm frequent itemsets và association rules
- **Web UI**: Giao diện web Flask để xem kết quả phân tích và pattern mining
- **Real-time Data**: Tích hợp với OpenWeatherMap API để lấy dữ liệu thời tiết và chất lượng không khí real-time
- **Database Storage**: Lưu trữ patterns vào SQLite database để tăng tốc độ truy vấn
- **Risk Assessment**: Đánh giá mức độ rủi ro ô nhiễm dựa trên các quy luật khớp
- **Data Preprocessing**: Tiền xử lý dữ liệu tự động (xử lý missing values, outliers, feature engineering)

## 🛠️ Cài đặt

### Yêu cầu hệ thống

- Python 3.7 trở lên
- pip (Python package manager)

### Cài đặt dependencies

```bash
pip install flask pandas numpy scikit-learn mlxtend requests python-dotenv
```

Hoặc tạo file `requirements.txt` và cài đặt:

```bash
pip install -r requirements.txt
```

### Cấu hình API (Tùy chọn)

Để sử dụng tính năng lấy dữ liệu real-time từ OpenWeatherMap API:

1. Đăng ký tài khoản tại [OpenWeatherMap](https://openweathermap.org/api)
2. Lấy API key
3. Tạo file `.env` trong thư mục gốc:

```env
OPENWEATHER_API_KEY=your_api_key_here
```

**Lưu ý**: Nếu không có API key, hệ thống vẫn hoạt động bình thường nhưng sẽ không thể lấy dữ liệu real-time từ API.

## 📁 Cấu trúc dự án

```
Predict_AQI/
│
├── app_pattern_mining_ui.py      # Flask web application
├── pattern_mining_weather_aqi.py # Module pattern mining chính
├── weather_aqi_dataset.csv       # Dataset thời tiết và AQI
├── patterns.db                   # SQLite database lưu patterns
│
├── templates/
│   └── pattern_mining_index.html # Giao diện web
│
├── static/
│   ├── style.css                 # CSS styling
│   └── script.js                 # JavaScript cho UI
│
├── AQI_Prediction_Analysis.ipynb # Notebook phân tích và dự đoán
├── EDA_weather_aqi.ipynb         # Notebook khám phá dữ liệu
│
└── README.md                     # File này
```

## 🚀 Sử dụng

### 1. Chạy Web Application

```bash
python app_pattern_mining_ui.py
```

Sau đó mở trình duyệt và truy cập: `http://localhost:5002`

### 2. Sử dụng Module Pattern Mining

```python
from pattern_mining_weather_aqi import WeatherAQIPatternMiner

# Khởi tạo miner
miner = WeatherAQIPatternMiner('weather_aqi_dataset.csv')

# Load và preprocess dữ liệu
miner.load_and_preprocess_data()

# Tạo association rules với FP-Growth
success, message = miner.generate_fp_growth_rules(
    min_support=0.01,  # Minimum support threshold
    min_lift=1.0       # Minimum lift threshold
)

# Phân tích dữ liệu hiện tại
current_data = {
    'hour': 14,
    'wind_speed': 2.5,
    'humidity': 75,
    'pm25': 45,
    'rain': 0,
    'temp': 28,
    'pressure': 1013
}

output = miner.prepare_output_before_llm(current_data, threshold_lift=1.5)
print(output)
```

### 3. Lấy dữ liệu từ API

```python
# Lấy dữ liệu thời tiết và chất lượng không khí real-time
current_data = WeatherAQIPatternMiner.fetch_current_data(
    city='Hanoi',
    country='VN'
)
```

## 📊 Quy trình hoạt động

1. **Preprocessing**: 
   - Load dữ liệu từ CSV
   - Xử lý missing values
   - Xử lý outliers
   - Feature engineering (tạo biến thời gian, mùa, lag features, etc.)

2. **Pattern Mining**:
   - Chuyển đổi dữ liệu thành events/transactions
   - Áp dụng FP-Growth để tìm frequent itemsets
   - Tạo association rules với các metrics (support, confidence, lift)
   - Lưu patterns vào database

3. **Analysis**:
   - So khớp dữ liệu hiện tại với association rules
   - Tính toán risk assessment
   - Chuẩn bị output để gửi vào LLM (nếu cần)

## 🔧 Các tham số quan trọng

- **min_support**: Ngưỡng support tối thiểu cho frequent itemsets (mặc định: 0.01)
- **min_lift**: Ngưỡng lift tối thiểu cho association rules (mặc định: 1.0)
- **threshold_lift**: Ngưỡng lift để lọc rules khi phân tích (mặc định: 1.5)

## 📈 Các loại Events được tạo

- **WIND_LOW**: Tốc độ gió < 1.5 m/s
- **WIND_HIGH**: Tốc độ gió >= 5.0 m/s
- **HUM_HIGH**: Độ ẩm > 85%
- **HUM_LOW**: Độ ẩm < 50%
- **RAIN_LIGHT**: Mưa nhẹ (0 < rain < 2mm)
- **RAIN_HEAVY**: Mưa lớn (rain >= 2mm)
- **TEMP_HIGH**: Nhiệt độ > 30°C
- **TEMP_LOW**: Nhiệt độ < 15°C
- **PRESSURE_HIGH**: Áp suất > 1020 hPa
- **PRESSURE_LOW**: Áp suất < 1000 hPa
- **PM25_GOOD**: PM2.5 <= 12 µg/m³
- **PM25_MODERATE**: 12 < PM2.5 <= 35.4 µg/m³
- **PM25_HIGH**: 35.4 < PM2.5 <= 55.4 µg/m³
- **PM25_VERY_HIGH**: PM2.5 > 150.4 µg/m³
- **NIGHT**: Ban đêm (22h - 5h)

## 🗄️ Database

Hệ thống sử dụng SQLite database (`patterns.db`) để lưu trữ:

- **metadata**: Thông tin về parameters và thời gian cập nhật
- **association_rules**: Các quy luật kết hợp
- **frequent_itemsets**: Các itemsets thường xuyên

Patterns được tự động load từ database khi khởi động nếu parameters khớp, giúp tăng tốc độ xử lý.

## 📝 API Endpoints

### Web API

- `GET /`: Trang chủ
- `POST /api/init`: Khởi tạo FP-Growth rules
- `GET /api/fetch-data`: Lấy dữ liệu từ OpenWeatherMap API
- `POST /api/analyze`: Phân tích dữ liệu hiện tại
- `GET /api/rules`: Lấy danh sách association rules
- `GET /api/itemsets`: Lấy frequent itemsets
- `GET /api/stats`: Lấy thống kê về dữ liệu và rules

## 🔍 Ví dụ Output

```json
{
  "timestamp": "2024-01-15T14:30:00",
  "weather_data": {
    "hour": 14,
    "wind_speed_mps": 2.5,
    "humidity_pct": 75.0,
    "temperature_c": 28.0,
    "pressure_hpa": 1013.0,
    "rain_mm": 0.0,
    "is_night": 0
  },
  "air_quality_data": {
    "pm25_ug_m3": 45.0,
    "pm10_ug_m3": 60.0
  },
  "location": {
    "province": "Hanoi"
  },
  "matched_rules": {
    "count": 3,
    "rules": [...]
  },
  "risk_assessment": {
    "risk_level": "Medium",
    "num_high_lift_rules": 1,
    "avg_lift": 1.65
  }
}
```

## 🧪 Notebooks

- **AQI_Prediction_Analysis.ipynb**: Phân tích chi tiết và xây dựng mô hình dự đoán
- **EDA_weather_aqi.ipynb**: Khám phá dữ liệu (Exploratory Data Analysis)

## 🤝 Đóng góp

Mọi đóng góp đều được chào đón! Vui lòng tạo issue hoặc pull request.

## 📄 License

Dự án này được phát hành dưới giấy phép MIT.

## 👤 Tác giả

Dự án được phát triển bởi [Tên của bạn]

## 🙏 Lời cảm ơn

- OpenWeatherMap API cho dữ liệu thời tiết real-time
- Thư viện mlxtend cho thuật toán FP-Growth
- Flask framework cho web application

---

**Lưu ý**: Dự án này được thiết kế để phân tích và dự đoán chất lượng không khí dựa trên dữ liệu lịch sử. Kết quả chỉ mang tính chất tham khảo và không thay thế cho các hệ thống giám sát chính thức.

