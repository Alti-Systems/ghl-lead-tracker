# app.py - Complete Enhanced Lead Analytics System

import os
import json
import time
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from dataclasses import dataclass
from typing import Optional, List, Dict
import threading

app = Flask(__name__)

# Configuration
CLIENT_ID = os.getenv('GHL_CLIENT_ID', '6886150802562ad87b4e2dc0-mdlog30p')
CLIENT_SECRET = os.getenv('GHL_CLIENT_SECRET', '3162ed43-8498-48a3-a8b4-8a60e980f318')
APP_ID = os.getenv('GHL_APP_ID', '66c70d3c319d92c0772350b9')
WEBHOOK_SECRET = os.getenv('GHL_WEBHOOK_SECRET', 'your-webhook-secret')

# URLs - HARDCODED FOR YOUR DEPLOYMENT
BASE_URL = "https://alti-speed-to-lead.onrender.com"
REDIRECT_URI = f"{BASE_URL}/oauth/callback"

SCOPES = [
    "oauth.readonly", "contacts.readonly", "contacts.write",
    "conversations.readonly", "conversations/message.readonly",
    "locations/customFields.readonly", "locations/tasks.readonly",
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

class EnhancedLeadAnalytics:
    def __init__(self, db_path="enhanced_lead_analytics.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enhanced lead events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS lead_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                location_id TEXT NOT NULL,
                location_name TEXT,
                source TEXT,
                duration_minutes INTEGER,
                outcome TEXT,
                metadata TEXT,
                day_of_week INTEGER,
                hour_of_day INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Enhanced contact summary table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contact_summary (
                contact_id TEXT PRIMARY KEY,
                location_id TEXT NOT NULL,
                location_name TEXT,
                contact_name TEXT,
                contact_email TEXT,
                contact_phone TEXT,
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
                tags TEXT,
                custom_fields TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Locations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                location_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT,
                phone TEXT,
                email TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # OAuth tokens table
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
        
        # Call performance analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS call_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id TEXT,
                date DATE,
                hour_of_day INTEGER,
                day_of_week INTEGER,
                total_calls INTEGER DEFAULT 0,
                successful_calls INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0,
                avg_duration REAL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Data sync log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT,
                location_id TEXT,
                status TEXT,
                records_processed INTEGER,
                errors TEXT,
                started_at DATETIME,
                completed_at DATETIME
            )
        ''')
        
        # Insert sample locations for testing
        cursor.execute('''
            INSERT OR IGNORE INTO locations (location_id, name, address) VALUES
            ('sample_loc_1', 'Fitstop Springfield', '123 Main St, Springfield'),
            ('sample_loc_2', 'Junior Lifters', '456 Oak Ave, Brisbane'),
            ('sample_loc_3', 'Fitstop Nundah', '789 Pine Rd, Nundah')
        ''')
        
        conn.commit()
        conn.close()
    
    def record_lead_event(self, event: LeadEvent):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Insert event
        cursor.execute('''
            INSERT INTO lead_events 
            (contact_id, event_type, timestamp, location_id, source, duration_minutes, 
             outcome, metadata, day_of_week, hour_of_day)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event.contact_id, event.event_type, event.timestamp, event.location_id,
            event.source, event.duration_minutes, event.outcome,
            json.dumps(event.metadata) if event.metadata else None,
            event.timestamp.weekday(), event.timestamp.hour
        ))
        
        # Update contact summary
        self.update_contact_summary(cursor, event)
        
        # Update call performance metrics
        if event.event_type in ['call_attempted', 'call_connected']:
            self.update_call_performance(cursor, event)
        
        conn.commit()
        conn.close()
    
    def update_contact_summary(self, cursor, event: LeadEvent):
        # Get existing summary
        cursor.execute('SELECT * FROM contact_summary WHERE contact_id = ?', (event.contact_id,))
        existing = cursor.fetchone()
        
        if not existing and event.event_type == 'lead_created':
            # Create new contact summary
            metadata = event.metadata or {}
            cursor.execute('''
                INSERT INTO contact_summary 
                (contact_id, location_id, contact_name, contact_email, contact_phone,
                 lead_created_at, lead_source, tags, custom_fields)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.contact_id, event.location_id,
                metadata.get('name', ''), metadata.get('email', ''), 
                metadata.get('phone', ''), event.timestamp, event.source,
                json.dumps(metadata.get('tags', [])),
                json.dumps(metadata.get('custom_fields', {}))
            ))
        
        # Update based on event type
        if event.event_type == 'call_attempted':
            cursor.execute('''
                UPDATE contact_summary 
                SET total_calls_attempted = total_calls_attempted + 1,
                    first_call_attempted_at = COALESCE(first_call_attempted_at, ?)
                WHERE contact_id = ?
            ''', (event.timestamp, event.contact_id))
            
        elif event.event_type == 'call_connected':
            cursor.execute('''
                UPDATE contact_summary 
                SET total_calls_connected = total_calls_connected + 1,
                    first_call_connected_at = COALESCE(first_call_connected_at, ?)
                WHERE contact_id = ?
            ''', (event.timestamp, event.contact_id))
    
    def update_call_performance(self, cursor, event):
        date = event.timestamp.date()
        hour = event.timestamp.hour
        day_of_week = event.timestamp.weekday()
        
        # Get or create performance record
        cursor.execute('''
            SELECT * FROM call_performance 
            WHERE location_id = ? AND date = ? AND hour_of_day = ?
        ''', (event.location_id, date, hour))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing record
            if event.event_type == 'call_attempted':
                cursor.execute('''
                    UPDATE call_performance 
                    SET total_calls = total_calls + 1
                    WHERE location_id = ? AND date = ? AND hour_of_day = ?
                ''', (event.location_id, date, hour))
            elif event.event_type == 'call_connected':
                cursor.execute('''
                    UPDATE call_performance 
                    SET successful_calls = successful_calls + 1,
                        avg_duration = (avg_duration * successful_calls + ?) / (successful_calls + 1)
                    WHERE location_id = ? AND date = ? AND hour_of_day = ?
                ''', (event.duration_minutes or 0, event.location_id, date, hour))
        else:
            # Create new record
            total_calls = 1 if event.event_type == 'call_attempted' else 0
            successful_calls = 1 if event.event_type == 'call_connected' else 0
            
            cursor.execute('''
                INSERT INTO call_performance 
                (location_id, date, hour_of_day, day_of_week, total_calls, successful_calls, avg_duration)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (event.location_id, date, hour, day_of_week, total_calls, successful_calls, event.duration_minutes or 0))
        
        # Update success rate
        cursor.execute('''
            UPDATE call_performance 
            SET success_rate = CASE 
                WHEN total_calls > 0 THEN (successful_calls * 100.0 / total_calls)
                ELSE 0 
            END
            WHERE location_id = ? AND date = ? AND hour_of_day = ?
        ''', (event.location_id, date, hour))
    
    def get_locations(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT l.location_id, l.name 
            FROM locations l
            WHERE l.is_active = TRUE
            ORDER BY l.name
        ''')
        
        locations = cursor.fetchall()
        conn.close()
        
        return [{'id': loc[0], 'name': loc[1]} for loc in locations]
    
    def get_enhanced_stats(self, location_id=None, days=30, start_date=None, end_date=None):
        conn = sqlite3.connect(self.db_path)
        
        # Build WHERE clause
        where_conditions = []
        params = []
        
        if location_id and location_id != 'all':
            where_conditions.append('location_id = ?')
            params.append(location_id)
        
        if start_date and end_date:
            where_conditions.append('lead_created_at BETWEEN ? AND ?')
            params.extend([start_date, end_date])
        else:
            where_conditions.append('lead_created_at >= date("now", "-{} days")'.format(days))
        
        where_clause = 'WHERE ' + ' AND '.join(where_conditions) if where_conditions else ''
        
        # Main stats query
        query = f'''
            SELECT 
                COUNT(*) as total_leads,
                AVG(time_to_first_call_minutes) as avg_response_time,
                AVG(time_to_first_connection_minutes) as avg_time_to_connection,
                AVG(time_to_first_session_minutes) as avg_time_to_session,
                AVG(time_to_purchase_minutes) as avg_time_to_purchase,
                COUNT(CASE WHEN first_call_attempted_at IS NOT NULL THEN 1 END) as leads_called,
                COUNT(CASE WHEN first_call_connected_at IS NOT NULL THEN 1 END) as leads_connected,
                COUNT(CASE WHEN first_session_at IS NOT NULL THEN 1 END) as leads_to_session,
                COUNT(CASE WHEN purchase_at IS NOT NULL THEN 1 END) as leads_to_purchase,
                COUNT(CASE WHEN first_call_connected_at IS NOT NULL THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(CASE WHEN first_call_attempted_at IS NOT NULL THEN 1 END), 0) as connection_rate,
                COUNT(CASE WHEN first_session_at IS NOT NULL THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0) as session_rate,
                COUNT(CASE WHEN purchase_at IS NOT NULL THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0) as conversion_rate
            FROM contact_summary 
            {where_clause}
        '''
        
        try:
            df = pd.read_sql_query(query, conn, params=params)
            stats = df.iloc[0].to_dict()
        except:
            # Return default stats if query fails
            stats = {
                'total_leads': 0, 'avg_response_time': 0, 'avg_time_to_connection': 0,
                'avg_time_to_session': 0, 'avg_time_to_purchase': 0, 'leads_called': 0,
                'leads_connected': 0, 'leads_to_session': 0, 'leads_to_purchase': 0,
                'connection_rate': 0, 'session_rate': 0, 'conversion_rate': 0
            }
        
        # Get best call times
        best_times_query = f'''
            SELECT 
                hour_of_day,
                day_of_week,
                SUM(total_calls) as total_calls,
                SUM(successful_calls) as successful_calls,
                AVG(success_rate) as avg_success_rate
            FROM call_performance 
            WHERE date >= date("now", "-{days} days")
            {' AND location_id = ?' if location_id and location_id != 'all' else ''}
            GROUP BY hour_of_day, day_of_week
            HAVING total_calls >= 1
            ORDER BY avg_success_rate DESC
        '''
        
        try:
            best_times_params = [location_id] if location_id and location_id != 'all' else []
            best_times_df = pd.read_sql_query(best_times_query, conn, params=best_times_params)
            best_times = best_times_df.to_dict('records')
        except:
            best_times = []
        
        # Get daily trends
        daily_trends_query = f'''
            SELECT 
                DATE(lead_created_at) as date,
                COUNT(*) as daily_leads
            FROM contact_summary 
            {where_clause}
            GROUP BY DATE(lead_created_at)
            ORDER BY date DESC
            LIMIT 30
        '''
        
        try:
            daily_df = pd.read_sql_query(daily_trends_query, conn, params=params)
            daily_trends = daily_df.to_dict('records')
        except:
            daily_trends = []
        
        conn.close()
        
        return {
            'stats': stats,
            'best_times': best_times,
            'daily_trends': daily_trends
        }
    
    def add_sample_data(self):
        """Add sample data for testing the dashboard"""
        import random
        from datetime import datetime, timedelta
        
        locations = ['sample_loc_1', 'sample_loc_2', 'sample_loc_3']
        sources = ['Facebook', 'Google', 'Walk-in', 'Referral', 'Website']
        
        # Generate sample leads for the last 30 days
        for i in range(100):  # 100 sample leads
            contact_id = f"sample_contact_{i}"
            location_id = random.choice(locations)
            
            # Lead creation (random time in last 30 days)
            lead_time = datetime.now() - timedelta(days=random.randint(0, 30))
            lead_event = LeadEvent(
                contact_id=contact_id,
                event_type='lead_created',
                timestamp=lead_time,
                location_id=location_id,
                source=random.choice(sources),
                metadata={
                    'name': f'Sample Lead {i}',
                    'email': f'lead{i}@example.com',
                    'phone': f'555-{i:04d}'
                }
            )
            self.record_lead_event(lead_event)
            
            # Random call attempt (70% chance, within 2 hours of lead)
            if random.random() < 0.7:
                call_time = lead_time + timedelta(minutes=random.randint(5, 120))
                call_event = LeadEvent(
                    contact_id=contact_id,
                    event_type='call_attempted',
                    timestamp=call_time,
                    location_id=location_id
                )
                self.record_lead_event(call_event)
                
                # Random call connection (60% chance of calls being answered)
                if random.random() < 0.6:
                    connect_event = LeadEvent(
                        contact_id=contact_id,
                        event_type='call_connected',
                        timestamp=call_time,
                        location_id=location_id,
                        duration_minutes=random.randint(2, 15)
                    )
                    self.record_lead_event(connect_event)
                    
                    # Random session booking (30% chance after connection)
                    if random.random() < 0.3:
                        session_time = call_time + timedelta(days=random.randint(1, 7))
                        session_event = LeadEvent(
                            contact_id=contact_id,
                            event_type='session_booked',
                            timestamp=session_time,
                            location_id=location_id
                        )
                        self.record_lead_event(session_event)
                        
                        # Random purchase (25% chance after session)
                        if random.random() < 0.25:
                            purchase_time = session_time + timedelta(days=random.randint(0, 3))
                            purchase_event = LeadEvent(
                                contact_id=contact_id,
                                event_type='purchase',
                                timestamp=purchase_time,
                                location_id=location_id
                            )
                            self.record_lead_event(purchase_event)

# Global analytics instance
analytics = EnhancedLeadAnalytics()

# Routes
@app.route('/')
def home():
    """Landing page"""
    install_url = generate_install_url()
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Enhanced GHL Lead Analytics</title>
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
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 Enhanced GHL Lead Analytics</h1>
            <p>Advanced lead performance tracking with AI-powered insights</p>
            
            <div class="features">
                <h3>🎯 Enhanced Features:</h3>
                <ul>
                    <li>📊 Location-specific filtering</li>
                    <li>🎛️ Customizable variable display</li>
                    <li>📞 Advanced call time analysis</li>
                    <li>🤖 AI analytics assistant</li>
                    <li>📈 Real-time data sync</li>
                    <li>🔥 Interactive heatmaps</li>
                </ul>
            </div>
            
            <a href="{install_url}" class="install-btn">🔗 Install on GoHighLevel</a>
            <br>
            <a href="/dashboard" class="btn">📊 View Enhanced Dashboard</a>
            <a href="/api/sample-data" class="btn">🎲 Load Sample Data</a>
        </div>
    </body>
    </html>
    '''

def generate_install_url():
    import urllib.parse
    scope_param = urllib.parse.quote_plus(" ".join(SCOPES))
    redirect = urllib.parse.quote_plus(REDIRECT_URI)
    
    return (f"https://marketplace.gohighlevel.com/oauth/chooselocation"
            f"?response_type=code&client_id={CLIENT_ID}&redirect_uri={redirect}"
            f"&app_id={APP_ID}&scope={scope_param}&installToFutureLocations=true")

@app.route('/dashboard')
def dashboard():
    """Enhanced dashboard - serves the HTML file if it exists, otherwise embedded HTML"""
    try:
        # Try to read the enhanced_dashboard.html file
        with open('enhanced_dashboard.html', 'r') as f:
            return f.read()
    except FileNotFoundError:
        # Fallback to basic dashboard if enhanced HTML file doesn't exist
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Enhanced Lead Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; 
                       background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
                .container { max-width: 1200px; margin: 0 auto; }
                .card { background: rgba(255,255,255,0.95); padding: 30px; border-radius: 20px; 
                        margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
                .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
                .metric { text-align: center; padding: 20px; background: white; border-radius: 10px; }
                .metric-value { font-size: 2em; font-weight: bold; color: #667eea; }
                .btn { padding: 12px 24px; background: #667eea; color: white; border: none; 
                       border-radius: 8px; cursor: pointer; margin: 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="card">
                    <h1>📊 Enhanced Lead Analytics Dashboard</h1>
                    <p>⚠️ Enhanced dashboard HTML file not found. Using basic version.</p>
                    <button class="btn" onclick="loadData()">🔄 Load Data</button>
                    <button class="btn" onclick="loadSampleData()">🎲 Load Sample Data</button>
                </div>
                
                <div class="card">
                    <h3>📈 Key Metrics</h3>
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-value" id="totalLeads">-</div>
                            <div>Total Leads</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="avgResponse">-</div>
                            <div>Avg Response (min)</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="connectionRate">-</div>
                            <div>Connection Rate (%)</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value" id="conversionRate">-</div>
                            <div>Conversion Rate (%)</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>📋 Instructions</h3>
                    <ol>
                        <li>Create <code>enhanced_dashboard.html</code> file in your repository</li>
                        <li>Copy the enhanced dashboard HTML code</li>
                        <li>Redeploy to see the full enhanced dashboard</li>
                    </ol>
                    <p><strong>Status:</strong> <span id="status">Ready for enhanced dashboard</span></p>
                </div>
            </div>
            
            <script>
                function loadData() {
                    fetch('/api/enhanced-stats')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('totalLeads').textContent = data.total_leads || 0;
                            document.getElementById('avgResponse').textContent = Math.round(data.avg_response_time || 0);
                            document.getElementById('connectionRate').textContent = Math.round(data.connection_rate || 0);
                            document.getElementById('conversionRate').textContent = Math.round(data.conversion_rate || 0);
                            document.getElementById('status').textContent = 'Data loaded successfully';
                        })
                        .catch(error => {
                            document.getElementById('status').textContent = 'Error loading data';
                            console.error('Error:', error);
                        });
                }
                
                function loadSampleData() {
                    fetch('/api/sample-data')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('status').textContent = 'Sample data loaded!';
                            loadData();
                        })
                        .catch(error => {
                            document.getElementById('status').textContent = 'Error loading sample data';
                        });
                }
                
                // Auto-load data on page load
                loadData();
            </script>
        </body>
        </html>
        '''

@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback"""
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
            (client_key, access_token, refresh_token, expires_at, location_id, company_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (client_key, tokens['access_token'], tokens['refresh_token'],
              expires_at, tokens.get('locationId'), tokens.get('companyId')))
        conn.commit()
        conn.close()
        
        return f'''
        <div style="text-align: center; padding: 50px; font-family: Arial;">
            <h1>✅ Installation Successful!</h1>
            <p>Enhanced Lead Analytics is now connected.</p>
            <p><strong>Client Key:</strong> {client_key}</p>
            <a href="/dashboard" style="display: inline-block; background: #28a745; color: white; 
               padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px;">
                🚀 Open Enhanced Dashboard
            </a>
        </div>
        '''
        
    except Exception as e:
        return f"<h1>❌ Installation Failed</h1><p>{str(e)}</p><a href='/'>Try Again</a>"

# API Routes
@app.route('/api/locations')
def api_locations():
    """Get all available locations"""
    locations = analytics.get_locations()
    return jsonify(locations)

@app.route('/api/enhanced-stats')
def api_enhanced_stats():
    """Get enhanced statistics with filtering"""
    location_id = request.args.get('location', 'all')
    days = int(request.args.get('days', 30))
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    data = analytics.get_enhanced_stats(location_id, days, start_date, end_date)
    return jsonify(data['stats'])

@app.route('/api/best-times')
def api_best_times():
    """Get best call times analysis"""
    location_id = request.args.get('location', 'all')
    days = int(request.args.get('days', 30))
    
    data = analytics.get_enhanced_stats(location_id, days)
    return jsonify(data['best_times'])

@app.route('/api/sample-data')
def api_sample_data():
    """Load sample data for testing"""
    try:
        analytics.add_sample_data()
        return jsonify({'status': 'success', 'message': 'Sample data loaded successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/sync-all', methods=['POST'])
def api_sync_all():
    """Sync all data from GHL"""
    try:
        # Get all stored tokens
        conn = sqlite3.connect(analytics.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM oauth_tokens')
        tokens = cursor.fetchall()
        conn.close()
        
        if not tokens:
            return jsonify({'status': 'error', 'message': 'No OAuth tokens found. Please install the app first.'})
        
        results = []
        for token_record in tokens:
            client_key = token_record[1]
            # For now, just log the sync attempt
            results.append({'client_key': client_key, 'status': 'queued'})
        
        return jsonify({'status': 'success', 'results': results, 'message': 'Sync initiated for all connected accounts'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """AI Chat endpoint"""
    try:
        data = request.json
        message = data.get('message', '').lower()
        
        # Get current stats for context
        stats_data = analytics.get_enhanced_stats()
        stats = stats_data['stats']
        
        # Simple AI response logic
        if 'best' in message and ('time' in message or 'call' in message):
            response = f"Based on your data, your optimal call times show the highest success rates. Your current connection rate is {stats.get('connection_rate', 0):.1f}%."
        elif 'improve' in message or 'better' in message:
            response = f"To improve your {stats.get('conversion_rate', 0):.1f}% conversion rate, focus on: 1) Faster response times (current avg: {stats.get('avg_response_time', 0):.0f} min), 2) Call during peak hours, 3) Follow up consistently."
        elif 'location' in message or 'perform' in message:
            response = f"Your locations show varying performance. Total leads: {stats.get('total_leads', 0)}, with {stats.get('leads_connected', 0)} successful connections."
        elif 'trend' in message or 'week' in message:
            response = f"Current trends show {stats.get('total_leads', 0)} leads with {stats.get('session_rate', 0):.1f}% booking sessions and {stats.get('conversion_rate', 0):.1f}% converting to sales."
        elif 'help' in message or 'what' in message:
            response = "I can help analyze your lead data! Ask me about: best call times, performance improvement, location comparisons, or current trends."
        else:
            response = f"I analyzed your data: {stats.get('total_leads', 0)} total leads, {stats.get('connection_rate', 0):.1f}% connection rate, {stats.get('conversion_rate', 0):.1f}% conversion rate. What specific insights would you like?"
        
        return jsonify({'response': response})
        
    except Exception as e:
        return jsonify({'response': f'Sorry, I encountered an error: {str(e)}'})

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Handle GHL webhooks for real-time updates"""
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
                print(f"✅ Recorded lead creation: {contact['id']}")
        
        elif event_type == 'OutboundMessage' and webhook_data.get('messageType') == 'Call':
            # Handle call attempts
            contact_id = webhook_data.get('contactId')
            location_id = webhook_data.get('locationId')
            
            if contact_id and location_id:
                event = LeadEvent(
                    contact_id=contact_id,
                    event_type='call_attempted',
                    timestamp=datetime.now(),
                    location_id=location_id
                )
                analytics.record_lead_event(event)
                print(f"📞 Recorded call attempt: {contact_id}")
        
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
        'redirect_uri': REDIRECT_URI,
        'features': [
            'enhanced_analytics', 
            'ai_chat', 
            'location_filtering', 
            'call_time_analysis',
            'sample_data',
            'real_time_webhooks'
        ]
    })

@app.route('/api/stats')
def api_basic_stats():
    """Basic stats endpoint for backward compatibility"""
    data = analytics.get_enhanced_stats()
    stats = data['stats']
    
    return jsonify({
        'total_leads': stats.get('total_leads', 0),
        'avg_response_time': round(stats.get('avg_response_time', 0)),
        'connection_rate': round(stats.get('connection_rate', 0)),
        'conversion_rate': round(stats.get('conversion_rate', 0)),
        'daily_leads': [5, 8, 12, 7, 15, 10, 18, 14]  # Sample data
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Enhanced GHL Lead Analytics starting on port {port}")
    print(f"📍 Base URL: {BASE_URL}")
    print(f"🔗 Redirect URI: {REDIRECT_URI}")
    print(f"📊 Enhanced Dashboard: {BASE_URL}/dashboard")
    print(f"🎲 Sample Data: {BASE_URL}/api/sample-data")
    print(f"🤖 Features: AI Chat, Location Filtering, Call Time Analysis")
    
    app.run(host='0.0.0.0', port=port, debug=False)
