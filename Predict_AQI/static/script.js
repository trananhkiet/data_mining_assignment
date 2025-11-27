// Refresh stats button
document.getElementById('refreshStatsBtn').addEventListener('click', async () => {
    await loadStats();
});

// Load stats on page load
window.addEventListener('DOMContentLoaded', async () => {
    await loadStats();
});

async function loadStats() {
    const statsDisplay = document.getElementById('statsDisplay');
    statsDisplay.innerHTML = '<p>Đang tải thống kê...</p>';
    
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        if (data.success) {
            const stats = data.stats;
            let html = '<div class="stats-display">';
            
            if (stats.data_loaded) {
                html += `
                    <div class="stat-item">
                        <h4>Dữ Liệu</h4>
                        <p>${stats.data_shape.rows.toLocaleString()} dòng × ${stats.data_shape.columns} cột</p>
                    </div>
                    <div class="stat-item">
                        <h4>Tỉnh/Thành phố</h4>
                        <p>${stats.provinces}</p>
                    </div>
                `;
            } else {
                html += '<div class="stat-item"><h4>Dữ Liệu</h4><p>Chưa tải</p></div>';
            }
            
            if (stats.rules_generated) {
                html += `
                    <div class="stat-item">
                        <h4>Association Rules</h4>
                        <p>${stats.rule_count}</p>
                    </div>
                `;
            } else {
                html += '<div class="stat-item"><h4>Association Rules</h4><p>Chưa tạo</p></div>';
            }
            
            if (stats.itemsets_generated) {
                html += `
                    <div class="stat-item">
                        <h4>Frequent Itemsets</h4>
                        <p>${stats.itemset_count}</p>
                    </div>
                `;
            } else {
                html += '<div class="stat-item"><h4>Frequent Itemsets</h4><p>Chưa tạo</p></div>';
            }
            
            html += '</div>';
            statsDisplay.innerHTML = html;
        } else {
            statsDisplay.innerHTML = `<p style="color: red;">Lỗi: ${data.message}</p>`;
        }
    } catch (error) {
        statsDisplay.innerHTML = `<p style="color: red;">Lỗi: ${error.message}</p>`;
    }
}

// Initialize rules button
document.getElementById('initBtn').addEventListener('click', async () => {
    const btn = document.getElementById('initBtn');
    const status = document.getElementById('initStatus');
    
    btn.disabled = true;
    btn.innerHTML = 'Đang khởi tạo... <span class="loading"></span>';
    status.className = 'status info';
    status.textContent = 'Đang áp dụng FP-Growth trên dữ liệu weather_aqi_dataset.csv...';
    status.style.display = 'block';
    
    try {
        const response = await fetch('/api/init', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            status.className = 'status success';
            status.textContent = `✅ ${data.message} - Tìm thấy ${data.rule_count} quy luật, ${data.itemset_count} itemsets`;
            btn.innerHTML = '✅ Đã Khởi Tạo';
            btn.disabled = true;
            btn.style.background = '#28a745';
            
            // Show rules and itemsets sections
            document.getElementById('rulesSection').style.display = 'block';
            document.getElementById('itemsetsSection').style.display = 'block';
            
            // Refresh stats
            await loadStats();
        } else {
            status.className = 'status error';
            status.textContent = `❌ ${data.message}`;
            btn.innerHTML = 'Khởi tạo Quy Luật';
            btn.disabled = false;
        }
    } catch (error) {
        status.className = 'status error';
        status.textContent = `❌ Lỗi: ${error.message}`;
        btn.innerHTML = 'Khởi tạo Quy Luật';
        btn.disabled = false;
    }
});

