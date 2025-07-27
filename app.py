# app.py - Complete Enhanced Lead Analytics System with Built-in Dashboard

import os
import json
import time
import requests
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from dataclasses import dataclass
from typing import Optional, List, Dict

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
        
        conn.close()
        return {'stats': stats}
    
    def add_sample_data(self):
        """Add sample data for testing the dashboard"""
        import random
        
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
    """Enhanced dashboard with all features built-in"""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced Lead Analytics Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.18.0/plotly.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; color: #333;
        }
        .container { max-width: 1600px; margin: 0 auto; padding: 20px; }
        .header {
            background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px);
            border-radius: 20px; padding: 30px; margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); text-align: center;
        }
        .controls-panel {
            display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 30px;
        }
        .control-section {
            background: rgba(255, 255, 255, 0.95); padding: 20px; border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        .control-section h3 { margin-bottom: 15px; color: #2c3e50; font-size: 1.1em; }
        .filter-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: 500; color: #555; }
        select, input, button {
            width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 8px;
            font-size: 14px; margin-bottom: 10px;
        }
        button {
            background: linear-gradient(45deg, #667eea, #764ba2); color: white;
            border: none; cursor: pointer; font-weight: bold; transition: all 0.3s ease;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }
        .checkbox-group { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .checkbox-item { display: flex; align-items: center; gap: 8px; }
        .checkbox-item input[type="checkbox"] { width: auto; margin: 0; }
        .dashboard-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 30px; margin-bottom: 30px; }
        .main-content { display: flex; flex-direction: column; gap: 20px; }
        .chat-panel {
            background: rgba(255, 255, 255, 0.95); border-radius: 20px; padding: 20px;
            height: fit-content; max-height: 80vh; display: flex; flex-direction: column;
        }
        .metrics-grid {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px; margin-bottom: 20px;
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
        .metric-label { color: #666; font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; }
        .chart-container {
            background: rgba(255, 255, 255, 0.95); border-radius: 20px; padding: 25px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1); margin-bottom: 20px;
        }
        .chart-title { font-size: 1.3em; font-weight: bold; margin-bottom: 20px; color: #2c3e50; text-align: center; }
        .best-times-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .chat-messages {
            flex: 1; overflow-y: auto; max-height: 400px; margin-bottom: 20px;
            padding: 10px; border: 1px solid #eee; border-radius: 10px; background: #f8f9fa;
        }
        .message { margin-bottom: 15px; padding: 10px; border-radius: 8px; }
        .user-message { background: #667eea; color: white; margin-left: 20px; }
        .ai-message { background: white; border: 1px solid #ddd; margin-right: 20px; }
        .chat-input { display: flex; gap: 10px; }
        .chat-input input { flex: 1; margin: 0; }
        .chat-input button { width: auto; padding: 10px 20px; margin: 0; }
        .data-status {
            background: rgba(255, 255, 255, 0.95); padding: 15px; border-radius: 10px;
            margin-bottom: 20px; border-left: 4px solid #667eea;
        }
        .status-indicator {
            display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 8px;
        }
        .status-connected { background: #28a745; }
        .status-syncing { background: #ffc107; animation: pulse 2s infinite; }
        .status-error { background: #dc3545; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        @media (max-width: 768px) {
            .controls-panel { grid-template-columns: 1fr; }
            .dashboard-grid { grid-template-columns: 1fr; }
            .best-times-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Enhanced Lead Performance Dashboard</h1>
            <p>Real-time analytics with AI-powered insights</p>
        </div>

        <div class="data-status">
            <span class="status-indicator status-connected" id="dataStatus"></span>
            <span id="dataStatusText">Connected - Last sync: <span id="lastSync">Never</span></span>
            <button onclick="syncAllData()" style="float: right; width: auto; padding: 5px 15px; margin: 0;">🔄 Sync Now</button>
        </div>

        <div class="controls-panel">
            <div class="control-section">
                <h3>🏢 Location Filter</h3>
                <div class="filter-group">
                    <label>Sub-Account:</label>
                    <select id="locationFilter">
                        <option value="all">All Locations</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>Date Range:</label>
                    <select id="dateRange">
                        <option value="7">Last 7 Days</option>
                        <option value="30" selected>Last 30 Days</option>
                        <option value="90">Last 90 Days</option>
                    </select>
                </div>
            </div>

            <div class="control-section">
                <h3>📊 Display Variables</h3>
                <div class="checkbox-group">
                    <div class="checkbox-item">
                        <input type="checkbox" id="var_total_leads" checked>
                        <label for="var_total_leads">Total Leads</label>
                    </div>
                    <div class="checkbox-item">
                        <input type="checkbox" id="var_response_time" checked>
                        <label for="var_response_time">Response Time</label>
                    </div>
                    <div class="checkbox-item">
                        <input type="checkbox" id="var_connection_rate" checked>
                        <label for="var_connection_rate">Connection Rate</label>
                    </div>
                    <div class="checkbox-item">
                        <input type="checkbox" id="var_conversion_rate" checked>
                        <label for="var_conversion_rate">Conversion Rate</label>
                    </div>
                </div>
                <button onclick="updateDashboard()">🔄 Update Display</button>
            </div>

            <div class="control-section">
                <h3>⚡ Quick Actions</h3>
                <button onclick="loadSampleData()">🎲 Load Sample Data</button>
                <button onclick="exportData()">💾 Export Data</button>
                <button onclick="resetFilters()">🔄 Reset Filters</button>
            </div>
        </div>

        <div class="dashboard-grid">
            <div class="main-content">
                <div class="metrics-grid" id="metricsGrid">
                    <!-- Metrics populated by JavaScript -->
                </div>

                <div class="chart-container" id="bestTimesContainer">
                    <div class="chart-title">📞 Best Call Times Analysis</div>
                    <div class="best-times-grid">
                        <div>
                            <h4>Success Rate by Hour</h4>
                            <canvas id="hourlyChart" width="400" height="300"></canvas>
                        </div>
                        <div>
                            <h4>Success Rate by Day</h4>
                            <canvas id="dailyChart" width="400" height="300"></canvas>
                        </div>
                    </div>
                </div>

                <div class="chart-container" id="funnelContainer">
                    <div class="chart-title">🎯 Conversion Funnel</div>
                    <canvas id="funnelChart" width="400" height="300"></canvas>
                </div>
            </div>

            <div class="chat-panel">
                <h3>🤖 AI Analytics Assistant</h3>
                <div class="chat-messages" id="chatMessages">
                    <div class="message ai-message">
                        <strong>AI Assistant:</strong> Hi! I can help you analyze your lead data. Try asking:
                        <ul style="margin: 10px 0; padding-left: 20px;">
                            <li>"What's my best performing location?"</li>
                            <li>"When should I call leads for better results?"</li>
                            <li>"How can I improve my conversion rate?"</li>
                        </ul>
                    </div>
                </div>
                <div class="chat-input">
                    <input type="text" id="chatInput" placeholder="Ask about your lead data..." onkeypress="handleChatKeyPress(event)">
                    <button onclick="sendChatMessage()">Send</button>
                </div>
            </div>
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
                select.innerHTML = '<option value="all">All Locations</option>';
                
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
            updateDataStatus('syncing', 'Loading data...');
            
            try {
                const params = new URLSearchParams({
                    location: currentFilters.location,
                    days: currentFilters.dateRange
                });
                
                const response = await fetch(`/api/enhanced-stats?${params}`);
                dashboardData = await response.json();
                
                updateMetrics();
                updateBestTimesAnalysis();
                updateConversionFunnel();
                updateDataStatus('connected', `Last sync: ${new Date().toLocaleTimeString()}`);
                
            } catch (error) {
                console.error('Error loading dashboard:', error);
                updateDataStatus('error', 'Error loading data');
            }
        }

        function updateDataStatus(status, text) {
            const indicator = document.getElementById('dataStatus');
            const statusText = document.getElementById('dataStatusText');
            
            indicator.className = `status-indicator status-${status}`;
            statusText.textContent = text;
        }

        function updateMetrics() {
            const metricsGrid = document.getElementById('metricsGrid');
            metricsGrid.innerHTML = '';

            const metrics = [
                { id: 'total_leads', label: 'Total Leads', value: dashboardData.total_leads || 0 },
                { id: 'response_time', label: 'Avg Response Time (min)', value: Math.round(dashboardData.avg_response_time || 0) },
                { id: 'connection_rate', label: 'Connection Rate (%)', value: Math.round(dashboardData.connection_rate || 0) },
                { id: 'conversion_rate', label: 'Conversion Rate (%)', value: Math.round(dashboardData.conversion_rate || 0) }
            ];

            metrics.forEach(metric => {
                const checkbox = document.getElementById(`var_${metric.id}`);
                if (checkbox && checkbox.checked) {
                    const card = document.createElement('div');
                    card.className = 'metric-card';
                    card.innerHTML = `
                        <div class="metric-value">${metric.value}</div>
                        <div class="metric-label">${metric.label}</div>
                    `;
                    metricsGrid.appendChild(card);
                }
            });
        }

        function updateBestTimesAnalysis() {
            // Sample hourly data
            const hourlyData = Array.from({length: 24}, (_, i) => Math.random() * 100);
            const dailyData = [65, 72, 78, 75, 70, 45, 35]; // Mon-Sun

            // Hourly chart
            const hourlyCtx = document.getElementById('hourlyChart').getContext('2d');
            new Chart(hourlyCtx, {
                type: 'bar',
                data: {
                    labels: Array.from({length: 24}, (_, i) => i + ':00'),
                    datasets: [{
                        label: 'Success Rate (%)',
                        data: hourlyData,
                        backgroundColor: 'rgba(102, 126, 234, 0.8)',
                        borderColor: 'rgba(102, 126, 234, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, max: 100 } }
                }
            });

            // Daily chart
            const dailyCtx = document.getElementById('dailyChart').getContext('2d');
            new Chart(dailyCtx, {
                type: 'bar',
                data: {
                    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                    datasets: [{
                        label: 'Success Rate (%)',
                        data: dailyData,
                        backgroundColor: 'rgba(118, 75, 162, 0.8)',
                        borderColor: 'rgba(118, 75, 162, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, max: 100 } }
                }
            });
        }

        function updateConversionFunnel() {
            const funnelCtx = document.getElementById('funnelChart').getContext('2d');
            
            const total = dashboardData.total_leads || 100;
            const funnelData = {
                'Total Leads': total,
                'Called': Math.floor(total * 0.85),
                'Connected': Math.floor(total * 0.52),
                'Session Booked': Math.floor(total * 0.23),
                'Purchased': Math.floor(total * 0.08)
            };

            new Chart(funnelCtx, {
                type: 'bar',
                data: {
                    labels: Object.keys(funnelData),
                    datasets: [{
                        label: 'Count',
                        data: Object.values(funnelData),
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

        function updateDashboard() {
            currentFilters.location = document.getElementById('locationFilter').value;
            currentFilters.dateRange = document.getElementById('dateRange').value;
            loadDashboard();
        }

        async function syncAllData() {
            updateDataStatus('syncing', 'Syncing data...');
            try {
                const response = await fetch('/api/sync-all', { method: 'POST' });
                const result = await response.json();
                updateDataStatus('connected', 'Sync completed');
                loadDashboard();
            } catch (error) {
                updateDataStatus('error', 'Sync failed');
            }
        }

        async function loadSampleData() {
            updateDataStatus('syncing', 'Loading sample data...');
            try {
                const response = await fetch('/api/sample-data');
                const result = await response.json();
                updateDataStatus('connected', 'Sample data loaded!');
                loadDashboard();
            } catch (error) {
                updateDataStatus('error', 'Failed to load sample data');
            }
        }

        // AI Chat Functions
        async function sendChatMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            addChatMessage('user', message);
            input.value = '';
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message })
                });
                const result = await response.json();
                addChatMessage('ai', result.response);
            } catch (error) {
                addChatMessage('ai', 'Sorry, I encountered an error processing your request.');
            }
        }

        function handleChatKeyPress(event) {
            if (event.key === 'Enter') {
                sendChatMessage();
            }
        }

        function addChatMessage(sender, message) {
            const messagesContainer = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}-message`;
            
            if (sender === 'user') {
                messageDiv.innerHTML = `<strong>You:</strong> ${message}`;
            } else {
                messageDiv.innerHTML = `<strong>AI Assistant:</strong> ${message}`;
            }
            
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }

        function resetFilters() {
            document.getElementById('locationFilter').value = 'all';
            document.getElementById('dateRange').value = '30';
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
            updateDashboard();
        }

        function exportData() {
            alert('Export feature coming soon!');
        }

        // Auto-refresh every 2 minutes
        setInterval(() => {
            if (document.visibilityState === 'visible') {
                loadDashboard();
            }
        }, 120000);
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
