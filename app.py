cursor.execute('''
                UPDATE oauth_tokens 
                SET access_token = ?, expires_at = ?
                WHERE client_key = ?
            ''', (new_tokens['access_token'], expires_at, token_record[1]))
            conn.commit()
            conn.close()
            
            return {
                'access_token': new_tokens['access_token'],
                'company_id': token_record[6],
                'location_id': token_record[5]
            }
    except Exception as e:
        print(f"❌ Token refresh failed: {e}")
    
    return None

def generate_install_url():
    import urllib.parse
    scope_param = urllib.parse.quote_plus(" ".join(SCOPES))
    redirect = urllib.parse.quote_plus(REDIRECT_URI)
    
    return (f"https://marketplace.gohighlevel.com/oauth/chooselocation"
            f"?response_type=code&client_id={CLIENT_ID}&redirect_uri={redirect}"
            f"&app_id={APP_ID}&scope={scope_param}&installToFutureLocations=true")

# Routes
@app.route('/')
def home():
    """Landing page"""
    install_url = generate_install_url()
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Real-Time GHL Lead Analytics</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; 
                   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-align: center; }}
            .card {{ background: rgba(255,255,255,0.95); color: #333; padding: 40px; border-radius: 20px; }}
            .install-btn {{ display: inline-block; background: linear-gradient(45deg, #667eea, #764ba2);
                          color: white; padding: 15px 30px; text-decoration: none; border-radius: 10px;
                          font-size: 18px; font-weight: bold; margin: 20px 0; }}
            .features {{ text-align: left; margin: 30px 0; }}
            .btn {{ padding: 10px 20px; margin: 10px; background: #28a745; color: white; 
                   text-decoration: none; border-radius: 5px; display: inline-block; }}
            .status {{ background: #e8f5e8; padding: 15px; border-radius: 10px; margin: 20px 0; color: #2e7d32; }}
            .webhook {{ background: #fff3e0; padding: 15px; border-radius: 10px; margin: 20px 0; color: #f57c00; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 Real-Time GHL Lead Analytics</h1>
            <p>Advanced lead performance tracking with ALL locations sync</p>
            
            <div class="status">
                <strong>✅ FIXED Issues:</strong><br>
                🔄 Syncs ALL locations (not just 10)<br>
                📊 Full conversion funnel tracking<br>
                ⚡ Real-time webhook processing<br>
                📞 Call attempt & connection tracking<br>
                🎯 Speed-to-lead metrics
            </div>
            
            <div class="webhook">
                <strong>🎯 Webhook Setup Required:</strong><br>
                After installation, configure webhook URL:<br>
                <code>{BASE_URL}/webhook</code><br>
                Subscribe to: ContactCreate, OutboundMessage, InboundMessage
            </div>
            
            <div class="features">
                <h3>📈 Full Conversion Tracking:</h3>
                <ul>
                    <li>📊 <strong>New Leads:</strong> Fresh contacts created</li>
                    <li>📞 <strong>Contacted:</strong> First call attempted</li>
                    <li>✅ <strong>Connected:</strong> Call answered</li>
                    <li>📅 <strong>Sessions:</strong> Appointments booked</li>
                    <li>💰 <strong>Purchases:</strong> Converted customers</li>
                    <li>⚡ <strong>Speed Metrics:</strong> 5min & 1hour response rates</li>
                    <li>🎯 <strong>Best Times:</strong> Optimal calling windows</li>
                </ul>
            </div>
            
            <a href="{install_url}" class="install-btn">🔗 Install on GoHighLevel</a>
            <br>
            <a href="/dashboard" class="btn">📊 View Dashboard</a>
            <a href="/api/sync-all-locations" class="btn">🔄 Sync ALL Locations</a>
            <a href="/health" class="btn">🏥 Health Check</a>
        </div>
    </body>
    </html>
    '''

@app.route('/dashboard')
def dashboard():
    """Enhanced dashboard with full conversion funnel"""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-Time Lead Analytics Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; color: #333;
        }
        .container { max-width: 1800px; margin: 0 auto; padding: 20px; }
        .header {
            background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px);
            border-radius: 20px; padding: 30px; margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); text-align: center;
        }
        .controls {
            background: rgba(255, 255, 255, 0.95); padding: 20px; border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1); margin-bottom: 20px;
            display: flex; gap: 20px; align-items: center; flex-wrap: wrap;
        }
        .control-group { display: flex; align-items: center; gap: 10px; }
        select, button {
            padding: 10px 15px; border: 1px solid #ddd; border-radius: 8px;
            font-size: 14px; background: white;
        }
        button {
            background: linear-gradient(45deg, #667eea, #764ba2); color: white;
            border: none; cursor: pointer; font-weight: bold; transition: all 0.3s ease;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }
        .status-bar {
            background: rgba(255, 255, 255, 0.95); padding: 15px; border-radius: 10px;
            margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;
        }
        .status-indicator {
            display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px;
        }
        .status-connected { background: #28a745; }
        .status-syncing { background: #ffc107; animation: pulse 2s infinite; }
        .status-error { background: #dc3545; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        
        .metrics-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px; margin-bottom: 30px;
        }
        .metric-card {
            background: rgba(255, 255, 255, 0.95); padding: 20px; border-radius: 15px;
            text-align: center; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }
        .metric-card:hover { transform: translateY(-5px); }
        .metric-value {
            font-size: 2.2em; font-weight: bold; margin-bottom: 8px;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .metric-label { color: #666; font-size: 0.9em; font-weight: 500; }
        .metric-sublabel { color: #999; font-size: 0.8em; margin-top: 5px; }
        
        .charts-section {
            display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-bottom: 30px;
        }
        .chart-container {
            background: rgba(255, 255, 255, 0.95); border-radius: 20px; padding: 25px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        .chart-title { font-size: 1.3em; font-weight: bold; margin-bottom: 20px; color: #2c3e50; text-align: center; }
        
        .best-times-table {
            background: rgba(255, 255, 255, 0.95); border-radius: 20px; padding: 25px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        table {
            width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden;
        }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: linear-gradient(45deg, #667eea, #764ba2); color: white; font-weight: bold; }
        tr:hover { background: #f8f9fa; }
        .success-rate { font-weight: bold; color: #28a745; }
        
        @media (max-width: 768px) {
            .charts-section { grid-template-columns: 1fr; }
            .controls { flex-direction: column; align-items: stretch; }
            .metrics-grid { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Real-Time Lead Performance Dashboard</h1>
            <p>Complete conversion funnel tracking with ALL locations</p>
        </div>

        <div class="status-bar">
            <div>
                <span class="status-indicator status-connected" id="dataStatus"></span>
                <span id="dataStatusText">Connected - Last sync: <span id="lastSync">Never</span></span>
            </div>
            <div>
                <button onclick="syncAllLocations()">🏢 Sync ALL Locations</button>
                <button onclick="syncExistingContacts()">📊 Sync Existing Contacts</button>
                <button onclick="refreshData()">🔄 Refresh</button>
            </div>
        </div>

        <div class="controls">
            <div class="control-group">
                <label><strong>Location:</strong></label>
                <select id="locationFilter">
                    <option value="all">All Locations</option>
                </select>
            </div>
            <div class="control-group">
                <label><strong>Time Period:</strong></label>
                <select id="dateRange">
                    <option value="7">Last 7 Days</option>
                    <option value="30" selected>Last 30 Days</option>
                    <option value="90">Last 90 Days</option>
                </select>
            </div>
            <button onclick="updateDashboard()">📊 Update Dashboard</button>
        </div>

        <!-- FULL CONVERSION FUNNEL METRICS -->
        <div class="metrics-grid" id="metricsGrid">
            <!-- Populated by JavaScript -->
        </div>

        <!-- Charts -->
        <div class="charts-section">
            <div class="chart-container">
                <div class="chart-title">🎯 Lead Status Breakdown</div>
                <canvas id="statusChart" width="400" height="300"></canvas>
            </div>
            <div class="chart-container">
                <div class="chart-title">📈 Conversion Funnel</div>
                <canvas id="funnelChart" width="400" height="300"></canvas>
            </div>
        </div>

        <!-- Best Call Times -->
        <div class="best-times-table">
            <div class="chart-title">🎯 Best Call Times (Real Data)</div>
            <table id="bestTimesTable">
                <thead>
                    <tr>
                        <th>Day</th>
                        <th>Hour</th>
                        <th>Total Calls</th>
                        <th>Connected</th>
                        <th>Success Rate</th>
                        <th>Avg Duration</th>
                    </tr>
                </thead>
                <tbody>
                    <!-- Populated by JavaScript -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let dashboardData = {};
        let currentFilters = { location: 'all', dateRange: '30' };

        document.addEventListener('DOMContentLoaded', function() {
            loadLocations();
            loadDashboard();
        });

        async function loadLocations() {
            try {
                const response = await fetch('/api/locations');
                const locations = await response.json();
                
                const select = document.getElementById('locationFilter');
                select.innerHTML = '<option value="all">All Locations (' + locations.length + ')</option>';
                
                locations.forEach(location => {
                    const option = document.createElement('option');
                    option.value = location.id;
                    option.textContent = location.name + (location.address ? ' - ' + location.address : '');
                    select.appendChild(option);
                });
                
                console.log('✅ Loaded ' + locations.length + ' locations');
            } catch (error) {
                console.error('❌ Error loading locations:', error);
            }
        }

        async function loadDashboard() {
            updateDataStatus('syncing', 'Loading real-time data...');
            
            try {
                const params = new URLSearchParams({
                    location: currentFilters.location,
                    days: currentFilters.dateRange
                });
                
                const response = await fetch('/api/realtime-stats?' + params);
                dashboardData = await response.json();
                
                updateMetrics();
                updateStatusChart();
                updateFunnelChart();
                updateBestTimesTable();
                updateDataStatus('connected', 'Last sync: ' + new Date().toLocaleTimeString());
                
            } catch (error) {
                console.error('❌ Error loading dashboard:', error);
                updateDataStatus('error', 'Error loading data');
            }
        }

        function updateDataStatus(status, text) {
            const indicator = document.getElementById('dataStatus');
            const statusText = document.getElementById('dataStatusText');
            
            indicator.className = 'status-indicator status-' + status;
            statusText.innerHTML = text;
        }

        function updateMetrics() {
            const metricsGrid = document.getElementById('metricsGrid');
            metricsGrid.innerHTML = '';

            // FULL CONVERSION FUNNEL METRICS
            const metrics = [
                { 
                    label: 'Total Leads', 
                    value: dashboardData.total_leads || 0,
                    sublabel: 'New contacts created'
                },
                { 
                    label: 'Contacted', 
                    value: dashboardData.leads_called || 0,
                    sublabel: 'First call attempted'
                },
                { 
                    label: 'Connected', 
                    value: dashboardData.leads_connected || 0,
                    sublabel: 'Call answered'
                },
                { 
                    label: 'Connection Rate', 
                    value: (dashboardData.connection_rate || 0) + '%',
                    sublabel: 'Calls that connected'
                },
                { 
                    label: 'Avg Time to Call', 
                    value: (dashboardData.avg_minutes_to_first_call || 0) + 'm',
                    sublabel: (dashboardData.avg_hours_to_first_call || 0) + 'h total'
                },
                { 
                    label: 'Avg Time to Connect', 
                    value: Math.round(dashboardData.avg_minutes_to_first_connection || 0) + 'm',
                    sublabel: (dashboardData.avg_hours_to_first_connection || 0) + 'h total'
                },
                { 
                    label: 'Calls <5min', 
                    value: (dashboardData.speed_to_call_rate || 0) + '%',
                    sublabel: (dashboardData.calls_within_5min || 0) + ' lightning calls'
                },
                { 
                    label: 'Calls <1hr', 
                    value: (dashboardData.hourly_call_rate || 0) + '%',
                    sublabel: (dashboardData.calls_within_1hour || 0) + ' same hour'
                }
            ];

            metrics.forEach(function(metric) {
                const card = document.createElement('div');
                card.className = 'metric-card';
                card.innerHTML = '<div class="metric-value">' + metric.value + '</div>' +
                    '<div class="metric-label">' + metric.label + '</div>' +
                    '<div class="metric-sublabel">' + metric.sublabel + '</div>';
                metricsGrid.appendChild(card);
            });
        }

        function updateStatusChart() {
            const ctx = document.getElementById('statusChart').getContext('2d');
            
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['New Leads', 'Contacted', 'Connected', 'Sessions', 'Purchased'],
                    datasets: [{
                        data: [
                            dashboardData.new_leads || 0,
                            dashboardData.contacted_leads || 0,
                            dashboardData.connected_leads || 0,
                            dashboardData.session_booked_leads || 0,
                            dashboardData.purchased_leads || 0
                        ],
                        backgroundColor: [
                            '#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            });
        }

        function updateFunnelChart() {
            const ctx = document.getElementById('funnelChart').getContext('2d');
            
            const total = dashboardData.total_leads || 0;
            const called = dashboardData.leads_called || 0;
            const connected = dashboardData.leads_connected || 0;
            const sessions = dashboardData.leads_to_session || 0;
            const purchases = dashboardData.leads_to_purchase || 0;

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Total Leads', 'Called', 'Connected', 'Sessions', 'Purchases'],
                    datasets: [{
                        label: 'Count',
                        data: [total, called, connected, sessions, purchases],
                        backgroundColor: [
                            'rgba(102, 126, 234, 0.8)',
                            'rgba(118, 75, 162, 0.8)',
                            'rgba(52, 152, 219, 0.8)',
                            'rgba(46, 204, 113, 0.8)',
                            'rgba(241, 196, 15, 0.8)'
                        ]
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    plugins: { legend: { display: false } }
                }
            });
        }

        function updateBestTimesTable() {
            const tbody = document.querySelector('#bestTimesTable tbody');
            tbody.innerHTML = '';

            const bestTimes = dashboardData.best_times || [];
            
            if (bestTimes.length === 0) {
                const row = document.createElement('tr');
                row.innerHTML = '<td colspan="6" style="text-align: center; color: #999;">No call data yet. Start making calls to see best times!</td>';
                tbody.appendChild(row);
                return;
            }

            bestTimes.slice(0, 10).forEach(function(item) {
                const row = document.createElement('tr');
                const hour12 = item.hour === 0 ? '12 AM' : 
                             item.hour < 12 ? item.hour + ' AM' :
                             item.hour === 12 ? '12 PM' : (item.hour - 12) + ' PM';
                
                row.innerHTML = '<td>' + item.day_name + '</td>' +
                    '<td>' + hour12 + '</td>' +
                    '<td>' + item.total_calls + '</td>' +
                    '<td>' + item.successful_calls + '</td>' +
                    '<td class="success-rate">' + item.success_rate + '%</td>' +
                    '<td>' + item.avg_duration + 'min</td>';
                tbody.appendChild(row);
            });
        }

        function updateDashboard() {
            currentFilters.location = document.getElementById('locationFilter').value;
            currentFilters.dateRange = document.getElementById('dateRange').value;
            loadDashboard();
        }

        async function syncAllLocations() {
            updateDataStatus('syncing', 'Syncing ALL GHL locations...');
            try {
                const response = await fetch('/api/sync-all-locations', { method: 'POST' });
                const result = await response.json();
                
                if (result.status === 'success') {
                    updateDataStatus('connected', 'Synced ' + result.count + ' locations!');
                    loadLocations();
                } else {
                    updateDataStatus('error', 'Location sync failed');
                }
            } catch (error) {
                updateDataStatus('error', 'Location sync failed');
            }
        }

        async function syncExistingContacts() {
            updateDataStatus('syncing', 'Syncing existing contacts...');
            try {
                const response = await fetch('/api/sync-existing-contacts', { method: 'POST' });
                const result = await response.json();
                
                if (result.status === 'success') {
                    updateDataStatus('connected', 'Synced ' + result.total_contacts + ' contacts!');
                    loadDashboard();
                } else {
                    updateDataStatus('error', 'Contact sync failed');
                }
            } catch (error) {
                updateDataStatus('error', 'Contact sync failed');
            }
        }

        async function refreshData() {
            updateDataStatus('syncing', 'Refreshing all data...');
            try {
                await syncAllLocations();
                setTimeout(() => {
                    loadDashboard();
                }, 1000);
            } catch (error) {
                updateDataStatus('error', 'Refresh failed');
            }
        }

        // Auto-refresh every 30 seconds
        setInterval(function() {
            if (document.visibilityState === 'visible') {
                loadDashboard();
            }
        }, 30000);
    </script>
</body>
</html>
    '''

@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback and sync ALL locations"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f"<h1>❌ Installation Error</h1><p>{error}</p><a href='/'>Try Again</a>"
    
    if not code:
        return "<h1>❌ No authorization code received</h1><a href='/'>Try Again</a>"
    
    try:
        resp = requests.post("https://services.leadconnectorhq.com/oauth/token", data={
            "grant_type": "authorization_code", "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET, "code": code, "redirect_uri": REDIRECT_URI
        })
        
        tokens = resp.json()
        if "error" in tokens:
            return f"<h1>❌ Token Error</h1><p>{tokens.get('error_description')}</p>"
        
        client_key = tokens.get('companyId') or tokens.get('locationId')
        expires_at = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
        
        conn = sqlite3.connect(analytics.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO oauth_tokens 
            (client_key, access_token, refresh_token, expires_at, location_id, company_id, scope)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (client_key, tokens['access_token'], tokens['refresh_token'],
              expires_at, tokens.get('locationId'), tokens.get('companyId'), tokens.get('scope')))
        conn.commit()
        conn.close()
        
        # FIXED: Sync ALL locations with pagination
        locations_synced = analytics.sync_all_locations_paginated(tokens['access_token'], tokens.get('companyId'))
        
        return f'''
        <div style="text-align: center; padding: 50px; font-family: Arial;">
            <h1>✅ Installation Successful!</h1>
            <p>Real-Time Lead Analytics is connected and ALL locations synced!</p>
            <p><strong>Client Key:</strong> {client_key}</p>
            <p><strong>Locations Synced:</strong> {locations_synced}</p>
            <div style="background: #e8f5e8; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <strong>🎯 IMPORTANT - Set Up Webhooks:</strong><br>
                1. Go to GHL Settings → Integrations → Webhooks<br>
                2. Create webhook with URL: <code>{BASE_URL}/webhook</code><br>
                3. Subscribe to: ContactCreate, OutboundMessage, InboundMessage<br>
                4. Create a test contact to verify tracking!
            </div>
            <div style="background: #e3f2fd; padding: 15px; border-radius: 10px; margin: 20px 0; color: #1565c0;">
                <strong>📊 Next Steps:</strong><br>
                • View dashboard to see all {locations_synced} locations<br>
                • Sync existing contacts for historical data<br>
                • Make test calls to build performance analytics
            </div>
            <a href="/dashboard" style="display: inline-block; background: #28a745; color: white; 
               padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px;">
                🚀 Open Dashboard ({locations_synced} Locations)
            </a>
        </div>
        '''
        
    except Exception as e:
        return f"<h1>❌ Installation Failed</h1><p>{str(e)}</p><a href='/'>Try Again</a>"

# API Routes
@app.route('/api/locations')
def api_locations():
    """Get ALL real GHL locations"""
    locations = analytics.get_real_locations()
    return jsonify(locations)

@app.route('/api/sync-all-locations', methods=['POST'])
def api_sync_all_locations():
    """FIXED: Sync ALL locations with pagination"""
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    count = analytics.sync_all_locations_paginated(token_data['access_token'], token_data.get('company_id'))
    return jsonify({'status': 'success', 'count': count, 'message': f'Synced ALL {count} locations!'})

@app.route('/api/sync-existing-contacts', methods=['POST'])
def api_sync_existing_contacts():
    """Sync existing contacts from all locations"""
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    try:
        locations = analytics.get_real_locations()
        total_contacts = 0
        
        for location in locations:
            count = analytics.sync_existing_contacts(token_data['access_token'], location['id'])
            total_contacts += count
            time.sleep(0.1)  # Rate limiting
        
        return jsonify({
            'status': 'success', 
            'total_contacts': total_contacts,
            'locations_processed': len(locations),
            'message': f'Synced {total_contacts} existing contacts from {len(locations)} locations'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/realtime-stats')
def api_realtime_stats():
    """Get FULL conversion funnel statistics"""
    location_id = request.args.get('location', 'all')
    days = int(request.args.get('days', 30))
    
    data = analytics.get_enhanced_stats(location_id, days)
    
    response = data['stats'].copy()
    response['best_times'] = data['best_times']
    
    return jsonify(response)

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """ENHANCED webhook handler for real-time tracking"""
    try:
        webhook_data = request.json
        event_type = webhook_data.get('type')
        contact_id = webhook_data.get('contactId') or webhook_data.get('contact', {}).get('id')
        location_id = webhook_data.get('locationId')
        
        print(f"🎯 WEBHOOK: {event_type} | Contact: {contact_id} | Location: {location_id}")
        
        # Always log for debugging
        analytics.log_webhook_event(event_type, contact_id, location_id, webhook_data)
        
        if event_type == 'ContactCreate':
            contact = webhook_data.get('contact', {})
            if contact.get('id') and location_id:
                success = analytics.record_contact_created(contact, location_id)
                if success:
                    print(f"✅ NEW LEAD TRACKED: {contact.get('id')}")
                return jsonify({'status': 'success', 'message': 'Contact created and tracked'})
        
        elif event_type == 'OutboundMessage':
            # Track call attempts
            message_type = webhook_data.get('messageType', '').lower()
            if 'call' in message_type and contact_id and location_id:
                analytics.record_call_attempt(contact_id, location_id)
                print(f"📞 CALL ATTEMPT: {contact_id}")
                return jsonify({'status': 'success', 'message': 'Call attempt tracked'})
        
        elif event_type == 'InboundMessage':
            # Track call connections
            message_type = webhook_data.get('messageType', '').lower()
            if 'call' in message_type and contact_id and location_id:
                duration = webhook_data.get('duration', 0)
                if duration > 0:
                    analytics.record_call_connected(contact_id, location_id, duration_minutes=duration//60)
                    print(f"✅ CALL CONNECTED: {contact_id} ({duration}s)")
                return jsonify({'status': 'success', 'message': 'Call connection tracked'})
        
        elif event_type == 'ContactUpdate':
            # Track contact updates (potential status changes)
            contact = webhook_data.get('contact', {})
            if contact_id and location_id:
                print(f"📝 CONTACT UPDATE: {contact_id}")
                return jsonify({'status': 'success', 'message': 'Contact update noted'})
        
        return jsonify({'status': 'success', 'message': f'Webhook {event_type} received and logged'})
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ WEBHOOK ERROR: {error_msg}")
        
        try:
            analytics.log_webhook_event(
                event_type or 'unknown', 
                contact_id or 'unknown', 
                location_id or 'unknown', 
                webhook_data or {}, 
                error_msg
            )
        except:
            pass
        
        return jsonify({'error': error_msg}), 500

@app.route('/api/webhook-debug')
def api_webhook_debug():
    """Debug endpoint to see recent webhook events"""
    conn = sqlite3.connect(analytics.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT event_type, contact_id, location_id, processed, error_message, received_at
        FROM webhook_events 
        ORDER BY received_at DESC 
        LIMIT 50
    ''')
    
    events = cursor.fetchall()
    conn.close()
    
    debug_data = [{
        'event_type': row[0],
        'contact_id': row[1],
        'location_id': row[2],
        'processed': bool(row[3]),
        'error_message': row[4],
        'received_at': row[5]
    } for row in events]
    
    return jsonify(debug_data)

@app.route('/api/test-contact', methods=['POST'])
def api_test_contact():
    """Create a test contact for verification"""
    try:
        # Create a test contact record
        test_contact = {
            'id': f'test_{int(time.time())}',
            'firstName': 'Test',
            'lastName': 'Contact',
            'email': 'test@example.com',
            'phone': '+1234567890',
            'source': 'manual_test',
            'dateAdded': datetime.now().isoformat()
        }
        
        # Use first available location
        locations = analytics.get_real_locations()
        if locations:
            location_id = locations[0]['id']
            success = analytics.record_contact_created(test_contact, location_id)
            
            if success:
                return jsonify({
                    'status': 'success',
                    'contact_id': test_contact['id'],
                    'location_id': location_id,
                    'message': 'Test contact created successfully'
                })
        
        return jsonify({'status': 'error', 'message': 'No locations available'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/health')
def health_check():
    """Comprehensive health check"""
    conn = sqlite3.connect(analytics.db_path)
    cursor = conn.cursor()
    
    # Check database health
    cursor.execute('SELECT COUNT(*) FROM contact_journey')
    total_contacts = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM ghl_locations WHERE is_active = TRUE')
    total_locations = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM webhook_events WHERE received_at >= date("now", "-1 day")')
    recent_webhooks = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM webhook_events WHERE received_at >= date("now", "-1 hour")')
    recent_hour_webhooks = cursor.fetchone()[0]
    
    # Get recent contact activity
    cursor.execute('SELECT COUNT(*) FROM contact_journey WHERE created_at >= date("now", "-1 day")')
    recent_contacts = cursor.fetchone()[0]
    
    conn.close()
    
    # Check token status
    token_data = get_valid_token()
    token_status = 'valid' if token_data else 'missing'
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'base_url': BASE_URL,
        'redirect_uri': REDIRECT_URI,
        'webhook_url': f'{BASE_URL}/webhook',
        'version': '3.0.0 - FIXED SYNC',
        'database_health': {
            'total_contacts': total_contacts,
            'total_locations': total_locations,
            'recent_webhooks_24h': recent_webhooks,
            'recent_webhooks_1h': recent_hour_webhooks,
            'recent_contacts_24h': recent_contacts
        },
        'oauth_status': token_status,
        'scopes_configured': SCOPES,
        'features': [
            'ALL_LOCATIONS_SYNC_FIXED',
            'FULL_CONVERSION_FUNNEL',
            'PAGINATED_API_CALLS',
            'REAL_TIME_WEBHOOK_PROCESSING',
            'ENHANCED_CONTACT_TRACKING',
            'SPEED_TO_LEAD_METRICS',
            'CALL_PERFORMANCE_ANALYTICS'
        ],
        'webhook_setup': {
            'url': f'{BASE_URL}/webhook',
            'required_events': ['ContactCreate', 'OutboundMessage', 'InboundMessage'],
            'debug_endpoint': f'{BASE_URL}/api/webhook-debug'
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Real-Time GHL Lead Analytics v3.0 - FIXED SYNC starting on port {port}")
    print(f"📍 Base URL: {BASE_URL}")
    print(f"🔗 Redirect URI: {REDIRECT_URI}")
    print(f"📨 Webhook URL: {BASE_URL}/webhook")
    print(f"📊 Dashboard: {BASE_URL}/dashboard")
    print(f"🔍 Debug: {BASE_URL}/api/webhook-debug")
    print(f"🏥 Health: {BASE_URL}/health")
    print(f"🎯 Scopes: {', '.join(SCOPES)}")
    print(f"✅ FIXES: ALL locations sync, Full conversion funnel, Real-time tracking")
    
    app.run(host='0.0.0.0', port=port, debug=False)# app.py - Real-Time GHL Lead Analytics - FIXED SYNC & TRACKING
import os
import json
import time
import requests
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from dataclasses import dataclass
from typing import Optional, List, Dict
import threading

app = Flask(__name__)

# Configuration
CLIENT_ID = os.getenv('GHL_CLIENT_ID', '6886150802562ad87b4e2dc0-mdlog30p')
CLIENT_SECRET = os.getenv('GHL_CLIENT_SECRET', '3162ed43-8498-48a3-a8b4-8a60e980f318')
APP_ID = os.getenv('GHL_APP_ID', '66c70d3c319d92c0772350b9')
WEBHOOK_SECRET = os.getenv('GHL_WEBHOOK_SECRET', 'your-webhook-secret')

# URLs
BASE_URL = "https://alti-speed-to-lead.onrender.com"
REDIRECT_URI = f"{BASE_URL}/oauth/callback"

# Updated Scopes - Correct Format
SCOPES = [
    "oauth.readonly",
    "contacts.readonly",
    "contacts.write",
    "conversations.readonly",
    "conversations/message.readonly",
    "locations.readonly",
    "locations/customFields.readonly",
    "locations/tasks.readonly",
    "locations/tags.readonly"
]

@dataclass
class LeadEvent:
    contact_id: str
    event_type: str
    timestamp: datetime
    location_id: str
    source: str = None
    duration_minutes: Optional[int] = None
    outcome: Optional[str] = None
    metadata: Dict = None

class RealTimeLeadAnalytics:
    def __init__(self, db_path="realtime_lead_analytics.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enhanced contact tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contact_journey (
                contact_id TEXT PRIMARY KEY,
                location_id TEXT NOT NULL,
                location_name TEXT,
                contact_name TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                contact_source TEXT,
                
                -- Critical timestamps
                created_at DATETIME NOT NULL,
                first_call_attempted_at DATETIME,
                first_call_connected_at DATETIME,
                first_session_booked_at DATETIME,
                first_purchase_at DATETIME,
                
                -- Time intervals (in minutes)
                minutes_to_first_call INTEGER,
                minutes_to_first_connection INTEGER,
                minutes_to_first_session INTEGER,
                minutes_to_purchase INTEGER,
                
                -- Counters
                total_calls_attempted INTEGER DEFAULT 0,
                total_calls_connected INTEGER DEFAULT 0,
                total_sessions_booked INTEGER DEFAULT 0,
                
                -- Status tracking
                current_status TEXT DEFAULT 'new_lead',
                opportunity_stage TEXT,
                tags TEXT,
                custom_fields TEXT,
                
                last_activity_at DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Real locations from GHL - FIXED for pagination
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ghl_locations (
                location_id TEXT PRIMARY KEY,
                location_name TEXT NOT NULL,
                address TEXT,
                phone TEXT,
                email TEXT,
                timezone TEXT,
                company_id TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                last_synced DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Call performance by time slots
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_performance_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id TEXT,
                date DATE,
                hour_of_day INTEGER,
                day_of_week INTEGER,
                day_name TEXT,
                total_calls INTEGER DEFAULT 0,
                successful_calls INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0,
                avg_call_duration REAL DEFAULT 0,
                best_performing BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # OAuth tokens
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_key TEXT UNIQUE NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at DATETIME,
                location_id TEXT,
                company_id TEXT,
                token_type TEXT DEFAULT 'Bearer',
                scope TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Webhook events log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                contact_id TEXT,
                location_id TEXT,
                raw_data TEXT,
                processed BOOLEAN DEFAULT FALSE,
                error_message TEXT,
                received_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database initialized with enhanced tracking")
    
    def sync_all_locations_paginated(self, access_token, company_id=None):
        """FIXED: Sync ALL locations with pagination"""
        print("🔄 Syncing ALL GHL locations with pagination...")
        
        headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-04-15"}
        all_locations = []
        
        try:
            if company_id:
                # Agency-level access - get ALL installed locations
                url = "https://services.leadconnectorhq.com/oauth/installedLocations"
                params = {"companyId": company_id, "appId": APP_ID, "isInstalled": True}
                
                # Handle pagination
                skip = 0
                limit = 100
                
                while True:
                    params['skip'] = skip
                    params['limit'] = limit
                    
                    resp = requests.get(url, headers=headers, params=params)
                    print(f"📡 API Request: {resp.status_code} - Skip: {skip}, Limit: {limit}")
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        locations = data.get('locations', []) if isinstance(data, dict) else data
                        
                        if not locations:
                            print(f"✅ No more locations. Total found: {len(all_locations)}")
                            break
                            
                        all_locations.extend(locations)
                        print(f"📍 Found {len(locations)} locations in this batch. Total: {len(all_locations)}")
                        
                        # Check if we got fewer than the limit (last page)
                        if len(locations) < limit:
                            break
                            
                        skip += limit
                        
                        # Rate limiting
                        time.sleep(0.1)
                    else:
                        print(f"❌ Error getting locations: {resp.status_code} - {resp.text}")
                        break
            else:
                # Direct API call for single location
                resp = requests.get("https://api.gohighlevel.com/v2/locations", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    all_locations = data.get('locations', []) if isinstance(data, dict) else data
            
            # Store all locations in database
            if all_locations:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for loc in all_locations:
                    location_id = loc.get('_id') or loc.get('id') or loc.get('locationId')
                    location_name = loc.get('name', 'Unknown Location')
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO ghl_locations 
                        (location_id, location_name, address, phone, email, timezone, company_id, last_synced)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        location_id, location_name, loc.get('address', ''),
                        loc.get('phone', ''), loc.get('email', ''), loc.get('timezone', ''),
                        company_id, datetime.now()
                    ))
                
                conn.commit()
                conn.close()
                print(f"✅ Successfully synced {len(all_locations)} locations!")
                return len(all_locations)
            else:
                print("❌ No locations found")
                return 0
                
        except Exception as e:
            print(f"❌ Error syncing locations: {e}")
            return 0
    
    def sync_existing_contacts(self, access_token, location_id, limit=100):
        """Sync existing contacts from a location"""
        print(f"🔄 Syncing existing contacts for location {location_id}...")
        
        headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-04-15"}
        
        try:
            # Get contacts from the last 30 days
            url = f"https://api.gohighlevel.com/v2/contacts"
            params = {
                "locationId": location_id,
                "limit": limit,
                "startAfter": (datetime.now() - timedelta(days=30)).isoformat()
            }
            
            resp = requests.get(url, headers=headers, params=params)
            
            if resp.status_code == 200:
                data = resp.json()
                contacts = data.get('contacts', [])
                
                for contact in contacts:
                    self.record_contact_created(contact, location_id)
                
                print(f"✅ Synced {len(contacts)} existing contacts for location {location_id}")
                return len(contacts)
            else:
                print(f"❌ Failed to sync contacts: {resp.status_code} - {resp.text}")
                return 0
                
        except Exception as e:
            print(f"❌ Error syncing contacts: {e}")
            return 0
    
    def record_contact_created(self, contact_data, location_id):
        """Record when a contact is created"""
        contact_id = contact_data.get('id')
        if not contact_id:
            return False
        
        # Get creation timestamp
        created_at_str = contact_data.get('dateAdded') or contact_data.get('createdAt')
        if created_at_str:
            try:
                # Handle different timestamp formats
                if 'T' in created_at_str:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    created_at = datetime.fromisoformat(created_at_str)
            except:
                created_at = datetime.now()
        else:
            created_at = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get location name
        cursor.execute('SELECT location_name FROM ghl_locations WHERE location_id = ?', (location_id,))
        location_result = cursor.fetchone()
        location_name = location_result[0] if location_result else 'Unknown Location'
        
        # Check if contact already exists
        cursor.execute('SELECT contact_id FROM contact_journey WHERE contact_id = ?', (contact_id,))
        existing = cursor.fetchone()
        
        if not existing:
            # Insert new contact
            cursor.execute('''
                INSERT INTO contact_journey 
                (contact_id, location_id, location_name, contact_name, contact_email, 
                 contact_phone, contact_source, created_at, current_status, tags, last_activity_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                contact_id, location_id, location_name,
                f"{contact_data.get('firstName', '')} {contact_data.get('lastName', '')}".strip(),
                contact_data.get('email', ''), contact_data.get('phone', ''),
                contact_data.get('source', 'unknown'), created_at, 'new_lead',
                json.dumps(contact_data.get('tags', [])), created_at
            ))
            
            conn.commit()
            print(f"✅ NEW LEAD: {contact_id} at {location_name}")
        else:
            print(f"📝 Contact {contact_id} already exists")
        
        conn.close()
        return True
    
    def record_call_attempt(self, contact_id, location_id, call_timestamp=None):
        """Record call attempt"""
        if not call_timestamp:
            call_timestamp = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT created_at, first_call_attempted_at FROM contact_journey WHERE contact_id = ?', (contact_id,))
        result = cursor.fetchone()
        
        if result:
            created_at = datetime.fromisoformat(result[0]) if isinstance(result[0], str) else result[0]
            first_call_attempted_at = result[1]
            
            minutes_to_call = None
            if not first_call_attempted_at:
                minutes_to_call = int((call_timestamp - created_at).total_seconds() / 60)
            
            cursor.execute('''
                UPDATE contact_journey 
                SET total_calls_attempted = total_calls_attempted + 1,
                    first_call_attempted_at = COALESCE(first_call_attempted_at, ?),
                    minutes_to_first_call = COALESCE(minutes_to_first_call, ?),
                    current_status = CASE 
                        WHEN current_status = 'new_lead' THEN 'contacted'
                        ELSE current_status 
                    END,
                    last_activity_at = ?
                WHERE contact_id = ?
            ''', (call_timestamp, minutes_to_call, call_timestamp, contact_id))
            
            self.update_call_performance(cursor, location_id, call_timestamp, 'attempted')
            conn.commit()
            print(f"📞 CALL ATTEMPT: {contact_id} ({minutes_to_call}min after creation)")
        
        conn.close()
    
    def record_call_connected(self, contact_id, location_id, call_timestamp=None, duration_minutes=0):
        """Record successful call connection"""
        if not call_timestamp:
            call_timestamp = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT created_at, first_call_connected_at FROM contact_journey WHERE contact_id = ?', (contact_id,))
        result = cursor.fetchone()
        
        if result:
            created_at = datetime.fromisoformat(result[0]) if isinstance(result[0], str) else result[0]
            first_call_connected_at = result[1]
            
            minutes_to_connection = None
            if not first_call_connected_at:
                minutes_to_connection = int((call_timestamp - created_at).total_seconds() / 60)
            
            cursor.execute('''
                UPDATE contact_journey 
                SET total_calls_connected = total_calls_connected + 1,
                    first_call_connected_at = COALESCE(first_call_connected_at, ?),
                    minutes_to_first_connection = COALESCE(minutes_to_first_connection, ?),
                    current_status = 'connected',
                    last_activity_at = ?
                WHERE contact_id = ?
            ''', (call_timestamp, minutes_to_connection, call_timestamp, contact_id))
            
            self.update_call_performance(cursor, location_id, call_timestamp, 'connected', duration_minutes)
            conn.commit()
            print(f"✅ CALL CONNECTED: {contact_id} ({minutes_to_connection}min after creation)")
        
        conn.close()
    
    def update_call_performance(self, cursor, location_id, timestamp, call_type, duration=0):
        """Update call performance analytics"""
        date = timestamp.date()
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_name = day_names[day_of_week]
        
        cursor.execute('''
            SELECT id, total_calls, successful_calls, avg_call_duration 
            FROM call_performance_slots 
            WHERE location_id = ? AND date = ? AND hour_of_day = ?
        ''', (location_id, date, hour))
        
        existing = cursor.fetchone()
        
        if existing:
            record_id, total_calls, successful_calls, avg_duration = existing
            
            if call_type == 'attempted':
                new_total = total_calls + 1
                cursor.execute('''
                    UPDATE call_performance_slots 
                    SET total_calls = ?
                    WHERE id = ?
                ''', (new_total, record_id))
            
            elif call_type == 'connected':
                new_successful = successful_calls + 1
                new_avg_duration = ((avg_duration * successful_calls) + duration) / new_successful if new_successful > 0 else duration
                
                cursor.execute('''
                    UPDATE call_performance_slots 
                    SET successful_calls = ?, avg_call_duration = ?
                    WHERE id = ?
                ''', (new_successful, new_avg_duration, record_id))
        else:
            total_calls = 1 if call_type == 'attempted' else 0
            successful_calls = 1 if call_type == 'connected' else 0
            
            cursor.execute('''
                INSERT INTO call_performance_slots 
                (location_id, date, hour_of_day, day_of_week, day_name, total_calls, successful_calls, avg_call_duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (location_id, date, hour, day_of_week, day_name, total_calls, successful_calls, duration))
        
        cursor.execute('''
            UPDATE call_performance_slots 
            SET success_rate = CASE 
                WHEN total_calls > 0 THEN (successful_calls * 100.0 / total_calls)
                ELSE 0 
            END
            WHERE location_id = ? AND date = ? AND hour_of_day = ?
        ''', (location_id, date, hour))
    
    def get_real_locations(self):
        """Get ALL real GHL locations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT location_id, location_name, address, last_synced
            FROM ghl_locations 
            WHERE is_active = TRUE
            ORDER BY location_name
        ''')
        
        locations = cursor.fetchall()
        conn.close()
        
        return [{
            'id': loc[0], 
            'name': loc[1],
            'address': loc[2] if loc[2] else '',
            'last_synced': loc[3]
        } for loc in locations]
    
    def get_enhanced_stats(self, location_id=None, days=30):
        """Get FULL conversion funnel statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        where_clause = f"WHERE created_at >= date('now', '-{days} days')"
        params = []
        
        if location_id and location_id != 'all':
            where_clause += " AND location_id = ?"
            params.append(location_id)
        
        # Enhanced stats query with FULL conversion funnel
        query = f'''
            SELECT 
                COUNT(*) as total_leads,
                
                -- Time calculations
                AVG(minutes_to_first_call) as avg_minutes_to_first_call,
                AVG(minutes_to_first_connection) as avg_minutes_to_first_connection,
                AVG(minutes_to_first_session) as avg_minutes_to_first_session,
                AVG(minutes_to_purchase) as avg_minutes_to_purchase,
                
                -- Conversion counts
                COUNT(CASE WHEN first_call_attempted_at IS NOT NULL THEN 1 END) as leads_called,
                COUNT(CASE WHEN first_call_connected_at IS NOT NULL THEN 1 END) as leads_connected,
                COUNT(CASE WHEN first_session_booked_at IS NOT NULL THEN 1 END) as leads_to_session,
                COUNT(CASE WHEN first_purchase_at IS NOT NULL THEN 1 END) as leads_to_purchase,
                
                -- Status breakdown
                COUNT(CASE WHEN current_status = 'new_lead' THEN 1 END) as new_leads,
                COUNT(CASE WHEN current_status = 'contacted' THEN 1 END) as contacted_leads,
                COUNT(CASE WHEN current_status = 'connected' THEN 1 END) as connected_leads,
                COUNT(CASE WHEN current_status = 'session_booked' THEN 1 END) as session_booked_leads,
                COUNT(CASE WHEN current_status = 'purchased' THEN 1 END) as purchased_leads,
                
                -- Performance rates
                ROUND(COUNT(CASE WHEN first_call_connected_at IS NOT NULL THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(CASE WHEN first_call_attempted_at IS NOT NULL THEN 1 END), 0), 1) as connection_rate,
                ROUND(COUNT(CASE WHEN first_session_booked_at IS NOT NULL THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0), 1) as session_rate,
                ROUND(COUNT(CASE WHEN first_purchase_at IS NOT NULL THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0), 1) as conversion_rate,
                    
                -- Speed metrics
                COUNT(CASE WHEN minutes_to_first_call <= 5 THEN 1 END) as calls_within_5min,
                COUNT(CASE WHEN minutes_to_first_call <= 60 THEN 1 END) as calls_within_1hour,
                COUNT(CASE WHEN minutes_to_first_connection <= 60 THEN 1 END) as connected_within_1hour
                    
            FROM contact_journey 
            {where_clause}
        '''
        
        try:
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            if result:
                stats = {
                    'total_leads': result[0] or 0,
                    'avg_minutes_to_first_call': round(result[1] or 0, 1),
                    'avg_hours_to_first_call': round((result[1] or 0) / 60, 2),
                    'avg_minutes_to_first_connection': round(result[2] or 0, 1),
                    'avg_hours_to_first_connection': round((result[2] or 0) / 60, 2),
                    'avg_minutes_to_first_session': round(result[3] or 0, 1),
                    'avg_hours_to_first_session': round((result[3] or 0) / 60, 2),
                    'avg_minutes_to_purchase': round(result[4] or 0, 1),
                    'avg_hours_to_purchase': round((result[4] or 0) / 60, 2),
                    'leads_called': result[5] or 0,
                    'leads_connected': result[6] or 0,
                    'leads_to_session': result[7] or 0,
                    'leads_to_purchase': result[8] or 0,
                    'new_leads': result[9] or 0,
                    'contacted_leads': result[10] or 0,
                    'connected_leads': result[11] or 0,
                    'session_booked_leads': result[12] or 0,
                    'purchased_leads': result[13] or 0,
                    'connection_rate': result[14] or 0,
                    'session_rate': result[15] or 0,
                    'conversion_rate': result[16] or 0,
                    'calls_within_5min': result[17] or 0,
                    'calls_within_1hour': result[18] or 0,
                    'connected_within_1hour': result[19] or 0,
                    'speed_to_call_rate': round((result[17] or 0) * 100.0 / max(result[0] or 1, 1), 1),
                    'hourly_call_rate': round((result[18] or 0) * 100.0 / max(result[0] or 1, 1), 1)
                }
            else:
                stats = self.get_empty_stats()
                
        except Exception as e:
            print(f"❌ Database query error: {e}")
            stats = self.get_empty_stats()
        
        best_times = self.get_best_call_times(location_id, days)
        conn.close()
        
        return {
            'stats': stats,
            'best_times': best_times
        }
    
    def get_empty_stats(self):
        """Return empty stats structure"""
        return {
            'total_leads': 0, 'avg_minutes_to_first_call': 0, 'avg_hours_to_first_call': 0,
            'avg_minutes_to_first_connection': 0, 'avg_hours_to_first_connection': 0,
            'avg_minutes_to_first_session': 0, 'avg_hours_to_first_session': 0,
            'avg_minutes_to_purchase': 0, 'avg_hours_to_purchase': 0,
            'leads_called': 0, 'leads_connected': 0, 'leads_to_session': 0, 'leads_to_purchase': 0,
            'new_leads': 0, 'contacted_leads': 0, 'connected_leads': 0, 'session_booked_leads': 0, 'purchased_leads': 0,
            'connection_rate': 0, 'session_rate': 0, 'conversion_rate': 0,
            'calls_within_5min': 0, 'calls_within_1hour': 0, 'connected_within_1hour': 0,
            'speed_to_call_rate': 0, 'hourly_call_rate': 0
        }
    
    def get_best_call_times(self, location_id=None, days=30):
        """Get best call times"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        where_clause = f"WHERE date >= date('now', '-{days} days')"
        params = []
        
        if location_id and location_id != 'all':
            where_clause += " AND location_id = ?"
            params.append(location_id)
        
        query = f'''
            SELECT 
                hour_of_day,
                day_name,
                day_of_week,
                SUM(total_calls) as total_calls,
                SUM(successful_calls) as successful_calls,
                ROUND(AVG(success_rate), 1) as avg_success_rate,
                ROUND(AVG(avg_call_duration), 1) as avg_duration
            FROM call_performance_slots 
            {where_clause}
            GROUP BY hour_of_day, day_of_week, day_name
            HAVING total_calls >= 1
            ORDER BY avg_success_rate DESC, total_calls DESC
        '''
        
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            best_times = [{
                'hour': row[0],
                'day_name': row[1],
                'day_of_week': row[2],
                'total_calls': row[3],
                'successful_calls': row[4],
                'success_rate': row[5],
                'avg_duration': row[6]
            } for row in results]
            
        except Exception as e:
            print(f"❌ Error getting best call times: {e}")
            best_times = []
        
        conn.close()
        return best_times
    
    def log_webhook_event(self, event_type, contact_id, location_id, raw_data, error_message=None):
        """Log webhook events for debugging"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO webhook_events 
            (event_type, contact_id, location_id, raw_data, error_message, processed)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (event_type, contact_id, location_id, json.dumps(raw_data), error_message, True))
        
        conn.commit()
        conn.close()

# Global analytics instance
analytics = RealTimeLeadAnalytics()

# Token management
def get_valid_token():
    """Get a valid access token"""
    conn = sqlite3.connect(analytics.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM oauth_tokens ORDER BY created_at DESC LIMIT 1')
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return None
    
    expires_at = datetime.fromisoformat(result[4])
    if expires_at <= datetime.now() + timedelta(minutes=5):
        return refresh_access_token(result)
    
    return {
        'access_token': result[2],
        'company_id': result[6],
        'location_id': result[5]
    }

def refresh_access_token(token_record):
    """Refresh the access token"""
    try:
        resp = requests.post("https://services.leadconnectorhq.com/oauth/token", data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": token_record[3]
        })
        
        if resp.status_code == 200:
            new_tokens = resp.json()
            expires_at = datetime.now() + timedelta(seconds=new_tokens.get('expires_in', 3600))
            
            conn = sqlite3.connect(analytics.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE oauth_tokens 
                SET access_token = ?, expires_at = ?
