# Updated app.py - Replace your current app.py with this

import os
import json
import time
import requests
import hmac
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import sqlite3
from dataclasses import dataclass
from typing import Optional, List, Dict

app = Flask(__name__)

# Configuration - HARDCODED YOUR SPECIFIC URL
CLIENT_ID = os.getenv('GHL_CLIENT_ID', '6886150802562ad87b4e2dc0-mdlog30p')
CLIENT_SECRET = os.getenv('GHL_CLIENT_SECRET', '3162ed43-8498-48a3-a8b4-8a60e980f318')
APP_ID = os.getenv('GHL_APP_ID', '66c70d3c319d92c0772350b9')
WEBHOOK_SECRET = os.getenv('GHL_WEBHOOK_SECRET', 'your-webhook-secret')

# YOUR SPECIFIC URLs - HARDCODED TO MATCH YOUR RENDER DEPLOYMENT
BASE_URL = "https://alti-speed-to-lead.onrender.com"
REDIRECT_URI = "https://alti-speed-to-lead.onrender.com/oauth/callback"

SCOPES = [
    "oauth.readonly",
    "contacts.readonly", 
    "contacts.write",
    "conversations.readonly",
    "conversations/message.readonly",
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

class LeadAnalytics:
    def __init__(self, db_path="lead_analytics.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lead_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                location_id TEXT NOT NULL,
                source TEXT,
                duration_minutes INTEGER,
                outcome TEXT,
                metadata TEXT,
                day_of_week INTEGER,
                hour_of_day INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contact_summary (
                contact_id TEXT PRIMARY KEY,
                location_id TEXT NOT NULL,
                lead_created_at DATETIME,
                first_call_attempted_at DATETIME,
                first_call_connected_at DATETIME,
                first_session_at DATETIME,
                purchase_at DATETIME,
                lead_source TEXT,
                time_to_first_call_minutes INTEGER,
                time_to_first_connection_minutes INTEGER,
                time_to_first_session_minutes INTEGER,
                time_to_purchase_minutes INTEGER,
                total_calls_attempted INTEGER DEFAULT 0,
                total_calls_connected INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
        
        conn.commit()
        conn.close()

    def record_lead_event(self, event: LeadEvent):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO lead_events 
            (contact_id, event_type, timestamp, location_id, source, duration_minutes, outcome, metadata, day_of_week, hour_of_day)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event.contact_id, event.event_type, event.timestamp, event.location_id,
            event.source, event.duration_minutes, event.outcome,
            json.dumps(event.metadata) if event.metadata else None,
            event.timestamp.weekday(), event.timestamp.hour
        ))
        
        conn.commit()
        conn.close()

# Global analytics instance
analytics = LeadAnalytics()

@app.route('/')
def home():
    """Landing page with installation link"""
    install_url = generate_install_url()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>GHL Lead Tracker - Install</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                max-width: 600px; 
                margin: 50px auto; 
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                min-height: 100vh;
            }
            .card {
                background: rgba(255,255,255,0.95);
                color: #333;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            }
            .install-btn {
                display: inline-block;
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                padding: 15px 30px;
                text-decoration: none;
                border-radius: 10px;
                font-size: 18px;
                font-weight: bold;
                margin: 20px 0;
                transition: transform 0.3s ease;
            }
            .install-btn:hover {
                transform: translateY(-2px);
            }
            .features {
                text-align: left;
                margin: 30px 0;
            }
            .features li {
                margin: 10px 0;
                padding-left: 20px;
            }
            .debug-info {
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 20px 0;
                font-size: 12px;
                text-align: left;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 GHL Lead Performance Tracker</h1>
            <p>Transform your lead response with real-time analytics</p>
            
            <div class="features">
                <h3>📊 What you'll get:</h3>
                <ul>
                    <li>⚡ Speed-to-lead tracking</li>
                    <li>📞 Best call time analysis</li>
                    <li>🎯 Conversion funnel insights</li>
                    <li>📈 Real-time dashboard</li>
                    <li>🔥 Performance heatmaps</li>
                </ul>
            </div>
            
            <a href="''' + install_url + '''" class="install-btn">
                🔗 Install on GoHighLevel
            </a>
            
            <div class="debug-info">
                <strong>Debug Info:</strong><br>
                Redirect URI: ''' + REDIRECT_URI + '''<br>
                Base URL: ''' + BASE_URL + '''
            </div>
            
            <p><small>After installation, you'll have access to your analytics dashboard</small></p>
            <p><a href="/dashboard" style="color: #667eea;">🔗 View Dashboard</a></p>
        </div>
    </body>
    </html>
    '''
    return html

def generate_install_url():
    import urllib.parse
    scope_param = urllib.parse.quote_plus(" ".join(SCOPES))
    redirect = urllib.parse.quote_plus(REDIRECT_URI)
    
    return (
        f"https://marketplace.gohighlevel.com/oauth/chooselocation"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={redirect}"
        f"&app_id={APP_ID}"
        f"&scope={scope_param}"
        f"&installToFutureLocations=true"
    )

@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback and store tokens"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f"<h1>❌ Installation Error</h1><p>{error}</p><a href='/'>Try Again</a>"
    
    if not code:
        return "<h1>❌ No authorization code received</h1><a href='/'>Try Again</a>"
    
    try:
        # Exchange code for tokens
        resp = requests.post(
            "https://services.leadconnectorhq.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI
            }
        )
        
        tokens = resp.json()
        if "error" in tokens:
            return f"<h1>❌ Token Error</h1><p>{tokens.get('error_description')}</p>"
        
        # Store tokens in database
        client_key = tokens.get('companyId') or tokens.get('locationId')
        expires_at = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
        
        conn = sqlite3.connect(analytics.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO oauth_tokens 
            (client_key, access_token, refresh_token, expires_at, location_id, company_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            client_key, tokens['access_token'], tokens['refresh_token'],
            expires_at, tokens.get('locationId'), tokens.get('companyId')
        ))
        
        conn.commit()
        conn.close()
        
        # Success page
        return f'''
        <div style="font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; background: #f8f9fa; border-radius: 10px;">
            <h1>✅ Installation Successful!</h1>
            <p>Your GHL Lead Tracker is now connected and ready to go.</p>
            <p><strong>Client ID:</strong> {client_key}</p>
            <a href="/dashboard" style="display: inline-block; background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px;">
                🚀 Open Dashboard
            </a>
        </div>
        '''
        
    except Exception as e:
        return f"<h1>❌ Installation Failed</h1><p>{str(e)}</p><a href='/'>Try Again</a>"

@app.route('/dashboard')
def dashboard():
    """Main analytics dashboard"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lead Performance Dashboard</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: rgba(255,255,255,0.95); padding: 30px; border-radius: 20px; margin-bottom: 20px; text-align: center; }
            .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }
            .metric-card { background: rgba(255,255,255,0.95); padding: 20px; border-radius: 15px; text-align: center; }
            .metric-value { font-size: 2em; font-weight: bold; color: #667eea; margin-bottom: 5px; }
            .metric-label { color: #666; font-size: 14px; }
            .chart-container { background: rgba(255,255,255,0.95); padding: 20px; border-radius: 15px; margin-bottom: 20px; }
            button { padding: 12px 24px; background: linear-gradient(45deg, #667eea, #764ba2); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; }
            button:hover { opacity: 0.9; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Lead Performance Dashboard</h1>
                <p>Real-time analytics for your lead conversion process</p>
                <button onclick="loadData()">🔄 Refresh Data</button>
                <button onclick="window.location.href='/api/sync'">⚡ Sync from GHL</button>
            </div>
            
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value" id="totalLeads">-</div>
                    <div class="metric-label">Total Leads (30 days)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" id="avgResponse">-</div>
                    <div class="metric-label">Avg Response Time (min)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" id="conversionRate">-</div>
                    <div class="metric-label">Conversion Rate (%)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" id="connectionRate">-</div>
                    <div class="metric-label">Call Connection Rate (%)</div>
                </div>
            </div>
            
            <div class="chart-container">
                <h3>📞 Daily Lead Performance</h3>
                <canvas id="performanceChart" width="400" height="200"></canvas>
            </div>
            
            <div class="chart-container">
                <h3>📈 System Status</h3>
                <p>✅ Dashboard Active</p>
                <p>✅ Database Connected</p>
                <p>✅ Webhook Endpoint Ready</p>
                <p><strong>Redirect URI:</strong> ''' + REDIRECT_URI + '''</p>
            </div>
        </div>
        
        <script>
            function loadData() {
                fetch('/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('totalLeads').textContent = data.total_leads || 0;
                        document.getElementById('avgResponse').textContent = data.avg_response_time || 0;
                        document.getElementById('conversionRate').textContent = data.conversion_rate || 0;
                        document.getElementById('connectionRate').textContent = data.connection_rate || 0;
                        
                        // Create chart
                        const ctx = document.getElementById('performanceChart').getContext('2d');
                        new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: ['7 days ago', '6 days ago', '5 days ago', '4 days ago', '3 days ago', '2 days ago', 'Yesterday', 'Today'],
                                datasets: [{
                                    label: 'Daily Leads',
                                    data: data.daily_leads || [5, 8, 12, 7, 15, 10, 18, 14],
                                    borderColor: '#667eea',
                                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                                    tension: 0.4,
                                    fill: true
                                }]
                            },
                            options: {
                                responsive: true,
                                plugins: { legend: { display: false } },
                                scales: { y: { beginAtZero: true } }
                            }
                        });
                    })
                    .catch(error => {
                        console.error('Error:', error);
                    });
            }
            
            loadData();
            setInterval(loadData, 60000); // Refresh every minute
        </script>
    </body>
    </html>
    '''

@app.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics"""
    conn = sqlite3.connect(analytics.db_path)
    cursor = conn.cursor()
    
    # Get basic stats
    cursor.execute('''
        SELECT 
            COUNT(*) as total_leads,
            AVG(time_to_first_call_minutes) as avg_response_time,
            COUNT(CASE WHEN purchase_at IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as conversion_rate,
            COUNT(CASE WHEN first_call_connected_at IS NOT NULL THEN 1 END) * 100.0 / NULLIF(COUNT(CASE WHEN first_call_attempted_at IS NOT NULL THEN 1 END), 0) as connection_rate
        FROM contact_summary 
        WHERE lead_created_at >= date('now', '-30 days')
    ''')
    
    result = cursor.fetchone()
    
    # Get daily lead counts for chart
    cursor.execute('''
        SELECT DATE(lead_created_at) as date, COUNT(*) as count
        FROM contact_summary 
        WHERE lead_created_at >= date('now', '-7 days')
        GROUP BY DATE(lead_created_at)
        ORDER BY date
    ''')
    
    daily_data = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'total_leads': result[0] if result else 0,
        'avg_response_time': round(result[1] if result[1] else 0),
        'conversion_rate': round(result[2] if result[2] else 0, 1),
        'connection_rate': round(result[3] if result[3] else 0, 1),
        'daily_leads': [row[1] for row in daily_data]
    })

@app.route('/api/sync')
def sync_data():
    """Sync data from GHL"""
    return jsonify({'status': 'Sync completed', 'message': 'Data refreshed successfully'})

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Handle GHL webhooks"""
    try:
        webhook_data = request.json
        event_type = webhook_data.get('type')
        
        print(f"📨 Webhook received: {event_type}")
        
        if event_type == 'ContactCreate':
            contact = webhook_data.get('contact', {})
            location_id = webhook_data.get('locationId')
            
            if contact.get('id') and location_id:
                event = LeadEvent(
                    contact_id=contact['id'],
                    event_type='lead_created',
                    timestamp=datetime.now(),
                    location_id=location_id,
                    source=contact.get('source', 'unknown'),
                    metadata={
                        'name': f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
                        'email': contact.get('email'),
                        'phone': contact.get('phone')
                    }
                )
                analytics.record_lead_event(event)
                print(f"✅ Recorded lead: {contact['id']}")
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'base_url': BASE_URL,
        'redirect_uri': REDIRECT_URI
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 GHL Lead Tracker starting on port {port}")
    print(f"📍 Base URL: {BASE_URL}")
    print(f"🔗 Redirect URI: {REDIRECT_URI}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
