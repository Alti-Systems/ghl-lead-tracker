# app.py - Simplified Lead Analytics - GET DATA SHOWING FIRST
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

class SimpleLeadAnalytics:
    def __init__(self, db_path="simple_analytics.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # SIMPLE: Just track contacts and basic info
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
            CREATE TABLE IF NOT EXISTS webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                contact_id TEXT,
                location_id TEXT,
                raw_data TEXT,
                received_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Simple database initialized")
    
    def add_contact(self, contact_data, location_id):
        """Simple contact addition - just store the data"""
        contact_id = contact_data.get('id')
        if not contact_id:
            print("❌ No contact ID found")
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get location name
        cursor.execute('SELECT location_name FROM locations WHERE location_id = ?', (location_id,))
        loc_result = cursor.fetchone()
        location_name = loc_result[0] if loc_result else 'Unknown Location'
        
        # Insert or update contact
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
        
        print(f"✅ CONTACT ADDED: {contact_data.get('firstName', '')} {contact_data.get('lastName', '')} - {location_name}")
        return True
    
    def get_basic_stats(self, location_id=None):
        """Get basic stats that should definitely work"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Base query
        where_clause = "WHERE 1=1"
        params = []
        
        if location_id and location_id != 'all':
            where_clause += " AND location_id = ?"
            params.append(location_id)
        
        # Total contacts
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause}", params)
        total_contacts = cursor.fetchone()[0]
        
        # Contacts with phone
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND phone IS NOT NULL AND phone != ''", params)
        contacts_with_phone = cursor.fetchone()[0]
        
        # Contacts with email
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND email IS NOT NULL AND email != ''", params)
        contacts_with_email = cursor.fetchone()[0]
        
        # Contacts with both phone AND email
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND phone IS NOT NULL AND phone != '' AND email IS NOT NULL AND email != ''", params)
        contacts_with_both = cursor.fetchone()[0]
        
        # New contacts today
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND date(created_at) = date('now')", params)
        new_today = cursor.fetchone()[0]
        
        # New contacts this week
        cursor.execute(f"SELECT COUNT(*) FROM contacts {where_clause} AND created_at >= date('now', '-7 days')", params)
        new_this_week = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_contacts': total_contacts,
            'contacts_with_phone': contacts_with_phone,
            'contacts_with_email': contacts_with_email,
            'contacts_with_both': contacts_with_both,
            'new_today': new_today,
            'new_this_week': new_this_week,
            'phone_rate': round(contacts_with_phone * 100.0 / max(total_contacts, 1), 1),
            'email_rate': round(contacts_with_email * 100.0 / max(total_contacts, 1), 1),
            'complete_rate': round(contacts_with_both * 100.0 / max(total_contacts, 1), 1)
        }
    
    def sync_locations(self, access_token, company_id=None):
        """Enhanced location sync with pagination to get ALL sub-accounts"""
        print("🔄 Syncing ALL locations with pagination...")
        headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-04-15"}
        all_locations = []
        
        try:
            if company_id:
                url = "https://services.leadconnectorhq.com/oauth/installedLocations"
                
                skip = 0
                limit = 100
                
                while True:
                    params = {
                        "companyId": company_id, 
                        "appId": APP_ID, 
                        "isInstalled": True,
                        "skip": skip,
                        "limit": limit
                    }
                    
                    resp = requests.get(url, headers=headers, params=params)
                    print(f"📡 Location API: {resp.status_code} - Skip: {skip}, Limit: {limit}")
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        locations = data.get('locations', []) if isinstance(data, dict) else data
                        
                        if not locations:
                            print(f"📍 No more locations found at skip={skip}")
                            break
                            
                        all_locations.extend(locations)
                        print(f"📊 Found {len(locations)} locations. Total so far: {len(all_locations)}")
                        
                        # If we got less than the limit, we're done
                        if len(locations) < limit:
                            break
                            
                        skip += limit
                        time.sleep(0.2)  # Rate limiting
                    else:
                        print(f"❌ API Error: {resp.status_code} - {resp.text}")
                        break
                
                # Save all locations to database
                if all_locations:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    
                    for loc in all_locations:
                        location_id = loc.get('_id') or loc.get('id') or loc.get('locationId')
                        location_name = loc.get('name', 'Unknown Location')
                        
                        cursor.execute('''
                            INSERT OR REPLACE INTO locations 
                            (location_id, location_name, company_id, last_synced)
                            VALUES (?, ?, ?, ?)
                        ''', (location_id, location_name, company_id, datetime.now()))
                        
                        print(f"💾 Saved location: {location_name} ({location_id})")
                    
                    conn.commit()
                    conn.close()
                    
                    print(f"✅ Successfully synced {len(all_locations)} total locations!")
                    return len(all_locations)
            
            return 0
        except Exception as e:
            print(f"❌ Location sync error: {e}")
            return 0
    
    def fetch_all_contacts_from_ghl(self, access_token, location_id):
        """ENHANCED: Fetch ALL contacts from GHL with better pagination and error handling"""
        print(f"📥 Fetching ALL contacts from GHL for location: {location_id}")
        headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-04-15"}
        
        try:
            # Use the correct contacts endpoint
            url = f"https://services.leadconnectorhq.com/contacts/"
            
            total_fetched = 0
            start_after_id = None
            
            while True:
                params = {
                    "locationId": location_id,
                    "limit": 100
                }
                
                if start_after_id:
                    params['startAfterId'] = start_after_id
                
                print(f"📡 Fetching contacts: {params}")
                resp = requests.get(url, headers=headers, params=params)
                print(f"📊 Contacts API Response: {resp.status_code}")
                
                if resp.status_code == 200:
                    data = resp.json()
                    contacts = data.get('contacts', [])
                    
                    print(f"📦 Received {len(contacts)} contacts in this batch")
                    
                    if not contacts:
                        print("📭 No more contacts found")
                        break
                    
                    # Add each contact to our database
                    for contact in contacts:
                        try:
                            success = self.add_contact(contact, location_id)
                            if success:
                                total_fetched += 1
                            # Get the last contact ID for pagination
                            start_after_id = contact.get('id')
                        except Exception as contact_error:
                            print(f"❌ Error adding contact {contact.get('id', 'unknown')}: {contact_error}")
                    
                    print(f"📊 Total fetched so far: {total_fetched}")
                    
                    # Check if we should continue (if we got fewer than limit, we're done)
                    if len(contacts) < 100:
                        print("📄 Last page reached (fewer than 100 contacts)")
                        break
                    
                    time.sleep(0.3)  # Rate limiting
                    
                elif resp.status_code == 429:
                    print("⏳ Rate limited, waiting 2 seconds...")
                    time.sleep(2)
                    continue
                    
                else:
                    print(f"❌ API Error: {resp.status_code}")
                    print(f"Response: {resp.text}")
                    break
            
            print(f"✅ TOTAL CONTACTS FETCHED: {total_fetched}")
            return total_fetched
            
        except Exception as e:
            print(f"❌ Error fetching contacts: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    def get_locations(self):
        """Get all locations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT location_id, location_name, last_synced FROM locations ORDER BY location_name')
        locations = cursor.fetchall()
        conn.close()
        
        return [{'id': loc[0], 'name': loc[1], 'last_synced': loc[2]} for loc in locations]
    
    def log_webhook(self, event_type, contact_id, location_id, raw_data):
        """Simple webhook logging"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO webhook_events (event_type, contact_id, location_id, raw_data)
            VALUES (?, ?, ?, ?)
        ''', (event_type, contact_id, location_id, json.dumps(raw_data)))
        
        conn.commit()
        conn.close()

# Global instance
analytics = SimpleLeadAnalytics()

# Token functions (same as before)
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
        <title>Simple Lead Analytics</title>
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
            <h1>Simple Lead Analytics</h1>
            <p>Basic contact tracking that actually works</p>
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
    <title>Simple Lead Dashboard</title>
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Simple Lead Analytics</h1>
            <p>Let's get the basic data showing first!</p>
        </div>

        <div class="controls">
            <label>Location:</label>
            <select id="locationFilter">
                <option value="all">Loading locations...</option>
            </select>
            
            <button onclick="loadDashboard()">🔄 Refresh Data</button>
            <button onclick="syncLocations()">📍 Sync Locations</button>
            <button onclick="fetchSelectedContacts()">📥 Fetch Contacts (Selected)</button>
            <button onclick="fetchAllContacts()">📥 Fetch ALL Locations</button>
            <button onclick="createTestContact()">🧪 Create Test Contact</button>
        </div>

        <div id="status"></div>

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
            setTimeout(() => statusDiv.innerHTML = '', 5000);
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
                
                if (locations.length === 0) {
                    showStatus('No locations found. Please sync locations first.', 'error');
                }
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
                showStatus('Dashboard updated successfully!');
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
                    sub: 'All contacts in database'
                },
                { 
                    label: 'With Phone Number', 
                    value: currentData.contacts_with_phone || 0,
                    sub: (currentData.phone_rate || 0) + '% of total'
                },
                { 
                    label: 'With Email Address', 
                    value: currentData.contacts_with_email || 0,
                    sub: (currentData.email_rate || 0) + '% of total'
                },
                { 
                    label: 'Complete Contacts', 
                    value: currentData.contacts_with_both || 0,
                    sub: 'Both phone & email (' + (currentData.complete_rate || 0) + '%)'
                },
                { 
                    label: 'New Today', 
                    value: currentData.new_today || 0,
                    sub: 'Contacts added today'
                },
                { 
                    label: 'New This Week', 
                    value: currentData.new_this_week || 0,
                    sub: 'Last 7 days'
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
        }

        async function syncLocations() {
            try {
                showStatus('Syncing locations...', 'success');
                const response = await fetch('/api/sync-locations', { method: 'POST' });
                const result = await response.json();
                
                if (result.status === 'success') {
                    showStatus('Synced ' + result.count + ' locations successfully!');
                    loadLocations();
                } else {
                    showStatus('Sync failed: ' + result.message, 'error');
                }
            } catch (error) {
                showStatus('Sync error: ' + error.message, 'error');
            }
        }

        async function fetchSelectedContacts() {
            try {
                const locationId = document.getElementById('locationFilter').value;
                
                if (locationId === 'all') {
                    showStatus('Use "Fetch ALL Locations" button for all locations, or select a specific location.', 'error');
                    return;
                }
                
                showStatus('Fetching contacts from selected location...', 'success');
                const response = await fetch('/api/fetch-contacts', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ location_id: locationId })
                });
                const result = await response.json();
                
                if (result.status === 'success') {
                    showStatus('Fetched ' + result.count + ' contacts from selected location!');
                    setTimeout(() => loadDashboard(), 1000);
                } else {
                    showStatus('Fetch failed: ' + result.message, 'error');
                }
            } catch (error) {
                showStatus('Fetch error: ' + error.message, 'error');
            }
        }

        async function fetchAllContacts() {
            try {
                showStatus('Fetching contacts from ALL locations... This may take a while.', 'success');
                const response = await fetch('/api/fetch-all-locations-contacts', { method: 'POST' });
                const result = await response.json();
                
                if (result.status === 'success') {
                    showStatus('SUCCESS: Fetched ' + result.total_contacts + ' contacts from ' + result.locations_processed + ' locations!');
                    setTimeout(() => loadDashboard(), 2000);
                } else {
                    showStatus('Fetch failed: ' + result.message, 'error');
                }
            } catch (error) {
                showStatus('Fetch error: ' + error.message, 'error');
            }
        }

        async function createTestContact() {
            try {
                showStatus('Creating test contact...', 'success');
                const response = await fetch('/api/create-test-contact', { method: 'POST' });
                const result = await response.json();
                
                if (result.status === 'success') {
                    showStatus('Test contact created: ' + result.contact_id);
                    setTimeout(() => loadDashboard(), 1000);
                } else {
                    showStatus('Test contact creation failed: ' + result.message, 'error');
                }
            } catch (error) {
                showStatus('Test error: ' + error.message, 'error');
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
        
        locations_synced = analytics.sync_locations(tokens['access_token'], tokens.get('companyId'))
        
        return f'''
        <div style="text-align: center; padding: 50px; font-family: Arial;">
            <h1>✅ Installation Successful!</h1>
            <p>Locations Synced: {locations_synced}</p>
            <p><strong>Next steps:</strong></p>
            <p>1. Setup webhook URL: <code>{BASE_URL}/webhook</code></p>
            <p>2. Subscribe to: ContactCreate, ContactUpdate</p>
            <br>
            <a href="/dashboard" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">
                📊 Open Dashboard
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

@app.route('/api/sync-locations', methods=['POST'])
def api_sync_locations():
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    count = analytics.sync_locations(token_data['access_token'], token_data.get('company_id'))
    return jsonify({'status': 'success', 'count': count})

@app.route('/api/fetch-contacts', methods=['POST'])
def api_fetch_contacts():
    """Fetch ALL contacts from GHL - either one location or all locations"""
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    data = request.json
    location_id = data.get('location_id')
    
    if location_id == 'all':
        # Fetch from ALL locations
        locations = analytics.get_locations()
        total_count = 0
        
        for location in locations:
            print(f"🔄 Fetching contacts for location: {location['name']}")
            count = analytics.fetch_all_contacts_from_ghl(token_data['access_token'], location['id'])
            total_count += count
            time.sleep(0.5)  # Rate limiting between locations
        
        return jsonify({
            'status': 'success', 
            'count': total_count,
            'locations_processed': len(locations),
            'message': f'Fetched {total_count} contacts from {len(locations)} locations'
        })
    
    elif location_id:
        # Fetch from specific location
        count = analytics.fetch_all_contacts_from_ghl(token_data['access_token'], location_id)
        return jsonify({
            'status': 'success', 
            'count': count,
            'message': f'Fetched {count} contacts from selected location'
        })
    
    else:
        return jsonify({'status': 'error', 'message': 'Location ID required'})

@app.route('/api/fetch-all-locations-contacts', methods=['POST'])
def api_fetch_all_locations_contacts():
    """NEW: Fetch contacts from ALL locations at once"""
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    locations = analytics.get_locations()
    if not locations:
        return jsonify({'status': 'error', 'message': 'No locations found. Please sync locations first.'})
    
    total_contacts = 0
    results = []
    
    for location in locations:
        try:
            print(f"🔄 Processing location: {location['name']} ({location['id']})")
            count = analytics.fetch_all_contacts_from_ghl(token_data['access_token'], location['id'])
            total_contacts += count
            
            results.append({
                'location_name': location['name'],
                'location_id': location['id'],
                'contacts_fetched': count
            })
            
            # Rate limiting between locations
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Error processing location {location['name']}: {e}")
            results.append({
                'location_name': location['name'],
                'location_id': location['id'],
                'contacts_fetched': 0,
                'error': str(e)
            })
    
    return jsonify({
        'status': 'success',
        'total_contacts': total_contacts,
        'locations_processed': len(locations),
        'results': results,
        'message': f'Fetched {total_contacts} total contacts from {len(locations)} locations'
    })

@app.route('/api/create-test-contact', methods=['POST'])
def api_create_test_contact():
    """Create a test contact for testing"""
    locations = analytics.get_locations()
    if not locations:
        return jsonify({'status': 'error', 'message': 'No locations available'})
    
    test_contact = {
        'id': f'test_{int(time.time())}',
        'firstName': 'Test',
        'lastName': 'Contact',
        'email': f'test{int(time.time())}@example.com',
        'phone': '+1234567890',
        'source': 'manual_test',
        'dateAdded': datetime.now().isoformat(),
        'customFields': [],
        'tags': ['test']
    }
    
    success = analytics.add_contact(test_contact, locations[0]['id'])
    
    if success:
        return jsonify({'status': 'success', 'contact_id': test_contact['id']})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to create test contact'})

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    try:
        webhook_data = request.json
        event_type = webhook_data.get('type')
        contact_id = webhook_data.get('contactId') or webhook_data.get('contact', {}).get('id')
        location_id = webhook_data.get('locationId')
        
        print(f"🔔 WEBHOOK: {event_type} | Contact: {contact_id} | Location: {location_id}")
        
        # Log all webhooks
        analytics.log_webhook(event_type, contact_id, location_id, webhook_data)
        
        # Handle contact events
        if event_type in ['ContactCreate', 'ContactUpdate']:
            contact = webhook_data.get('contact', {})
            if contact.get('id') and location_id:
                success = analytics.add_contact(contact, location_id)
                if success:
                    print(f"✅ CONTACT PROCESSED: {contact.get('firstName', '')} {contact.get('lastName', '')}")
        
        return jsonify({'status': 'success', 'message': f'Webhook {event_type} processed'})
        
    except Exception as e:
        print(f"❌ WEBHOOK ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    try:
        conn = sqlite3.connect(analytics.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM contacts')
        total_contacts = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM locations')
        total_locations = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM webhook_events WHERE date(received_at) = date("now")')
        webhooks_today = cursor.fetchone()[0]
        
        conn.close()
        
        token_data = get_valid_token()
        token_status = 'valid' if token_data else 'missing'
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'base_url': BASE_URL,
            'webhook_url': f'{BASE_URL}/webhook',
            'version': 'Simple v1.0 - GET DATA WORKING',
            'database_health': {
                'total_contacts': total_contacts,
                'total_locations': total_locations,
                'webhooks_today': webhooks_today
            },
            'oauth_status': token_status,
            'next_steps': [
                'Install OAuth tokens',
                'Sync locations',
                'Fetch existing contacts', 
                'Setup webhooks in GHL'
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
    print(f"🚀 Simple Lead Analytics starting on port {port}")
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"📡 Webhook URL: {BASE_URL}/webhook")
    print(f"📊 Dashboard: {BASE_URL}/dashboard")
    print(f"❤️ Health: {BASE_URL}/health")
    print("🎯 FOCUS: Get basic contact data showing first!")
    
    app.run(host='0.0.0.0', port=port, debug=False)
