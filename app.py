# debug_app.py - DEBUG VERSION to see exactly what's happening
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

class DebugLeadAnalytics:
    def __init__(self, db_path="debug_analytics.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                contact_id TEXT PRIMARY KEY,
                location_id TEXT NOT NULL,
                location_name TEXT,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                phone TEXT,
                source TEXT,
                date_added TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                custom_fields TEXT,
                tags TEXT,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                location_id TEXT PRIMARY KEY,
                location_name TEXT NOT NULL,
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_debug_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT,
                method TEXT,
                status_code INTEGER,
                request_data TEXT,
                response_data TEXT,
                error_message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Debug database initialized")
    
    def log_api_call(self, endpoint, method, status_code, request_data=None, response_data=None, error_message=None):
        """Log all API calls for debugging"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_debug_log 
            (endpoint, method, status_code, request_data, response_data, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            endpoint, method, status_code, 
            json.dumps(request_data) if request_data else None,
            response_data[:1000] if response_data else None,  # Truncate long responses
            error_message
        ))
        
        conn.commit()
        conn.close()
    
    def test_api_connection(self, access_token):
        """Test basic API connectivity"""
        headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-04-15"}
        
        print("🔍 TESTING API CONNECTION...")
        
        # Test 1: Get current user info
        try:
            url = "https://services.leadconnectorhq.com/users/current"
            resp = requests.get(url, headers=headers)
            print(f"👤 User Info API: {resp.status_code}")
            self.log_api_call(url, "GET", resp.status_code, None, resp.text[:500])
            
            if resp.status_code == 200:
                user_data = resp.json()
                print(f"✅ User: {user_data.get('name', 'Unknown')} - Company: {user_data.get('companyId', 'Unknown')}")
                return user_data
            else:
                print(f"❌ User API failed: {resp.text}")
                return None
                
        except Exception as e:
            print(f"❌ User API error: {e}")
            self.log_api_call(url, "GET", 0, None, None, str(e))
            return None
    
    def debug_locations_api(self, access_token, company_id):
        """Debug the locations API with multiple approaches"""
        headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-04-15"}
        
        print(f"🔍 DEBUGGING LOCATIONS API for company: {company_id}")
        
        # Approach 1: Installed locations
        try:
            url1 = "https://services.leadconnectorhq.com/oauth/installedLocations"
            params1 = {"companyId": company_id, "appId": APP_ID, "isInstalled": True}
            
            print(f"📡 Testing: {url1}")
            print(f"📋 Params: {params1}")
            
            resp1 = requests.get(url1, headers=headers, params=params1)
            print(f"📊 Response: {resp1.status_code}")
            
            self.log_api_call(url1, "GET", resp1.status_code, params1, resp1.text[:1000])
            
            if resp1.status_code == 200:
                data1 = resp1.json()
                print(f"✅ Installed Locations Found: {len(data1.get('locations', []))}")
                if data1.get('locations'):
                    print(f"🏢 First location: {data1['locations'][0].get('name', 'No name')}")
                return data1.get('locations', [])
            else:
                print(f"❌ Installed locations failed: {resp1.text}")
                
        except Exception as e:
            print(f"❌ Installed locations error: {e}")
        
        # Approach 2: Direct locations API
        try:
            url2 = "https://services.leadconnectorhq.com/locations/"
            params2 = {"companyId": company_id}
            
            print(f"📡 Testing: {url2}")
            resp2 = requests.get(url2, headers=headers, params=params2)
            print(f"📊 Response: {resp2.status_code}")
            
            self.log_api_call(url2, "GET", resp2.status_code, params2, resp2.text[:1000])
            
            if resp2.status_code == 200:
                data2 = resp2.json()
                locations = data2.get('locations', [])
                print(f"✅ Direct Locations Found: {len(locations)}")
                return locations
            else:
                print(f"❌ Direct locations failed: {resp2.text}")
                
        except Exception as e:
            print(f"❌ Direct locations error: {e}")
        
        return []
    
    def debug_contacts_api(self, access_token, location_id):
        """Debug the contacts API with detailed logging"""
        headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-04-15"}
        
        print(f"🔍 DEBUGGING CONTACTS API for location: {location_id}")
        
        # Test different contact API approaches
        approaches = [
            {
                "name": "Standard Contacts API",
                "url": "https://services.leadconnectorhq.com/contacts/",
                "params": {"locationId": location_id, "limit": 10}
            },
            {
                "name": "Search Contacts API", 
                "url": "https://services.leadconnectorhq.com/contacts/search",
                "params": {"locationId": location_id, "limit": 10}
            }
        ]
        
        for approach in approaches:
            try:
                print(f"📡 Testing: {approach['name']} - {approach['url']}")
                print(f"📋 Params: {approach['params']}")
                
                resp = requests.get(approach['url'], headers=headers, params=approach['params'])
                print(f"📊 Response: {resp.status_code}")
                
                self.log_api_call(approach['url'], "GET", resp.status_code, approach['params'], resp.text[:1000])
                
                if resp.status_code == 200:
                    data = resp.json()
                    contacts = data.get('contacts', [])
                    print(f"✅ {approach['name']}: Found {len(contacts)} contacts")
                    
                    if contacts:
                        first_contact = contacts[0]
                        print(f"👤 Sample contact: {first_contact.get('firstName', '')} {first_contact.get('lastName', '')} - {first_contact.get('email', 'No email')}")
                        return contacts
                    else:
                        print(f"📭 No contacts found with {approach['name']}")
                else:
                    print(f"❌ {approach['name']} failed: {resp.text}")
                    
            except Exception as e:
                print(f"❌ {approach['name']} error: {e}")
                self.log_api_call(approach['url'], "GET", 0, approach['params'], None, str(e))
        
        return []
    
    def add_contact(self, contact_data, location_id):
        """Add contact with debug logging"""
        contact_id = contact_data.get('id')
        if not contact_id:
            print("❌ No contact ID found in data")
            return False
        
        print(f"💾 Adding contact: {contact_data.get('firstName', '')} {contact_data.get('lastName', '')} ({contact_id})")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT location_name FROM locations WHERE location_id = ?', (location_id,))
        loc_result = cursor.fetchone()
        location_name = loc_result[0] if loc_result else 'Unknown Location'
        
        cursor.execute('''
            INSERT OR REPLACE INTO contacts 
            (contact_id, location_id, location_name, first_name, last_name, 
             email, phone, source, date_added, custom_fields, tags, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            contact_id,
            location_id,
            location_name,
            contact_data.get('firstName', ''),
            contact_data.get('lastName', ''),
            contact_data.get('email', ''),
            contact_data.get('phone', ''),
            contact_data.get('source', ''),
            contact_data.get('dateAdded', ''),
            json.dumps(contact_data.get('customFields', [])),
            json.dumps(contact_data.get('tags', [])),
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Contact saved to database")
        return True
    
    def get_basic_stats(self, location_id=None):
        """Get basic stats with debug info"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        where_clause = "WHERE 1=1"
        params = []
        
        if location_id and location_id != 'all':
            where_clause += " AND location_id = ?"
            params.append(location_id)
        
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause}", params)
        total_contacts = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND phone IS NOT NULL AND phone != ''", params)
        contacts_with_phone = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND email IS NOT NULL AND email != ''", params)
        contacts_with_email = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND phone IS NOT NULL AND phone != '' AND email IS NOT NULL AND email != ''", params)
        contacts_with_both = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND date(created_at) = date('now')", params)
        new_today = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND created_at >= date('now', '-7 days')", params)
        new_this_week = cursor.fetchone()[0]
        
        # Debug: Show sample contacts
        cursor.execute(f"SELECT first_name, last_name, email, phone, location_name FROM contacts {where_clause} LIMIT 5", params)
        sample_contacts = cursor.fetchall()
        
        conn.close()
        
        print(f"📊 STATS DEBUG - Total: {total_contacts}, Location filter: {location_id}")
        print(f"📋 Sample contacts: {sample_contacts}")
        
        return {
            'total_contacts': total_contacts,
            'contacts_with_phone': contacts_with_phone,
            'contacts_with_email': contacts_with_email,
            'contacts_with_both': contacts_with_both,
            'new_today': new_today,
            'new_this_week': new_this_week,
            'phone_rate': round(contacts_with_phone * 100.0 / max(total_contacts, 1), 1),
            'email_rate': round(contacts_with_email * 100.0 / max(total_contacts, 1), 1),
            'complete_rate': round(contacts_with_both * 100.0 / max(total_contacts, 1), 1),
            'sample_contacts': [f"{c[0]} {c[1]} - {c[2]} - {c[3]} ({c[4]})" for c in sample_contacts]
        }
    
    def get_locations(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT location_id, location_name, last_synced FROM locations ORDER BY location_name')
        locations = cursor.fetchall()
        conn.close()
        
        return [{'id': loc[0], 'name': loc[1], 'last_synced': loc[2]} for loc in locations]
    
    def get_debug_logs(self, limit=10):
        """Get recent API debug logs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT endpoint, method, status_code, error_message, timestamp 
            FROM api_debug_log 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        logs = cursor.fetchall()
        conn.close()
        
        return [{
            'endpoint': log[0], 'method': log[1], 'status_code': log[2],
            'error_message': log[3], 'timestamp': log[4]
        } for log in logs]

# Global instance
analytics = DebugLeadAnalytics()

# Token functions
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
        <title>Debug Lead Analytics</title>
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
            <h1>🔍 Debug Lead Analytics</h1>
            <p>Let's figure out why contacts aren't showing</p>
            <a href="{install_url}" class="install-btn">Install on GoHighLevel</a>
            <br><br>
            <a href="/dashboard">Debug Dashboard</a> | 
            <a href="/debug">Debug Info</a> |
            <a href="/health">Health Check</a>
        </div>
    </body>
    </html>
    '''

@app.route('/debug')
def debug_info():
    """Show debug information"""
    token_data = get_valid_token()
    debug_logs = analytics.get_debug_logs(20)
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Debug Information</title>
        <style>
            body {{ font-family: monospace; margin: 20px; background: #1a1a1a; color: #00ff00; }}
            .section {{ background: #2a2a2a; padding: 20px; margin: 10px 0; border-radius: 5px; }}
            .error {{ color: #ff6b6b; }}
            .success {{ color: #51cf66; }}
            .info {{ color: #74c0fc; }}
        </style>
    </head>
    <body>
        <h1>🔍 DEBUG INFORMATION</h1>
        
        <div class="section">
            <h2>🔑 TOKEN STATUS</h2>
            <p>Token Available: <span class="{'success' if token_data else 'error'}">{'YES' if token_data else 'NO'}</span></p>
            {f'<p>Company ID: {token_data.get("company_id", "Unknown")}</p>' if token_data else ''}
        </div>
        
        <div class="section">
            <h2>📊 RECENT API CALLS</h2>
            {''.join([f'<p class="{'success' if log['status_code'] == 200 else 'error'}">{log["timestamp"]}: {log["method"]} {log["endpoint"]} - Status: {log["status_code"]}{" - Error: " + log["error_message"] if log["error_message"] else ""}</p>' for log in debug_logs])}
        </div>
        
        <div class="section">
            <h2>🛠️ DEBUG ACTIONS</h2>
            <button onclick="testConnection()">Test API Connection</button>
            <button onclick="debugLocations()">Debug Locations API</button>
            <button onclick="debugContacts()">Debug Contacts API</button>
        </div>
        
        <div id="results"></div>
        
        <script>
            async function testConnection() {{
                const response = await fetch('/api/test-connection', {{ method: 'POST' }});
                const result = await response.json();
                document.getElementById('results').innerHTML = '<div class="section"><h3>🔗 Connection Test</h3><pre>' + JSON.stringify(result, null, 2) + '</pre></div>';
            }}
            
            async function debugLocations() {{
                const response = await fetch('/api/debug-locations', {{ method: 'POST' }});
                const result = await response.json();
                document.getElementById('results').innerHTML = '<div class="section"><h3>📍 Locations Debug</h3><pre>' + JSON.stringify(result, null, 2) + '</pre></div>';
            }}
            
            async function debugContacts() {{
                const locationId = prompt('Enter Location ID to test:');
                if (locationId) {{
                    const response = await fetch('/api/debug-contacts', {{ 
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ location_id: locationId }})
                    }});
                    const result = await response.json();
                    document.getElementById('results').innerHTML = '<div class="section"><h3>👥 Contacts Debug</h3><pre>' + JSON.stringify(result, null, 2) + '</pre></div>';
                }}
            }}
        </script>
    </body>
    </html>
    '''

@app.route('/dashboard')
def dashboard():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>Debug Dashboard</title>
    <style>
        body { font-family: Arial; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
        .controls { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .metric { background: white; padding: 25px; border-radius: 10px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric-value { font-size: 2.5em; font-weight: bold; color: #667eea; margin-bottom: 10px; }
        .metric-label { color: #666; font-weight: 500; }
        .metric-sub { color: #999; font-size: 0.9em; margin-top: 5px; }
        button { background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; margin: 5px; font-weight: 500; }
        button:hover { background: #5a6fd8; }
        select { padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 5px; }
        .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .debug-section { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; padding: 15px; margin: 10px 0; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Debug Dashboard</h1>
            <p>Let's see exactly what's happening with the API calls</p>
        </div>

        <div class="controls">
            <label>Location:</label>
            <select id="locationFilter">
                <option value="all">Loading locations...</option>
            </select>
            
            <button onclick="loadDashboard()">🔄 Refresh Data</button>
            <button onclick="testApiConnection()">🔗 Test API</button>
            <button onclick="debugLocationsCall()">📍 Debug Locations</button>
            <button onclick="debugContactsCall()">👥 Debug Contacts</button>
        </div>

        <div id="status"></div>
        
        <div class="debug-section">
            <h3>🛠️ Debug Information</h3>
            <div id="debugInfo">Click debug buttons to see detailed API responses...</div>
        </div>

        <div class="metrics" id="metricsGrid">
            <div class="metric">
                <div class="metric-value">Loading...</div>
                <div class="metric-label">Please wait</div>
            </div>
        </div>
    </div>

    <script>
        let currentData = {};

        document.addEventListener('DOMContentLoaded', function() {
            loadLocations();
            loadDashboard();
        });

        function showStatus(message, type = 'success') {
            const statusDiv = document.getElementById('status');
            statusDiv.innerHTML = '<div class="' + type + '">' + message + '</div>';
            setTimeout(() => statusDiv.innerHTML = '', 10000);
        }
        
        function showDebugInfo(info) {
            document.getElementById('debugInfo').innerHTML = '<pre>' + JSON.stringify(info, null, 2) + '</pre>';
        }

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
                
                showStatus('Loaded ' + locations.length + ' locations');
            } catch (error) {
                showStatus('Error loading locations: ' + error.message, 'error');
            }
        }

        async function loadDashboard() {
            try {
                const locationId = document.getElementById('locationFilter').value;
                const response = await fetch('/api/stats?location=' + locationId);
                currentData = await response.json();
                
                updateMetrics();
                showStatus('Dashboard data loaded');
            } catch (error) {
                showStatus('Error loading dashboard: ' + error.message, 'error');
            }
        }

        function updateMetrics() {
            const metricsGrid = document.getElementById('metricsGrid');
            
            const metrics = [
                { 
                    label: 'Total Contacts', 
                    value: currentData.total_contacts || 0,
                    sub: 'Database count'
                },
                { 
                    label: 'With Phone', 
                    value: currentData.contacts_with_phone || 0,
                    sub: (currentData.phone_rate || 0) + '% of total'
                },
                { 
                    label: 'With Email', 
                    value: currentData.contacts_with_email || 0,
                    sub: (currentData.email_rate || 0) + '% of total'
                },
                { 
                    label: 'Complete Contacts', 
                    value: currentData.contacts_with_both || 0,
                    sub: 'Both phone & email'
                }
            ];

            metricsGrid.innerHTML = '';
            
            metrics.forEach(function(metric) {
                const card = document.createElement('div');
                card.className = 'metric';
                card.innerHTML = 
                    '<div class="metric-value">' + metric.value + '</div>' +
                    '<div class="metric-label">' + metric.label + '</div>' +
                    '<div class="metric-sub">' + metric.sub + '</div>';
                metricsGrid.appendChild(card);
            });
            
            // Show sample contacts if available
            if (currentData.sample_contacts && currentData.sample_contacts.length > 0) {
                const sampleDiv = document.createElement('div');
                sampleDiv.className = 'debug-section';
                sampleDiv.innerHTML = '<h4>📋 Sample Contacts:</h4>' + 
                    currentData.sample_contacts.map(c => '<p>' + c + '</p>').join('');
                metricsGrid.appendChild(sampleDiv);
            }
        }

        async function testApiConnection() {
            try {
                showStatus('Testing API connection...', 'success');
                const response = await fetch('/api/test-connection', { method: 'POST' });
                const result = await response.json();
                
                showDebugInfo(result);
                
                if (result.status === 'success') {
                    showStatus('✅ API connection successful!');
                } else {
                    showStatus('❌ API connection failed: ' + result.message, 'error');
                }
            } catch (error) {
                showStatus('API test error: ' + error.message, 'error');
            }
        }

        async function debugLocationsCall() {
            try {
                showStatus('Debugging locations API...', 'success');
                const response = await fetch('/api/debug-locations', { method: 'POST' });
                const result = await response.json();
                
                showDebugInfo(result);
                
                if (result.locations_found > 0) {
                    showStatus('✅ Found ' + result.locations_found + ' locations');
                    loadLocations(); // Refresh location dropdown
                } else {
                    showStatus('❌ No locations found - check debug info', 'error');
                }
            } catch (error) {
                showStatus('Locations debug error: ' + error.message, 'error');
            }
        }

        async function debugContactsCall() {
            try {
                const locationId = document.getElementById('locationFilter').value;
                if (locationId === 'all') {
                    showStatus('Please select a specific location to debug contacts', 'error');
                    return;
                }
                
                showStatus('Debugging contacts API for selected location...', 'success');
                const response = await fetch('/api/debug-contacts', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ location_id: locationId })
                });
                const result = await response.json();
                
                showDebugInfo(result);
                
                if (result.contacts_found > 0) {
                    showStatus('✅ Found ' + result.contacts_found + ' contacts');
                    loadDashboard(); // Refresh dashboard
                } else {
                    showStatus('❌ No contacts found - check debug info', 'error');
                }
            } catch (error) {
                showStatus('Contacts debug error: ' + error.message, 'error');
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
            (client_key, access_token, refresh_token, expires_at, location_id, company_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (client_key, tokens['access_token'], tokens['refresh_token'],
              expires_at, tokens.get('locationId'), tokens.get('companyId')))
        conn.commit()
        conn.close()
        
        return f'''
        <div style="text-align: center; padding: 50px; font-family: Arial;">
            <h1>✅ OAuth Installation Successful!</h1>
            <p>Company ID: {tokens.get('companyId', 'Unknown')}</p>
            <p>Location ID: {tokens.get('locationId', 'Not specified')}</p>
            <p>Scopes: {tokens.get('scope', 'Unknown')}</p>
            <br>
            <a href="/dashboard" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">
                🔍 Open Debug Dashboard
            </a>
            <br><br>
            <a href="/debug" style="background: #6c757d; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">
                🛠️ View Debug Info
            </a>
        </div>
        '''
        
    except Exception as e:
        return f"<h1>Installation Failed</h1><p>{str(e)}</p>"

# API Routes
@app.route('/api/locations')
def api_locations():
    locations = analytics.get_locations()
    return jsonify(locations)

@app.route('/api/stats')
def api_stats():
    location_id = request.args.get('location', 'all')
    stats = analytics.get_basic_stats(location_id)
    return jsonify(stats)

@app.route('/api/test-connection', methods=['POST'])
def api_test_connection():
    """Test basic API connectivity"""
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    user_data = analytics.test_api_connection(token_data['access_token'])
    
    if user_data:
        return jsonify({
            'status': 'success',
            'message': 'API connection successful',
            'user_data': user_data,
            'token_company_id': token_data.get('company_id'),
            'api_company_id': user_data.get('companyId')
        })
    else:
        return jsonify({'status': 'error', 'message': 'API connection failed'})

@app.route('/api/debug-locations', methods=['POST'])
def api_debug_locations():
    """Debug locations API"""
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    company_id = token_data.get('company_id')
    if not company_id:
        return jsonify({'status': 'error', 'message': 'No company ID found in token'})
    
    locations = analytics.debug_locations_api(token_data['access_token'], company_id)
    
    # Save found locations to database
    if locations:
        conn = sqlite3.connect(analytics.db_path)
        cursor = conn.cursor()
        
        for loc in locations:
            location_id = loc.get('_id') or loc.get('id') or loc.get('locationId')
            location_name = loc.get('name', 'Unknown Location')
            
            cursor.execute('''
                INSERT OR REPLACE INTO locations 
                (location_id, location_name, company_id, last_synced)
                VALUES (?, ?, ?, ?)
            ''', (location_id, location_name, company_id, datetime.now()))
        
        conn.commit()
        conn.close()
    
    return jsonify({
        'status': 'success',
        'locations_found': len(locations),
        'company_id': company_id,
        'sample_locations': locations[:3] if locations else [],
        'message': f'Found {len(locations)} locations'
    })

@app.route('/api/debug-contacts', methods=['POST'])
def api_debug_contacts():
    """Debug contacts API for a specific location"""
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    data = request.json
    location_id = data.get('location_id')
    
    if not location_id:
        return jsonify({'status': 'error', 'message': 'Location ID required'})
    
    contacts = analytics.debug_contacts_api(token_data['access_token'], location_id)
    
    # Save found contacts to database
    saved_count = 0
    for contact in contacts:
        if analytics.add_contact(contact, location_id):
            saved_count += 1
    
    return jsonify({
        'status': 'success',
        'contacts_found': len(contacts),
        'contacts_saved': saved_count,
        'location_id': location_id,
        'sample_contacts': [
            {
                'id': c.get('id'),
                'name': f"{c.get('firstName', '')} {c.get('lastName', '')}".strip(),
                'email': c.get('email', ''),
                'phone': c.get('phone', '')
            } for c in contacts[:3]
        ] if contacts else [],
        'message': f'Found {len(contacts)} contacts, saved {saved_count}'
    })

@app.route('/health')
def health_check():
    try:
        token_data = get_valid_token()
        debug_logs = analytics.get_debug_logs(5)
        
        conn = sqlite3.connect(analytics.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM contacts')
        total_contacts = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM locations')
        total_locations = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'base_url': BASE_URL,
            'version': 'Debug v1.0 - API TROUBLESHOOTING',
            'database_health': {
                'total_contacts': total_contacts,
                'total_locations': total_locations
            },
            'oauth_status': 'valid' if token_data else 'missing',
            'company_id': token_data.get('company_id') if token_data else None,
            'recent_api_calls': debug_logs,
            'debug_endpoints': [
                f'{BASE_URL}/debug',
                f'{BASE_URL}/api/test-connection',
                f'{BASE_URL}/api/debug-locations',
                f'{BASE_URL}/api/debug-contacts'
            ]
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🔍 Debug Lead Analytics starting on port {port}")
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"📊 Dashboard: {BASE_URL}/dashboard")
    print(f"🛠️ Debug Info: {BASE_URL}/debug")
    print(f"❤️ Health: {BASE_URL}/health")
    print("🎯 MISSION: Find out why contacts aren't showing!")
    
    app.run(host='0.0.0.0', port=port, debug=True)