// Fetch data from API button
document.getElementById('fetchDataBtn').addEventListener('click', async () => {
    const btn = document.getElementById('fetchDataBtn');
    const status = document.getElementById('fetchStatus');
    const dataDisplay = document.getElementById('fetchedDataDisplay');
    const dataContent = document.getElementById('fetchedDataContent');
    
    const city = document.getElementById('apiCity').value || 'Hanoi';
    const country = document.getElementById('apiCountry').value || 'VN';
    
    btn.disabled = true;
    btn.innerHTML = 'Đang lấy dữ liệu... <span class="loading"></span>';
    status.className = 'status info';
    status.textContent = 'Đang lấy dữ liệu từ API...';
    status.style.display = 'block';
    dataDisplay.style.display = 'none';
    
    try {
        const response = await fetch(`/api/fetch-data?city=${encodeURIComponent(city)}&country=${encodeURIComponent(country)}`);
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            status.className = 'status success';
            status.textContent = `✅ Đã lấy dữ liệu từ ${data.source.weather === 'openweathermap' ? 'OpenWeatherMap API' : 'Demo data'}`;
            
            // Display fetched data
            dataContent.innerHTML = `
                <div class="data-item">
                    <strong>Nguồn:</strong>
                    <span>${data.source.weather === 'openweathermap' ? '🌐 OpenWeatherMap API' : '📊 Demo Data'}</span>
                </div>
                <div class="data-item">
                    <strong>Thời gian:</strong>
                    <span>${new Date(result.timestamp).toLocaleString('vi-VN')}</span>
                </div>
                <div class="data-item">
                    <strong>Giờ:</strong>
                    <span>${data.hour}:00</span>
                </div>
                <div class="data-item">
                    <strong>Tốc độ gió:</strong>
                    <span>${data.wind_speed.toFixed(2)} m/s</span>
                </div>
                <div class="data-item">
                    <strong>Độ ẩm:</strong>
                    <span>${data.humidity.toFixed(1)}%</span>
                </div>
                <div class="data-item">
                    <strong>PM2.5:</strong>
                    <span>${data.pm25.toFixed(2)} µg/m³</span>
                </div>
                <div class="data-item">
                    <strong>PM10:</strong>
                    <span>${data.pm10 ? data.pm10.toFixed(2) + ' µg/m³' : 'N/A'}</span>
                </div>
                <div class="data-item">
                    <strong>Nhiệt độ:</strong>
                    <span>${data.temp ? data.temp.toFixed(1) + '°C' : 'N/A'}</span>
                </div>
                <div class="data-item">
                    <strong>Áp suất:</strong>
                    <span>${data.pressure ? data.pressure.toFixed(1) + ' hPa' : 'N/A'}</span>
                </div>
                <div class="data-item">
                    <strong>Lượng mưa:</strong>
                    <span>${data.rain.toFixed(2)} mm</span>
                </div>
            `;
            
            dataDisplay.style.display = 'block';
            
            // Store fetched data globally
            window.fetchedData = data;
        } else {
            status.className = 'status error';
            status.textContent = `❌ Lỗi: ${result.message}`;
        }
    } catch (error) {
        status.className = 'status error';
        status.textContent = `❌ Lỗi: ${error.message}`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Lấy Dữ Liệu Từ API';
    }
});

// Use fetched data button
document.getElementById('useFetchedDataBtn').addEventListener('click', () => {
    if (window.fetchedData) {
        const data = window.fetchedData;
        document.getElementById('hour').value = data.hour;
        document.getElementById('windSpeed').value = data.wind_speed.toFixed(2);
        document.getElementById('humidity').value = data.humidity.toFixed(1);
        document.getElementById('pm25').value = data.pm25.toFixed(2);
        document.getElementById('pm10').value = data.pm10 ? data.pm10.toFixed(2) : '';
        document.getElementById('rain').value = data.rain.toFixed(2);
        document.getElementById('temp').value = data.temp ? data.temp.toFixed(1) : '';
        document.getElementById('pressure').value = data.pressure ? data.pressure.toFixed(1) : '';
        document.getElementById('province').value = data.province || data.city || '';
        
        alert('✅ Đã điền dữ liệu từ API vào form!');
    }
});

