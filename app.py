# app.py - Real-Time GHL Lead Analytics - COMPLETE CLEAN VERSION
import os
import json
import time
import requests
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configuration
CLIENT_ID = os.getenv('GHL_CLIENT_ID', '6886150802562ad87b4e2dc0-mdlog30p')
CLIENT_SECRET = os.getenv('GHL_CLIENT_SECRET', '3162ed43-8498-48a3-a8b4-8a60e980f318')
APP_ID = os.getenv('GHL_APP_ID', '66c70d3c319d92c0772350b9')

# URLs
BASE_URL = "https://alti-speed-to-lead.onrender.com"
REDIRECT_URI = f"{BASE_URL}/oauth/callback"

# Scopes
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

class RealTimeLeadAnalytics:
    def __init__(self, db_path="realtime_lead_analytics.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM ghl_locations WHERE is_active = TRUE')
    total_locations = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM webhook_events WHERE received_at >= date("now", "-1 day")')
    recent_webhooks = cursor.fetchone()[0]
    
    conn.close()
    
    token_data = get_valid_token()
    token_status = 'valid' if token_data else 'missing'
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'base_url': BASE_URL,
        'webhook_url': f'{BASE_URL}/webhook',
        'version': '3.0.0 - WORKING',
        'database_health': {
            'total_contacts': total_contacts,
            'total_locations': total_locations,
            'recent_webhooks_24h': recent_webhooks
        },
        'oauth_status': token_status,
        'scopes_configured': SCOPES
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Real-Time GHL Lead Analytics v3.0 - WORKING starting on port {port}")
    print(f"Base URL: {BASE_URL}")
    print(f"Webhook URL: {BASE_URL}/webhook")
    print(f"Dashboard: {BASE_URL}/dashboard")
    print(f"Health: {BASE_URL}/health")
    print("READY: Clean deployment, All locations sync, Lead tracking")
    
    app.run(host='0.0.0.0', port=port, debug=False)('''
            CREATE TABLE IF NOT EXISTS contact_journey (
                contact_id TEXT PRIMARY KEY,
                location_id TEXT NOT NULL,
                location_name TEXT,
                contact_name TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                contact_source TEXT,
                created_at DATETIME NOT NULL,
                first_call_attempted_at DATETIME,
                first_call_connected_at DATETIME,
                first_session_booked_at DATETIME,
                first_purchase_at DATETIME,
                minutes_to_first_call INTEGER,
                minutes_to_first_connection INTEGER,
                minutes_to_first_session INTEGER,
                minutes_to_purchase INTEGER,
                total_calls_attempted INTEGER DEFAULT 0,
                total_calls_connected INTEGER DEFAULT 0,
                total_sessions_booked INTEGER DEFAULT 0,
                current_status TEXT DEFAULT 'new_lead',
                opportunity_stage TEXT,
                tags TEXT,
                custom_fields TEXT,
                last_activity_at DATETIME,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
        print("Database initialized successfully")
    
    def sync_all_locations_paginated(self, access_token, company_id=None):
        print("Syncing ALL GHL locations with pagination...")
        headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-04-15"}
        all_locations = []
        
        try:
            if company_id:
                url = "https://services.leadconnectorhq.com/oauth/installedLocations"
                params = {"companyId": company_id, "appId": APP_ID, "isInstalled": True}
                
                skip = 0
                limit = 100
                
                while True:
                    params['skip'] = skip
                    params['limit'] = limit
                    
                    resp = requests.get(url, headers=headers, params=params)
                    print(f"API Request: {resp.status_code} - Skip: {skip}")
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        locations = data.get('locations', []) if isinstance(data, dict) else data
                        
                        if not locations:
                            break
                            
                        all_locations.extend(locations)
                        print(f"Found {len(locations)} locations. Total: {len(all_locations)}")
                        
                        if len(locations) < limit:
                            break
                            
                        skip += limit
                        time.sleep(0.1)
                    else:
                        break
            
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
                print(f"Successfully synced {len(all_locations)} locations!")
                return len(all_locations)
            
            return 0
        except Exception as e:
            print(f"Error syncing locations: {e}")
            return 0
    
    def record_contact_created(self, contact_data, location_id):
        contact_id = contact_data.get('id')
        if not contact_id:
            return False
        
        created_at_str = contact_data.get('dateAdded') or contact_data.get('createdAt')
        if created_at_str:
            try:
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
        
        cursor.execute('SELECT location_name FROM ghl_locations WHERE location_id = ?', (location_id,))
        location_result = cursor.fetchone()
        location_name = location_result[0] if location_result else 'Unknown Location'
        
        cursor.execute('SELECT contact_id FROM contact_journey WHERE contact_id = ?', (contact_id,))
        existing = cursor.fetchone()
        
        if not existing:
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
            print(f"NEW LEAD: {contact_id} at {location_name}")
        
        conn.close()
        return True
    
    def get_real_locations(self):
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
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM contact_journey')
            total_count = cursor.fetchone()[0]
            
            if total_count == 0:
                conn.close()
                return {
                    'stats': self.get_empty_stats(),
                    'best_times': []
                }
            
            where_clause = f"WHERE created_at >= date('now', '-{days} days')"
            params = []
            
            if location_id and location_id != 'all':
                where_clause += " AND location_id = ?"
                params.append(location_id)
            
            query = f'''
                SELECT 
                    COUNT(*) as total_leads,
                    COALESCE(AVG(minutes_to_first_call), 0) as avg_minutes_to_first_call,
                    COALESCE(AVG(minutes_to_first_connection), 0) as avg_minutes_to_first_connection,
                    COUNT(CASE WHEN first_call_attempted_at IS NOT NULL THEN 1 END) as leads_called,
                    COUNT(CASE WHEN first_call_connected_at IS NOT NULL THEN 1 END) as leads_connected,
                    COUNT(CASE WHEN current_status = 'new_lead' THEN 1 END) as new_leads,
                    COUNT(CASE WHEN current_status = 'contacted' THEN 1 END) as contacted_leads,
                    COUNT(CASE WHEN current_status = 'connected' THEN 1 END) as connected_leads
                FROM contact_journey 
                {where_clause}
            '''
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            if result:
                total_leads = result[0] or 0
                leads_called = result[3] or 0
                leads_connected = result[4] or 0
                
                connection_rate = round(leads_connected * 100.0 / max(leads_called, 1), 1) if leads_called > 0 else 0
                
                stats = {
                    'total_leads': total_leads,
                    'avg_minutes_to_first_call': round(result[1] or 0, 1),
                    'avg_hours_to_first_call': round((result[1] or 0) / 60, 2),
                    'avg_minutes_to_first_connection': round(result[2] or 0, 1),
                    'avg_hours_to_first_connection': round((result[2] or 0) / 60, 2),
                    'leads_called': leads_called,
                    'leads_connected': leads_connected,
                    'new_leads': result[5] or 0,
                    'contacted_leads': result[6] or 0,
                    'connected_leads': result[7] or 0,
                    'connection_rate': connection_rate,
                    'session_rate': 0,
                    'conversion_rate': 0,
                    'leads_to_session': 0,
                    'leads_to_purchase': 0,
                    'session_booked_leads': 0,
                    'purchased_leads': 0,
                    'calls_within_5min': 0,
                    'calls_within_1hour': 0,
                    'speed_to_call_rate': 0,
                    'hourly_call_rate': 0
                }
            else:
                stats = self.get_empty_stats()
            
            conn.close()
            
            return {
                'stats': stats,
                'best_times': []
            }
            
        except Exception as e:
            print(f"Error in get_enhanced_stats: {e}")
            return {
                'stats': self.get_empty_stats(),
                'best_times': []
            }
    
    def get_empty_stats(self):
        return {
            'total_leads': 0, 'avg_minutes_to_first_call': 0, 'avg_hours_to_first_call': 0,
            'avg_minutes_to_first_connection': 0, 'avg_hours_to_first_connection': 0,
            'leads_called': 0, 'leads_connected': 0, 'new_leads': 0, 'contacted_leads': 0, 
            'connected_leads': 0, 'connection_rate': 0, 'session_rate': 0, 'conversion_rate': 0,
            'leads_to_session': 0, 'leads_to_purchase': 0, 'session_booked_leads': 0, 
            'purchased_leads': 0, 'calls_within_5min': 0, 'calls_within_1hour': 0,
            'speed_to_call_rate': 0, 'hourly_call_rate': 0
        }
    
    def log_webhook_event(self, event_type, contact_id, location_id, raw_data, error_message=None):
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
        print(f"Token refresh failed: {e}")
    
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
    install_url = generate_install_url()
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Real-Time GHL Lead Analytics</title>
        <style>
            body {{ font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px; 
                   background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-align: center; }}
            .card {{ background: rgba(255,255,255,0.95); color: #333; padding: 40px; border-radius: 20px; }}
            .install-btn {{ display: inline-block; background: linear-gradient(45deg, #667eea, #764ba2);
                          color: white; padding: 15px 30px; text-decoration: none; border-radius: 10px;
                          font-size: 18px; font-weight: bold; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Real-Time GHL Lead Analytics</h1>
            <p>Advanced lead performance tracking</p>
            <a href="{install_url}" class="install-btn">Install on GoHighLevel</a>
            <br><br>
            <a href="/dashboard">View Dashboard</a> | 
            <a href="/health">Health Check</a>
        </div>
    </body>
    </html>
    '''

@app.route('/dashboard')
def dashboard():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>Lead Analytics Dashboard</title>
    <style>
        body { font-family: Arial; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
        .controls { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .metric { background: white; padding: 20px; border-radius: 10px; text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #667eea; }
        .metric-label { color: #666; margin-top: 5px; }
        button { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 5px; }
        select { padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Real-Time Lead Analytics Dashboard</h1>
            <p>Complete conversion funnel tracking</p>
        </div>

        <div class="controls">
            <label>Location:</label>
            <select id="locationFilter">
                <option value="all">All Locations</option>
            </select>
            
            <label>Time Period:</label>
            <select id="dateRange">
                <option value="7">Last 7 Days</option>
                <option value="30" selected>Last 30 Days</option>
                <option value="90">Last 90 Days</option>
            </select>
            
            <button onclick="updateDashboard()">Update</button>
            <button onclick="syncAllLocations()">Sync Locations</button>
            <button onclick="createTestData()">Create Test Data</button>
        </div>

        <div class="metrics" id="metricsGrid"></div>
    </div>

    <script>
        let dashboardData = {};

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
                    option.textContent = location.name;
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Error loading locations:', error);
            }
        }

        async function loadDashboard() {
            try {
                const locationId = document.getElementById('locationFilter').value;
                const days = document.getElementById('dateRange').value;
                
                const params = new URLSearchParams({
                    location: locationId,
                    days: days
                });
                
                const response = await fetch('/api/realtime-stats?' + params);
                dashboardData = await response.json();
                
                updateMetrics();
            } catch (error) {
                console.error('Error loading dashboard:', error);
            }
        }

        function updateMetrics() {
            const metricsGrid = document.getElementById('metricsGrid');
            metricsGrid.innerHTML = '';

            const metrics = [
                { label: 'Total Leads', value: dashboardData.total_leads || 0 },
                { label: 'Called', value: dashboardData.leads_called || 0 },
                { label: 'Connected', value: dashboardData.leads_connected || 0 },
                { label: 'Connection Rate', value: (dashboardData.connection_rate || 0) + '%' },
                { label: 'Avg Time to Call', value: (dashboardData.avg_minutes_to_first_call || 0) + 'm' },
                { label: 'Avg Time to Connect', value: (dashboardData.avg_minutes_to_first_connection || 0) + 'm' }
            ];

            metrics.forEach(function(metric) {
                const card = document.createElement('div');
                card.className = 'metric';
                card.innerHTML = '<div class="metric-value">' + metric.value + '</div>' +
                    '<div class="metric-label">' + metric.label + '</div>';
                metricsGrid.appendChild(card);
            });
        }

        function updateDashboard() {
            loadDashboard();
        }

        async function syncAllLocations() {
            try {
                const response = await fetch('/api/sync-all-locations', { method: 'POST' });
                const result = await response.json();
                alert('Synced ' + result.count + ' locations!');
                loadLocations();
            } catch (error) {
                alert('Sync failed');
            }
        }

        async function createTestData() {
            try {
                const response = await fetch('/api/create-test-data', { method: 'POST' });
                const result = await response.json();
                alert('Created ' + result.test_contacts.length + ' test contacts!');
                setTimeout(() => { loadDashboard(); }, 1000);
            } catch (error) {
                alert('Test data creation failed');
            }
        }
    </script>
</body>
</html>
    '''

@app.route('/oauth/callback')
def oauth_callback():
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f"<h1>Installation Error</h1><p>{error}</p>"
    
    if not code:
        return "<h1>No authorization code received</h1>"
    
    try:
        resp = requests.post("https://services.leadconnectorhq.com/oauth/token", data={
            "grant_type": "authorization_code", "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET, "code": code, "redirect_uri": REDIRECT_URI
        })
        
        tokens = resp.json()
        if "error" in tokens:
            return f"<h1>Token Error</h1><p>{tokens.get('error_description')}</p>"
        
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
        
        locations_synced = analytics.sync_all_locations_paginated(tokens['access_token'], tokens.get('companyId'))
        
        return f'''
        <div style="text-align: center; padding: 50px; font-family: Arial;">
            <h1>Installation Successful!</h1>
            <p>Locations Synced: {locations_synced}</p>
            <p><strong>Setup webhook URL:</strong> {BASE_URL}/webhook</p>
            <p><strong>Subscribe to:</strong> ContactCreate, OutboundMessage, InboundMessage</p>
            <a href="/dashboard" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">
                Open Dashboard
            </a>
        </div>
        '''
        
    except Exception as e:
        return f"<h1>Installation Failed</h1><p>{str(e)}</p>"

# API Routes
@app.route('/api/locations')
def api_locations():
    locations = analytics.get_real_locations()
    return jsonify(locations)

@app.route('/api/sync-all-locations', methods=['POST'])
def api_sync_all_locations():
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    count = analytics.sync_all_locations_paginated(token_data['access_token'], token_data.get('company_id'))
    return jsonify({'status': 'success', 'count': count})

@app.route('/api/realtime-stats')
def api_realtime_stats():
    try:
        location_id = request.args.get('location', 'all')
        days = int(request.args.get('days', 30))
        
        data = analytics.get_enhanced_stats(location_id, days)
        response = data['stats'].copy()
        response['best_times'] = data['best_times']
        
        return jsonify(response)
        
    except Exception as e:
        print(f"Error in realtime-stats: {str(e)}")
        return jsonify(analytics.get_empty_stats())

@app.route('/api/create-test-data', methods=['POST'])
def api_create_test_data():
    try:
        locations = analytics.get_real_locations()
        if not locations:
            return jsonify({'status': 'error', 'message': 'No locations available'})
        
        location_id = locations[0]['id']
        test_contacts = []
        
        for i in range(5):
            test_contact = {
                'id': f'test_contact_{int(time.time())}_{i}',
                'firstName': f'Test{i}',
                'lastName': 'Contact',
                'email': f'test{i}@example.com',
                'phone': f'+123456789{i}',
                'source': 'test_data',
                'dateAdded': (datetime.now() - timedelta(hours=i)).isoformat()
            }
            
            success = analytics.record_contact_created(test_contact, location_id)
            if success:
                test_contacts.append(test_contact['id'])
        
        return jsonify({
            'status': 'success',
            'test_contacts': test_contacts,
            'location_used': location_id
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    try:
        webhook_data = request.json
        event_type = webhook_data.get('type')
        contact_id = webhook_data.get('contactId') or webhook_data.get('contact', {}).get('id')
        location_id = webhook_data.get('locationId')
        
        print(f"WEBHOOK: {event_type} | Contact: {contact_id} | Location: {location_id}")
        
        analytics.log_webhook_event(event_type, contact_id, location_id, webhook_data)
        
        if event_type == 'ContactCreate':
            contact = webhook_data.get('contact', {})
            if contact.get('id') and location_id:
                success = analytics.record_contact_created(contact, location_id)
                if success:
                    print(f"NEW LEAD TRACKED: {contact.get('id')}")
        
        return jsonify({'status': 'success', 'message': f'Webhook {event_type} processed'})
        
    except Exception as e:
        print(f"WEBHOOK ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    conn = sqlite3.connect(analytics.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM contact_journey')
    total_contacts = cursor.fetchone()[0]
    
    cursor.execute
