"""
Pattern Mining cho Weather AQI Dataset
Sử dụng dữ liệu từ weather_aqi_dataset.csv và xử lý theo AQI_Prediction_Analysis.ipynb
Output: Raw data trước khi gửi vào LLM (không có LLM interpretation)
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import warnings
import sqlite3
import os
import json

warnings.filterwarnings('ignore')

# API imports
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠ requests library not available. Install with: pip install requests")

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Pattern mining imports
try:
    from mlxtend.frequent_patterns import fpgrowth, association_rules
    from mlxtend.preprocessing import TransactionEncoder
    PATTERN_MINING_AVAILABLE = True
except ImportError:
    PATTERN_MINING_AVAILABLE = False
    print("⚠ Pattern mining libraries not available. Install with: pip install mlxtend")


class WeatherAQIPatternMiner:
    """Pattern Mining cho Weather AQI Dataset"""
    
    def __init__(self, data_file: str = 'weather_aqi_dataset.csv', db_file: str = 'patterns.db'):
        self.data_file = data_file
        self.db_file = db_file
        self.df_preprocessed = None
        self.association_rules_df = None
        self.frequent_itemsets = None
        self._init_database()
    
    def _init_database(self):
        """Khởi tạo database và các bảng cần thiết"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Bảng metadata để lưu thông tin về parameters
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                min_support REAL,
                min_lift REAL,
                data_file TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Bảng association_rules
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS association_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER,
                antecedents TEXT,
                consequents TEXT,
                support REAL,
                confidence REAL,
                lift REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Bảng frequent_itemsets
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS frequent_itemsets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                itemset TEXT,
                support REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Index để query nhanh hơn
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rules_lift ON association_rules(lift DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_itemsets_support ON frequent_itemsets(support DESC)')
        
        conn.commit()
        conn.close()
    
    def save_patterns_to_db(self, min_support: float, min_lift: float) -> bool:
        """Lưu patterns vào database"""
        if self.association_rules_df is None or self.frequent_itemsets is None:
            return False
        
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Xóa dữ liệu cũ
            cursor.execute('DELETE FROM association_rules')
            cursor.execute('DELETE FROM frequent_itemsets')
            cursor.execute('DELETE FROM metadata')
            
            # Lưu metadata
            cursor.execute('''
                INSERT INTO metadata (min_support, min_lift, data_file, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (min_support, min_lift, self.data_file, datetime.now().isoformat()))
            
            # Lưu association rules
            for idx, rule in self.association_rules_df.iterrows():
                # Convert frozenset to list for JSON serialization
                ant_set = rule['antecedents']
                cons_set = rule['consequents']
                ant_list = list(ant_set) if isinstance(ant_set, (frozenset, set)) else ant_set
                cons_list = list(cons_set) if isinstance(cons_set, (frozenset, set)) else cons_set
                
                cursor.execute('''
                    INSERT INTO association_rules (rule_id, antecedents, consequents, support, confidence, lift)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    int(idx),
                    json.dumps(ant_list),
                    json.dumps(cons_list),
                    float(rule['support']),
                    float(rule['confidence']),
                    float(rule['lift'])
                ))
            
            # Lưu frequent itemsets
            for idx, row in self.frequent_itemsets.iterrows():
                itemset = row['itemsets']
                itemset_list = list(itemset) if isinstance(itemset, (frozenset, set)) else itemset
                
                cursor.execute('''
                    INSERT INTO frequent_itemsets (itemset, support)
                    VALUES (?, ?)
                ''', (
                    json.dumps(itemset_list),
                    float(row['support'])
                ))
            
            conn.commit()
            conn.close()
            print(f"[OK] Da luu {len(self.association_rules_df)} rules va {len(self.frequent_itemsets)} itemsets vao database")
            return True
            
        except Exception as e:
            print(f"[ERROR] Loi khi luu vao database: {e}")
            return False
    
    def load_patterns_from_db(self, min_support: float = None, min_lift: float = None) -> bool:
        """Load patterns từ database"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Kiểm tra metadata
            cursor.execute('SELECT min_support, min_lift, data_file FROM metadata ORDER BY updated_at DESC LIMIT 1')
            meta = cursor.fetchone()
            
            if meta is None:
                conn.close()
                return False
            
            db_min_support, db_min_lift, db_data_file = meta
            
            # Nếu có yêu cầu parameters cụ thể, check xem có match không
            if min_support is not None and abs(db_min_support - min_support) > 0.001:
                conn.close()
                return False
            if min_lift is not None and abs(db_min_lift - min_lift) > 0.001:
                conn.close()
                return False
            
            # Load association rules
            cursor.execute('''
                SELECT rule_id, antecedents, consequents, support, confidence, lift
                FROM association_rules
                ORDER BY lift DESC
            ''')
            rules_data = cursor.fetchall()
            
            if len(rules_data) == 0:
                conn.close()
                return False
            
            # Tạo DataFrame cho rules
            rules_list = []
            for rule_id, antecedents, consequents, support, confidence, lift in rules_data:
                # Parse từ JSON
                try:
                    ant_list = json.loads(antecedents) if isinstance(antecedents, str) else antecedents
                    cons_list = json.loads(consequents) if isinstance(consequents, str) else consequents
                    
                    # Convert list to frozenset
                    ant_set = frozenset(ant_list) if ant_list else frozenset()
                    cons_set = frozenset(cons_list) if cons_list else frozenset()
                    
                    rules_list.append({
                        'antecedents': ant_set,
                        'consequents': cons_set,
                        'support': support,
                        'confidence': confidence,
                        'lift': lift
                    })
                except Exception as e:
                    print(f"Warning: Could not parse rule {rule_id}: {e}")
                    continue
            
            if rules_list:
                self.association_rules_df = pd.DataFrame(rules_list)
                self.association_rules_df.index = range(len(self.association_rules_df))
            
            # Load frequent itemsets
            cursor.execute('''
                SELECT itemset, support
                FROM frequent_itemsets
                ORDER BY support DESC
            ''')
            itemsets_data = cursor.fetchall()
            
            if len(itemsets_data) > 0:
                itemsets_list = []
                for itemset_str, support in itemsets_data:
                    try:
                        # Parse từ JSON
                        itemset_list = json.loads(itemset_str) if isinstance(itemset_str, str) else itemset_str
                        itemset_set = frozenset(itemset_list) if itemset_list else frozenset()
                        
                        itemsets_list.append({
                            'itemsets': itemset_set,
                            'support': support
                        })
                    except Exception as e:
                        print(f"Warning: Could not parse itemset: {e}")
                        continue
                
                if itemsets_list:
                    self.frequent_itemsets = pd.DataFrame(itemsets_list)
            
            conn.close()
            
            if self.association_rules_df is not None and len(self.association_rules_df) > 0:
                print(f"[OK] Da load {len(self.association_rules_df)} rules va {len(self.frequent_itemsets) if self.frequent_itemsets is not None else 0} itemsets tu database")
                return True
            else:
                return False
                
        except Exception as e:
            print(f"[ERROR] Loi khi load tu database: {e}")
            return False
        
    def load_and_preprocess_data(self) -> bool:
        """
        Load và preprocess dữ liệu theo AQI_Prediction_Analysis.ipynb và EDA_weather_aqi.ipynb
        """
        try:
            print(f"Loading data from {self.data_file}...")
            df = pd.read_csv(self.data_file)
            
            print(f"Original data shape: {df.shape}")
            
            # 1. Xóa các cột có 100% giá trị thiếu
            missing_data = df.isnull().sum()
            missing_percent = (missing_data / len(df)) * 100
            cols_to_drop = missing_data[missing_percent == 100.0].index.tolist()
            if cols_to_drop:
                print(f"Dropping {len(cols_to_drop)} columns with 100% missing values")
                df = df.drop(columns=cols_to_drop)
            
            # 2. Chuyển đổi kiểu dữ liệu thời gian
            df['time'] = pd.to_datetime(df['time'])
            
            # Tạo các biến thời gian
            df['year'] = df['time'].dt.year
            df['month'] = df['time'].dt.month
            df['day'] = df['time'].dt.day
            df['hour'] = df['time'].dt.hour
            df['day_of_week'] = df['time'].dt.dayofweek
            df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
            
            # Tạo biến mùa (cho Việt Nam: Xuân=1, Hạ=2, Thu=3, Đông=4)
            def get_season(month):
                if month in [3, 4, 5]:
                    return 1  # Xuân
                elif month in [6, 7, 8]:
                    return 2  # Hạ
                elif month in [9, 10, 11]:
                    return 3  # Thu
                else:
                    return 4  # Đông
            
            df['season'] = df['month'].apply(get_season)
            
            # 3. Xử lý outliers cho PM2.5 và PM10 (capping trên)
            Q1_pm25 = df['pm2p5'].quantile(0.25)
            Q3_pm25 = df['pm2p5'].quantile(0.75)
            IQR_pm25 = Q3_pm25 - Q1_pm25
            upper_bound_pm25 = Q3_pm25 + 3 * IQR_pm25
            df['pm2p5'] = df['pm2p5'].clip(upper=upper_bound_pm25)
            
            Q1_pm10 = df['pm10'].quantile(0.25)
            Q3_pm10 = df['pm10'].quantile(0.75)
            IQR_pm10 = Q3_pm10 - Q1_pm10
            upper_bound_pm10 = Q3_pm10 + 3 * IQR_pm10
            df['pm10'] = df['pm10'].clip(upper=upper_bound_pm10)
            
            # 4. Feature Engineering
            # Tạo biến tương tác
            df['temp_humidity'] = df['temperature_2m'] * df['relativehumidity_2m']
            df['wind_pressure'] = df['windspeed_10m'] * df['pressure_msl']
            df['temp_wind'] = df['temperature_2m'] * df['windspeed_10m']
            
            # Tạo biến AQI level
            def categorize_aqi_pm25(pm25):
                if pm25 <= 12:
                    return 1  # Tốt
                elif pm25 <= 35.4:
                    return 2  # Trung bình
                elif pm25 <= 55.4:
                    return 3  # Kém
                elif pm25 <= 150.4:
                    return 4  # Xấu
                else:
                    return 5  # Rất xấu
            
            df['aqi_level_pm25'] = df['pm2p5'].apply(categorize_aqi_pm25)
            
            # Tạo biến lag features
            df = df.sort_values(['province', 'time'])
            df['pm2p5_lag1'] = df.groupby('province')['pm2p5'].shift(1)
            df['pm10_lag1'] = df.groupby('province')['pm10'].shift(1)
            
            # Rolling mean
            df['pm2p5_rolling_mean_24h'] = df.groupby('province')['pm2p5'].transform(
                lambda x: x.rolling(window=8, min_periods=1).mean()
            )
            
            # 5. Xử lý missing values
            from sklearn.impute import SimpleImputer
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            numeric_cols = [col for col in numeric_cols if col not in ['pm2p5', 'pm10', 'aqi_level_pm25']]
            
            imputer = SimpleImputer(strategy='median')
            df[numeric_cols] = imputer.fit_transform(df[numeric_cols])
            
            # Xóa các dòng còn thiếu PM2.5 hoặc PM10
            df = df.dropna(subset=['pm2p5', 'pm10'])
            
            # 6. Thêm biến is_night
            df['is_night'] = ((df['hour'] >= 22) | (df['hour'] <= 5)).astype(int)
            
            self.df_preprocessed = df
            print(f"Preprocessed data shape: {df.shape}")
            print(f"Time range: {df['time'].min()} to {df['time'].max()}")
            print(f"Provinces: {df['province'].nunique()}")
            
            return True
            
        except Exception as e:
            print(f"Error loading and preprocessing data: {e}")
            return False
    
    def create_events(self, df: Optional[pd.DataFrame] = None) -> List[List[str]]:
        """
        Tạo events từ dữ liệu cho pattern mining
        Tương tự như trong aqi_data/app.py nhưng điều chỉnh cho weather_aqi_dataset
        """
        if df is None:
            df = self.df_preprocessed
        
        if df is None:
            raise ValueError("No data available. Please load data first.")
        
        events = []
        for _, row in df.iterrows():
            event_items = []
            
            # Weather events
            wind_speed = row.get('windspeed_10m', 999)
            if pd.notna(wind_speed) and wind_speed < 1.5:
                event_items.append('WIND_LOW')
            elif pd.notna(wind_speed) and wind_speed >= 5.0:
                event_items.append('WIND_HIGH')
            
            humidity = row.get('relativehumidity_2m', 0)
            if pd.notna(humidity) and humidity > 85:
                event_items.append('HUM_HIGH')
            elif pd.notna(humidity) and humidity < 50:
                event_items.append('HUM_LOW')
            
            rain = row.get('precipitation', 0)
            if pd.notna(rain) and rain > 0 and rain < 2:
                event_items.append('RAIN_LIGHT')
            elif pd.notna(rain) and rain >= 2:
                event_items.append('RAIN_HEAVY')
            
            if row.get('is_night', 0) == 1:
                event_items.append('NIGHT')
            
            pm25 = row.get('pm2p5', 0)
            if pd.notna(pm25):
                if pm25 > 150.4:
                    event_items.append('PM25_VERY_HIGH')
                elif pm25 > 55.4:
                    event_items.append('PM25_HIGH')
                elif pm25 > 35.4:
                    event_items.append('PM25_MODERATE')
                elif pm25 <= 12:
                    event_items.append('PM25_GOOD')
            
            temp = row.get('temperature_2m', None)
            if pd.notna(temp):
                if temp > 30:
                    event_items.append('TEMP_HIGH')
                elif temp < 15:
                    event_items.append('TEMP_LOW')
            
            pressure = row.get('pressure_msl', None)
            if pd.notna(pressure):
                if pressure > 1020:
                    event_items.append('PRESSURE_HIGH')
                elif pressure < 1000:
                    event_items.append('PRESSURE_LOW')
            
            if event_items:  # Only add non-empty transactions
                events.append(event_items)
        
        return events
    
    def generate_fp_growth_rules(self, min_support: float = 0.01, 
                                 min_lift: float = 1.0,
                                 force_regenerate: bool = False) -> Tuple[bool, str]:
        """
        Áp dụng FP-Growth để tìm frequent itemsets và association rules
        Nếu đã có trong database và parameters match, sẽ load từ database
        """
        if not PATTERN_MINING_AVAILABLE:
            return False, "Pattern mining libraries not available"
        
        # Thử load từ database trước (nếu không force regenerate)
        if not force_regenerate:
            if self.load_patterns_from_db(min_support, min_lift):
                return True, f"Loaded {len(self.association_rules_df)} rules from database"
        
        if self.df_preprocessed is None:
            success = self.load_and_preprocess_data()
            if not success:
                return False, "Failed to load data"
        
        try:
            # Create events
            print("Creating events from data...")
            events = self.create_events()
            print(f"Created {len(events)} events")
            
            if len(events) == 0:
                return False, "No events created"
            
            # Transaction encoding
            print("Encoding transactions...")
            te = TransactionEncoder()
            te_ary = te.fit(events).transform(events)
            df_itemset = pd.DataFrame(te_ary, columns=te.columns_)
            
            print(f"Itemset data shape: {df_itemset.shape}")
            print(f"Items: {list(te.columns_)}")
            
            # Apply FP-Growth
            print(f"Applying FP-Growth with min_support={min_support}...")
            frequent_itemsets = fpgrowth(df_itemset, min_support=min_support, use_colnames=True)
            print(f"Found {len(frequent_itemsets)} frequent itemsets")
            
            self.frequent_itemsets = frequent_itemsets
            
            # Generate association rules
            if len(frequent_itemsets) > 0:
                print("Generating association rules...")
                rules = association_rules(frequent_itemsets, metric="lift", min_threshold=min_lift)
                
                # Filter rules where PM25_HIGH or PM25_VERY_HIGH is in consequent
                pm25_rules = rules[
                    rules['consequents'].apply(
                        lambda x: 'PM25_HIGH' in str(x) or 'PM25_VERY_HIGH' in str(x)
                    )
                ]
                pm25_rules = pm25_rules.sort_values('lift', ascending=False)
                
                self.association_rules_df = pm25_rules
                print(f"Generated {len(pm25_rules)} association rules with PM25_HIGH/VERY_HIGH")
                
                # Lưu vào database
                self.save_patterns_to_db(min_support, min_lift)
                
                return True, f"Generated {len(pm25_rules)} association rules"
            else:
                return False, "No frequent itemsets found"
                
        except Exception as e:
            return False, f"Error generating rules: {str(e)}"
    
    def match_rules_with_conditions(self, current_data: Dict, 
                                   threshold_lift: float = 1.5) -> List[Dict]:
        """
        Match current data với association rules
        Trả về danh sách các rules matched
        """
        if self.association_rules_df is None or len(self.association_rules_df) == 0:
            return []
        
        matched_rules = []
        
        # Extract current conditions
        wind_speed = current_data.get('wind_speed', current_data.get('windspeed_10m', 999))
        humidity = current_data.get('humidity', current_data.get('relativehumidity_2m', 0))
        is_night = current_data.get('is_night', 0)
        pm25 = current_data.get('pm25', current_data.get('pm2p5', 0))
        rain = current_data.get('rain', current_data.get('precipitation', 0))
        temp = current_data.get('temp', current_data.get('temperature_2m', None))
        pressure = current_data.get('pressure', current_data.get('pressure_msl', None))
        hour = current_data.get('hour', 12)
        
        # Check each rule
        for idx, rule in self.association_rules_df.iterrows():
            if rule['lift'] < threshold_lift:
                continue
            
            antecedents = rule['antecedents']
            matched = True
            
            # Check if all antecedents match
            for ant in antecedents:
                if ant == 'WIND_LOW' and wind_speed >= 1.5:
                    matched = False
                    break
                elif ant == 'WIND_HIGH' and wind_speed < 5.0:
                    matched = False
                    break
                elif ant == 'HUM_HIGH' and humidity <= 85:
                    matched = False
                    break
                elif ant == 'HUM_LOW' and humidity >= 50:
                    matched = False
                    break
                elif ant == 'NIGHT' and is_night != 1:
                    matched = False
                    break
                elif ant == 'PM25_HIGH' and pm25 <= 55.4:
                    matched = False
                    break
                elif ant == 'PM25_VERY_HIGH' and pm25 <= 150.4:
                    matched = False
                    break
                elif ant == 'PM25_MODERATE' and (pm25 <= 35.4 or pm25 > 55.4):
                    matched = False
                    break
                elif ant == 'PM25_GOOD' and pm25 > 12:
                    matched = False
                    break
                elif ant == 'RAIN_LIGHT':
                    if not (0 < rain < 2):
                        matched = False
                        break
                elif ant == 'RAIN_HEAVY' and rain < 2:
                    matched = False
                    break
                elif ant == 'TEMP_HIGH' and (temp is None or temp <= 30):
                    matched = False
                    break
                elif ant == 'TEMP_LOW' and (temp is None or temp >= 15):
                    matched = False
                    break
                elif ant == 'PRESSURE_HIGH' and (pressure is None or pressure <= 1020):
                    matched = False
                    break
                elif ant == 'PRESSURE_LOW' and (pressure is None or pressure >= 1000):
                    matched = False
                    break
            
            if matched:
                matched_rules.append({
                    'rule_id': int(idx),
                    'antecedents': str(antecedents),
                    'consequents': str(rule['consequents']),
                    'lift': float(rule['lift']),
                    'confidence': float(rule['confidence']),
                    'support': float(rule['support'])
                })
        
        # Sort by lift
        matched_rules.sort(key=lambda x: x['lift'], reverse=True)
        return matched_rules
    
    def prepare_output_before_llm(self, current_data: Dict, 
                                   matched_rules: Optional[List[Dict]] = None,
                                   threshold_lift: float = 1.5) -> Dict:
        """
        Chuẩn bị output trước khi gửi vào LLM
        Đây là raw data, không có LLM interpretation
        Tương tự như context được build trong aqi_data/app.py nhưng trả về dict thay vì string
        """
        if matched_rules is None:
            matched_rules = self.match_rules_with_conditions(current_data, threshold_lift)
        
        # Extract current conditions
        hour = current_data.get('hour', current_data.get('hour', 12))
        wind_speed = current_data.get('wind_speed', current_data.get('windspeed_10m', 0))
        humidity = current_data.get('humidity', current_data.get('relativehumidity_2m', 0))
        pm25 = current_data.get('pm25', current_data.get('pm2p5', 0))
        rain = current_data.get('rain', current_data.get('precipitation', 0))
        temp = current_data.get('temp', current_data.get('temperature_2m', None))
        pressure = current_data.get('pressure', current_data.get('pressure_msl', None))
        pm10 = current_data.get('pm10', None)
        province = current_data.get('province', None)
        
        # Build output structure
        output = {
            'timestamp': datetime.now().isoformat(),
            'weather_data': {
                'hour': hour,
                'wind_speed_mps': round(wind_speed, 2),
                'humidity_pct': round(humidity, 1),
                'temperature_c': round(temp, 1) if temp is not None else None,
                'pressure_hpa': round(pressure, 1) if pressure is not None else None,
                'rain_mm': round(rain, 2),
                'is_night': current_data.get('is_night', 1 if (22 <= hour or hour <= 5) else 0)
            },
            'air_quality_data': {
                'pm25_ug_m3': round(pm25, 2),
                'pm10_ug_m3': round(pm10, 2) if pm10 is not None else None
            },
            'location': {
                'province': province
            },
            'matched_rules': {
                'count': len(matched_rules),
                'rules': matched_rules[:10] if matched_rules else []  # Top 10 rules
            },
            'risk_assessment': {
                'risk_level': self._calculate_risk_level(matched_rules),
                'num_high_lift_rules': len([r for r in matched_rules if r['lift'] > 2.0]) if matched_rules else 0,
                'avg_lift': np.mean([r['lift'] for r in matched_rules]) if matched_rules else 0.0
            }
        }
        
        # Add source information if available
        if 'source' in current_data:
            output['source'] = current_data['source']
        
        return output
    
    def _calculate_risk_level(self, matched_rules: List[Dict]) -> str:
        """Tính toán risk level dựa trên matched rules"""
        if not matched_rules:
            return 'Low'
        
        high_lift_rules = [r for r in matched_rules if r['lift'] > 2.0]
        avg_lift = np.mean([r['lift'] for r in matched_rules])
        
        if avg_lift > 2.0 or len(high_lift_rules) >= 3:
            return 'Very High'
        elif avg_lift > 1.7 or len(high_lift_rules) >= 2:
            return 'High'
        elif len(matched_rules) >= 2:
            return 'Medium'
        else:
            return 'Low'
    
    def get_frequent_itemsets(self, top_n: int = 20) -> pd.DataFrame:
        """Lấy top N frequent itemsets"""
        if self.frequent_itemsets is None:
            return pd.DataFrame()
        
        return self.frequent_itemsets.sort_values('support', ascending=False).head(top_n)
    
    def get_association_rules(self, top_n: int = 20) -> pd.DataFrame:
        """Lấy top N association rules"""
        if self.association_rules_df is None:
            return pd.DataFrame()
        
        return self.association_rules_df.head(top_n)
    
    @staticmethod
    def fetch_weather_data(city: str = "Hanoi", country: str = "VN") -> Optional[Dict]:
        """
        Fetch real-time weather data from OpenWeatherMap API
        Falls back to demo data if API key is not available
        """
        if not REQUESTS_AVAILABLE:
            print("[WARNING] requests library not available. Using demo data.")
            current_hour = datetime.now().hour
            return {}
        
        # Try to get API key from environment variable
        api_key = os.getenv('OPENWEATHER_API_KEY', '')
        
        if not api_key:
            # Return demo data if no API key
            print("[WARNING] No OpenWeatherMap API key found. Using demo data.")
            current_hour = datetime.now().hour
            return {}
        
        try:
            # OpenWeatherMap API endpoint
            url = "http://api.openweathermap.org/data/2.5/weather"
            params = {
                'q': f"{city},{country}",
                'appid': api_key,
                'units': 'metric'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            current_hour = datetime.now().hour
            
            # Convert wind speed from m/s (OpenWeatherMap uses m/s already, but check)
            wind_speed = data.get('wind', {}).get('speed', 0)
            # OpenWeatherMap already returns wind speed in m/s, no conversion needed
            
            return {
                'wind_speed': wind_speed,  # m/s
                'humidity': data.get('main', {}).get('humidity', 0),
                'rain': data.get('rain', {}).get('1h', 0.0) if 'rain' in data else 0.0,
                'hour': current_hour,
                'temp': data.get('main', {}).get('temp', 0),
                'pressure': data.get('main', {}).get('pressure', 0),
                'source': 'openweathermap'
            }
        except Exception as e:
            print(f"[ERROR] Error fetching weather data: {e}")
            # Fallback to demo data
            current_hour = datetime.now().hour
            return {}
    
    @staticmethod
    def fetch_air_quality_data(city: str = "Hanoi", country: str = "VN") -> Optional[Dict]:
        """
        Fetch real-time air quality data from OpenWeatherMap Air Pollution API
        Falls back to demo data if API key is not available
        """
        if not REQUESTS_AVAILABLE:
            print("[WARNING] requests library not available. Using demo data.")
            return {}
        
        api_key = os.getenv('OPENWEATHER_API_KEY', '')
        
        if not api_key:
            # Return demo data if no API key
            print("[WARNING] No OpenWeatherMap API key found. Using demo data.")
            return {}
        
        try:
            # First get coordinates for the city
            geo_url = "http://api.openweathermap.org/geo/1.0/direct"
            geo_params = {
                'q': f"{city},{country}",
                'appid': api_key
            }
            
            geo_response = requests.get(geo_url, params=geo_params, timeout=10)
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            
            if not geo_data:
                raise ValueError("City not found")
            
            lat = geo_data[0]['lat']
            lon = geo_data[0]['lon']
            
            # Get air pollution data
            aqi_url = "http://api.openweathermap.org/data/2.5/air_pollution"
            aqi_params = {
                'lat': lat,
                'lon': lon,
                'appid': api_key
            }
            
            aqi_response = requests.get(aqi_url, params=aqi_params, timeout=10)
            aqi_response.raise_for_status()
            aqi_data = aqi_response.json()
            
            components = aqi_data.get('list', [{}])[0].get('components', {})
            
            return {
                'pm25': components.get('pm2_5', 0),
                'pm10': components.get('pm10', 0),
                'aqi': aqi_data.get('list', [{}])[0].get('main', {}).get('aqi', 0) * 50,  # Scale 1-5 to approximate AQI
                'source': 'openweathermap'
            }
        except Exception as e:
            print(f"[ERROR] Error fetching air quality data: {e}")
            # Fallback to demo data
            return {}
    
    @staticmethod
    def fetch_current_data(city: str = "Hanoi", country: str = "VN") -> Dict:
        """
        Fetch current weather and air quality data from external APIs
        Returns combined data ready for analysis
        """
        # Fetch weather data
        weather_data = WeatherAQIPatternMiner.fetch_weather_data(city, country)
        
        # Fetch air quality data
        aqi_data = WeatherAQIPatternMiner.fetch_air_quality_data(city, country)
        
        # Combine data with safe defaults
        current_hour = weather_data.get('hour', datetime.now().hour)
        current_data = {
            'wind_speed': weather_data.get('wind_speed', 0),
            'humidity': weather_data.get('humidity', 0),
            'pm25': aqi_data.get('pm25', 0),
            'rain': weather_data.get('rain', 0),
            'hour': current_hour,
            'temp': weather_data.get('temp', 0),
            'pressure': weather_data.get('pressure', 0),
            'pm10': aqi_data.get('pm10', 0),
            'aqi': aqi_data.get('aqi', 0),
            'is_night': 1 if (22 <= current_hour or current_hour <= 5) else 0,
            'province': city,  # Use city as province
            'source': {
                'weather': weather_data.get('source', 'unknown'),
                'air_quality': aqi_data.get('source', 'unknown')
            }
        }
        
        return current_data


# Example usage
if __name__ == '__main__':
    # Initialize miner
    miner = WeatherAQIPatternMiner('weather_aqi_dataset.csv')
    
    # Load and preprocess data
    print("=" * 80)
    print("LOADING AND PREPROCESSING DATA")
    print("=" * 80)
    success = miner.load_and_preprocess_data()
    
    if success:
        # Generate FP-Growth rules
        print("\n" + "=" * 80)
        print("GENERATING FP-GROWTH RULES")
        print("=" * 80)
        success, message = miner.generate_fp_growth_rules(min_support=0.01, min_lift=1.0)
        print(f"Result: {message}")
        
        if success:
            # Show top frequent itemsets
            print("\n" + "=" * 80)
            print("TOP 20 FREQUENT ITEMSETS")
            print("=" * 80)
            print(miner.get_frequent_itemsets(20))
            
            # Show top association rules
            print("\n" + "=" * 80)
            print("TOP 20 ASSOCIATION RULES")
            print("=" * 80)
            print(miner.get_association_rules(20))
            
            # Example: Prepare output for a sample data point
            print("\n" + "=" * 80)
            print("EXAMPLE: OUTPUT BEFORE LLM")
            print("=" * 80)
            
            # Sample current data
            sample_data = {}
            
            output = miner.prepare_output_before_llm(sample_data, threshold_lift=1.5)
            
            import json
            print(json.dumps(output, indent=2, ensure_ascii=False))

