"""
Flask Web UI cho Pattern Mining Weather AQI
Hiển thị kết quả pattern mining và output trước khi gửi vào LLM
"""

from flask import Flask, render_template, request, jsonify
from pattern_mining_weather_aqi import WeatherAQIPatternMiner
import json
from datetime import datetime

app = Flask(__name__)

# Global miner instance
miner = None

def get_miner():
    """Get or initialize miner instance"""
    global miner
    if miner is None:
        miner = WeatherAQIPatternMiner('weather_aqi_dataset.csv')
        # Thử load patterns từ database khi khởi động
        try:
            if miner.load_patterns_from_db():
                print("[OK] Da load patterns tu database khi khoi dong")
        except Exception as e:
            print(f"⚠ Không thể load từ database: {e}")
    return miner

@app.route('/')
def index():
    """Main page"""
    return render_template('pattern_mining_index.html')

@app.route('/api/init', methods=['POST'])
def init_rules():
    """Initialize FP-Growth rules from historical data or database"""
    try:
        miner = get_miner()
        
        # Get parameters from request (optional)
        # Handle empty JSON body gracefully
        try:
            data = request.json or {}
        except Exception:
            data = {}
        min_support = float(data.get('min_support', 0.01))
        min_lift = float(data.get('min_lift', 1.0))
        force_regenerate = data.get('force_regenerate', False)
        
        # Load data if not loaded
        if miner.df_preprocessed is None:
            success = miner.load_and_preprocess_data()
            if not success:
                return jsonify({
                    'success': False,
                    'message': 'Failed to load data'
                }), 500
        
        # Generate rules (sẽ tự động load từ database nếu có)
        success, message = miner.generate_fp_growth_rules(
            min_support=min_support, 
            min_lift=min_lift,
            force_regenerate=force_regenerate
        )
        
        if success:
            rule_count = len(miner.association_rules_df) if miner.association_rules_df is not None else 0
            itemset_count = len(miner.frequent_itemsets) if miner.frequent_itemsets is not None else 0
            loaded_from_db = 'database' in message.lower()
            return jsonify({
                'success': True,
                'message': message,
                'rule_count': rule_count,
                'itemset_count': itemset_count,
                'loaded_from_db': loaded_from_db
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/fetch-data', methods=['GET'])
def fetch_current_data():
    """
    Fetch current weather and air quality data from external APIs
    """
    try:
        # Get city and country from query params (default to Hanoi)
        city = request.args.get('city', 'Hanoi')
        country = request.args.get('country', 'VN')
        
        # Fetch data using miner's static method
        current_data = WeatherAQIPatternMiner.fetch_current_data(city, country)
        
        return jsonify({
            'success': True,
            'data': current_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error fetching data: {str(e)}'
        }), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_current_data():
    """Analyze current data against association rules and return output before LLM"""
    try:
        miner = get_miner()
        
        if miner.association_rules_df is None or len(miner.association_rules_df) == 0:
            return jsonify({
                'success': False,
                'message': 'Association rules not initialized. Please initialize first.'
            }), 400
        
        # Handle empty JSON body gracefully
        try:
            data = request.json or {}
        except Exception:
            data = {}
        
        # Check if we should fetch data from API
        fetch_from_api = data.get('fetch_from_api', False)
        api_source = None
        if fetch_from_api:
            city = data.get('city', 'Hanoi')
            country = data.get('country', 'VN')
            api_data = WeatherAQIPatternMiner.fetch_current_data(city, country)
            # Store source information
            api_source = api_data.get('source')
            # Merge API data with provided data (provided data takes precedence if exists)
            for key, value in api_data.items():
                if key not in data or data.get(key) is None or data.get(key) == 0:
                    data[key] = value
        
        # Prepare current data dict
        current_data = {
            'hour': int(data.get('hour', datetime.now().hour)),
            'wind_speed': float(data.get('wind_speed', 0)),
            'humidity': float(data.get('humidity', 0)),
            'pm25': float(data.get('pm25', 0)),
            'rain': float(data.get('rain', 0)),
            'temp': float(data.get('temp', 0)) if data.get('temp') else None,
            'pressure': float(data.get('pressure', 0)) if data.get('pressure') else None,
            'pm10': float(data.get('pm10', 0)) if data.get('pm10') else None,
            'province': data.get('province', data.get('city', '')),
            'is_night': 1 if (22 <= int(data.get('hour', datetime.now().hour)) or 
                             int(data.get('hour', datetime.now().hour)) <= 5) else 0
        }
        
        # Add source information if fetched from API
        if api_source:
            current_data['source'] = api_source
        
        # Get output before LLM
        threshold_lift = float(data.get('threshold_lift', 1.5))
        output = miner.prepare_output_before_llm(current_data, threshold_lift=threshold_lift)
        
        # Add source information if available
        if fetch_from_api and 'source' in data:
            output['source'] = data['source']
        elif fetch_from_api:
            # Try to get source from API data
            try:
                api_data = WeatherAQIPatternMiner.fetch_current_data(
                    data.get('city', 'Hanoi'), 
                    data.get('country', 'VN')
                )
                if 'source' in api_data:
                    output['source'] = api_data['source']
            except:
                pass
        
        return jsonify({
            'success': True,
            'output': output
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error analyzing data: {str(e)}'
        }), 500

@app.route('/api/rules', methods=['GET'])
def get_rules():
    """Get all association rules"""
    try:
        miner = get_miner()
        
        if miner.association_rules_df is None or len(miner.association_rules_df) == 0:
            return jsonify({
                'success': False,
                'message': 'Rules not initialized'
            }), 400
        
        rules_list = []
        for idx, rule in miner.association_rules_df.iterrows():
            rules_list.append({
                'rule_id': int(idx),
                'antecedents': str(rule['antecedents']),
                'consequents': str(rule['consequents']),
                'support': float(rule['support']),
                'confidence': float(rule['confidence']),
                'lift': float(rule['lift'])
            })
        
        return jsonify({
            'success': True,
            'rules': rules_list,
            'total': len(rules_list)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting rules: {str(e)}'
        }), 500

@app.route('/api/itemsets', methods=['GET'])
def get_itemsets():
    """Get frequent itemsets"""
    try:
        miner = get_miner()
        
        top_n = int(request.args.get('top_n', 20))
        
        if miner.frequent_itemsets is None or len(miner.frequent_itemsets) == 0:
            return jsonify({
                'success': False,
                'message': 'Frequent itemsets not available'
            }), 400
        
        itemsets = miner.get_frequent_itemsets(top_n)
        
        itemsets_list = []
        for idx, row in itemsets.iterrows():
            itemsets_list.append({
                'itemset': str(row['itemsets']),
                'support': float(row['support'])
            })
        
        return jsonify({
            'success': True,
            'itemsets': itemsets_list,
            'total': len(itemsets_list)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting itemsets: {str(e)}'
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics about the data and rules"""
    try:
        miner = get_miner()
        
        # Check database info
        import sqlite3
        import os
        db_exists = os.path.exists(miner.db_file)
        db_info = None
        
        if db_exists:
            try:
                conn = sqlite3.connect(miner.db_file)
                cursor = conn.cursor()
                cursor.execute('SELECT min_support, min_lift, data_file, updated_at FROM metadata ORDER BY updated_at DESC LIMIT 1')
                meta = cursor.fetchone()
                if meta:
                    cursor.execute('SELECT COUNT(*) FROM association_rules')
                    rule_count_db = cursor.fetchone()[0]
                    cursor.execute('SELECT COUNT(*) FROM frequent_itemsets')
                    itemset_count_db = cursor.fetchone()[0]
                    db_info = {
                        'min_support': float(meta[0]),
                        'min_lift': float(meta[1]),
                        'data_file': meta[2],
                        'updated_at': meta[3],
                        'rule_count': rule_count_db,
                        'itemset_count': itemset_count_db
                    }
                conn.close()
            except Exception as e:
                db_info = {'error': str(e)}
        
        stats = {
            'data_loaded': miner.df_preprocessed is not None,
            'rules_generated': miner.association_rules_df is not None and len(miner.association_rules_df) > 0,
            'itemsets_generated': miner.frequent_itemsets is not None and len(miner.frequent_itemsets) > 0,
            'database': {
                'exists': db_exists,
                'file': miner.db_file,
                'info': db_info
            }
        }
        
        if miner.df_preprocessed is not None:
            stats['data_shape'] = {
                'rows': int(miner.df_preprocessed.shape[0]),
                'columns': int(miner.df_preprocessed.shape[1])
            }
            stats['time_range'] = {
                'start': str(miner.df_preprocessed['time'].min()),
                'end': str(miner.df_preprocessed['time'].max())
            }
            stats['provinces'] = int(miner.df_preprocessed['province'].nunique())
        
        if miner.association_rules_df is not None:
            stats['rule_count'] = int(len(miner.association_rules_df))
        
        if miner.frequent_itemsets is not None:
            stats['itemset_count'] = int(len(miner.frequent_itemsets))
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting stats: {str(e)}'
        }), 500

if __name__ == '__main__':
    print("=" * 80)
    print("Pattern Mining Weather AQI - Web UI")
    print("=" * 80)
    print("Starting server...")
    print("Visit http://localhost:5002 to view the UI")
    print("=" * 80)
    app.run(debug=True, host='0.0.0.0', port=5002)