// Analyze button
document.getElementById('analyzeBtn').addEventListener('click', async () => {
    const btn = document.getElementById('analyzeBtn');
    const resultsSection = document.getElementById('resultsSection');
    const useApiData = document.getElementById('useApiData').checked;
    
    // Get input values
    let currentData = {
        hour: parseInt(document.getElementById('hour').value) || 12,
        wind_speed: parseFloat(document.getElementById('windSpeed').value) || 0,
        humidity: parseFloat(document.getElementById('humidity').value) || 0,
        pm25: parseFloat(document.getElementById('pm25').value) || 0,
        pm10: parseFloat(document.getElementById('pm10').value) || 0,
        rain: parseFloat(document.getElementById('rain').value) || 0,
        temp: parseFloat(document.getElementById('temp').value) || null,
        pressure: parseFloat(document.getElementById('pressure').value) || null,
        province: document.getElementById('province').value || '',
        threshold_lift: parseFloat(document.getElementById('thresholdLift').value) || 1.5
    };
    
    // If use API data, add fetch_from_api flag
    if (useApiData) {
        currentData.fetch_from_api = true;
        currentData.city = document.getElementById('apiCity').value || 'Hanoi';
        currentData.country = document.getElementById('apiCountry').value || 'VN';
    }
    
    btn.disabled = true;
    btn.innerHTML = 'Đang phân tích... <span class="loading"></span>';
    
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(currentData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayResults(data.output);
            resultsSection.style.display = 'block';
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        } else {
            alert(`Lỗi: ${data.message}`);
        }
    } catch (error) {
        alert(`Lỗi: ${error.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Phân Tích & Xem Output';
    }
});

function displayResults(output) {
    // Display weather data
    const weatherData = output.weather_data;
    const weatherDisplay = document.getElementById('weatherDataDisplay');
    
    // Check if data source is available in output
    const dataSource = output.source || {};
    const sourceInfo = dataSource.weather ? 
        (dataSource.weather === 'openweathermap' ? '🌐 OpenWeatherMap API' : '📊 Demo Data') : 
        '✍️ Nhập thủ công';
    
    weatherDisplay.innerHTML = `
        <div class="data-item">
            <strong>Nguồn dữ liệu:</strong>
            <span>${sourceInfo}</span>
        </div>
        <div class="data-item">
            <strong>Giờ:</strong>
            <span>${weatherData.hour}:00 ${weatherData.is_night ? '(Ban đêm)' : '(Ban ngày)'}</span>
        </div>
        <div class="data-item">
            <strong>Tốc độ gió:</strong>
            <span>${weatherData.wind_speed_mps} m/s</span>
        </div>
        <div class="data-item">
            <strong>Độ ẩm:</strong>
            <span>${weatherData.humidity_pct}%</span>
        </div>
        <div class="data-item">
            <strong>Nhiệt độ:</strong>
            <span>${weatherData.temperature_c !== null ? weatherData.temperature_c + '°C' : 'N/A'}</span>
        </div>
        <div class="data-item">
            <strong>Áp suất:</strong>
            <span>${weatherData.pressure_hpa !== null ? weatherData.pressure_hpa + ' hPa' : 'N/A'}</span>
        </div>
        <div class="data-item">
            <strong>Lượng mưa:</strong>
            <span>${weatherData.rain_mm} mm</span>
        </div>
    `;
    
    // Display air quality data
    const airQuality = output.air_quality_data;
    const airQualityDisplay = document.getElementById('airQualityDisplay');
    airQualityDisplay.innerHTML = `
        <div class="data-item">
            <strong>PM2.5:</strong>
            <span>${airQuality.pm25_ug_m3} µg/m³</span>
        </div>
        <div class="data-item">
            <strong>PM10:</strong>
            <span>${airQuality.pm10_ug_m3 !== null ? airQuality.pm10_ug_m3 + ' µg/m³' : 'N/A'}</span>
        </div>
    `;
    
    // Display risk assessment
    const risk = output.risk_assessment;
    const riskDisplay = document.getElementById('riskAssessmentDisplay');
    const riskClass = risk.risk_level.toLowerCase().replace(' ', '-');
    riskDisplay.innerHTML = `
        <div class="data-item">
            <strong>Mức độ rủi ro:</strong>
            <span class="risk-badge ${riskClass}">${risk.risk_level}</span>
        </div>
        <div class="data-item">
            <strong>Số rules khớp:</strong>
            <span>${output.matched_rules.count}</span>
        </div>
        <div class="data-item">
            <strong>Rules có lift cao (>2.0):</strong>
            <span>${risk.num_high_lift_rules}</span>
        </div>
        <div class="data-item">
            <strong>Lift trung bình:</strong>
            <span>${risk.avg_lift.toFixed(2)}</span>
        </div>
    `;
    
    // Display matched rules
    const matchedRulesDisplay = document.getElementById('matchedRulesDisplay');
    if (output.matched_rules.count > 0) {
        let rulesHtml = '';
        output.matched_rules.rules.forEach((rule, index) => {
            rulesHtml += `
                <div class="rule-item">
                    <h4>Rule #${rule.rule_id} (Thứ hạng ${index + 1})</h4>
                    <p><strong>Điều kiện:</strong> ${rule.antecedents}</p>
                    <p><strong>Kết quả:</strong> ${rule.consequents}</p>
                    <div class="rule-metrics">
                        <div class="metric">
                            <div class="metric-label">Lift</div>
                            <div class="metric-value">${rule.lift.toFixed(2)}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Confidence</div>
                            <div class="metric-value">${(rule.confidence * 100).toFixed(1)}%</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Support</div>
                            <div class="metric-value">${(rule.support * 100).toFixed(2)}%</div>
                        </div>
                    </div>
                </div>
            `;
        });
        matchedRulesDisplay.innerHTML = rulesHtml;
    } else {
        matchedRulesDisplay.innerHTML = '<p style="color: #666; padding: 20px; text-align: center;">Không có quy luật nào khớp với điều kiện hiện tại.</p>';
    }
    
    // Display raw JSON output
    const rawJsonOutput = document.getElementById('rawJsonOutput');
    rawJsonOutput.textContent = JSON.stringify(output, null, 2);
}

// Show rules button
document.getElementById('showRulesBtn').addEventListener('click', async () => {
    const rulesList = document.getElementById('rulesList');
    const btn = document.getElementById('showRulesBtn');
    
    if (rulesList.innerHTML.trim() !== '') {
        rulesList.innerHTML = '';
        btn.innerHTML = 'Xem Tất Cả Quy Luật';
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = 'Đang tải... <span class="loading"></span>';
    
    try {
        const response = await fetch('/api/rules');
        const data = await response.json();
        
        if (data.success) {
            let html = '';
            data.rules.forEach((rule, index) => {
                html += `
                    <div class="rule-card">
                        <h4>Rule #${rule.rule_id} (Thứ hạng ${index + 1})</h4>
                        <p><strong>Điều kiện:</strong> ${rule.antecedents}</p>
                        <p><strong>Kết quả:</strong> ${rule.consequents}</p>
                        <div class="rule-metrics">
                            <div class="metric">
                                <div class="metric-label">Lift</div>
                                <div class="metric-value">${rule.lift.toFixed(2)}</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Confidence</div>
                                <div class="metric-value">${(rule.confidence * 100).toFixed(1)}%</div>
                            </div>
                            <div class="metric">
                                <div class="metric-label">Support</div>
                                <div class="metric-value">${(rule.support * 100).toFixed(2)}%</div>
                            </div>
                        </div>
                    </div>
                `;
            });
            rulesList.innerHTML = html;
            btn.innerHTML = 'Ẩn Quy Luật';
        } else {
            alert(`Lỗi: ${data.message}`);
        }
    } catch (error) {
        alert(`Lỗi: ${error.message}`);
    } finally {
        btn.disabled = false;
    }
});

// Show itemsets button
document.getElementById('showItemsetsBtn').addEventListener('click', async () => {
    const itemsetsList = document.getElementById('itemsetsList');
    const btn = document.getElementById('showItemsetsBtn');
    
    if (itemsetsList.innerHTML.trim() !== '') {
        itemsetsList.innerHTML = '';
        btn.innerHTML = 'Xem Frequent Itemsets';
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = 'Đang tải... <span class="loading"></span>';
    
    try {
        const response = await fetch('/api/itemsets?top_n=50');
        const data = await response.json();
        
        if (data.success) {
            let html = '';
            data.itemsets.forEach((itemset, index) => {
                html += `
                    <div class="itemset-card">
                        <h4>Itemset #${index + 1}</h4>
                        <p><strong>Items:</strong> ${itemset.itemset}</p>
                        <div class="metric">
                            <div class="metric-label">Support</div>
                            <div class="metric-value">${(itemset.support * 100).toFixed(2)}%</div>
                        </div>
                    </div>
                `;
            });
            itemsetsList.innerHTML = html;
            btn.innerHTML = 'Ẩn Itemsets';
        } else {
            alert(`Lỗi: ${data.message}`);
        }
    } catch (error) {
        alert(`Lỗi: ${error.message}`);
    } finally {
        btn.disabled = false;
    }
});

