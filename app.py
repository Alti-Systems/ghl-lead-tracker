# app.py - Real-Time GHL Lead Analytics System - Fixed Indentation
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
        
        # Enhanced contact tracking with accurate time calculations
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
        
        # Real locations from GHL
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ghl_locations (
                location_id TEXT PRIMARY KEY,
                location_name TEXT NOT NULL,
                address TEXT,
                phone TEXT,
                email TEXT,
                timezone TEXT,
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
        
        # OAuth tokens with refresh capability
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
        
        # Webhook events log for debugging
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
    
    def sync_real_locations(self, access_token, company_id=None):
        """Sync actual GHL locations"""
        print("Syncing real GHL locations...")
        
        headers = {"Authorization": f"Bearer {access_token}", "Version": "2021-04-15"}
        
        try:
            if company_id:
                resp = requests.get(
                    f"https://services.leadconnectorhq.com/oauth/installedLocations",
                    headers=headers,
                    params={"companyId": company_id, "appId": APP_ID, "isInstalled": True}
                )
            else:
                resp = requests.get("https://api.gohighlevel.com/v2/locations", headers=headers)
            
            if resp.status_code == 200:
                data = resp.json()
                locations = data.get('locations', []) if isinstance(data, dict) else data
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                for loc in locations:
                    location_id = loc.get('_id') or loc.get('id') or loc.get('locationId')
                    location_name = loc.get('name', 'Unknown Location')
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO ghl_locations 
                        (location_id, location_name, address, phone, email, timezone, last_synced)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        location_id, location_name, loc.get('address', ''),
                        loc.get('phone', ''), loc.get('email', ''), loc.get('timezone', ''),
                        datetime.now()
                    ))
                
                conn.commit()
                conn.close()
                print(f"Synced {len(locations)} real locations from GHL")
                return len(locations)
            else:
                print(f"Failed to sync locations: {resp.status_code} - {resp.text}")
                return 0
                
        except Exception as e:
            print(f"Error syncing locations: {e}")
            return 0
    
    def record_contact_created(self, contact_data, location_id):
        """Record when a contact is created"""
        contact_id = contact_data.get('id')
        if not contact_id:
            return False
        
        created_at_str = contact_data.get('dateAdded')
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')).replace(tzinfo=None)
            except:
                created_at = datetime.now()
        else:
            created_at = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT location_name FROM ghl_locations WHERE location_id = ?', (location_id,))
        location_result = cursor.fetchone()
        location_name = location_result[0] if location_result else 'Unknown Location'
        
        cursor.execute('''
            INSERT OR REPLACE INTO contact_journey 
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
        conn.close()
        
        print(f"Recorded contact creation: {contact_id} at {location_name}")
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
            print(f"Recorded call attempt for {contact_id}")
        
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
            print(f"Recorded call connection for {contact_id}")
        
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
        """Get actual GHL locations"""
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
        """Get enhanced statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        where_clause = f"WHERE created_at >= date('now', '-{days} days')"
        params = []
        
        if location_id and location_id != 'all':
            where_clause += " AND location_id = ?"
            params.append(location_id)
        
        query = f'''
            SELECT 
                COUNT(*) as total_leads,
                AVG(minutes_to_first_call) as avg_minutes_to_first_call,
                AVG(minutes_to_first_connection) as avg_minutes_to_first_connection,
                AVG(minutes_to_first_session) as avg_minutes_to_first_session,
                AVG(minutes_to_purchase) as avg_minutes_to_purchase,
                COUNT(CASE WHEN first_call_attempted_at IS NOT NULL THEN 1 END) as leads_called,
                COUNT(CASE WHEN first_call_connected_at IS NOT NULL THEN 1 END) as leads_connected,
                COUNT(CASE WHEN first_session_booked_at IS NOT NULL THEN 1 END) as leads_to_session,
                COUNT(CASE WHEN first_purchase_at IS NOT NULL THEN 1 END) as leads_to_purchase,
                COUNT(CASE WHEN current_status = 'new_lead' THEN 1 END) as new_leads,
                COUNT(CASE WHEN current_status = 'contacted' THEN 1 END) as contacted_leads,
                COUNT(CASE WHEN current_status = 'connected' THEN 1 END) as connected_leads,
                COUNT(CASE WHEN current_status = 'session_booked' THEN 1 END) as session_booked_leads,
                COUNT(CASE WHEN current_status = 'purchased' THEN 1 END) as purchased_leads,
                ROUND(COUNT(CASE WHEN first_call_connected_at IS NOT NULL THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(CASE WHEN first_call_attempted_at IS NOT NULL THEN 1 END), 0), 1) as connection_rate,
                ROUND(COUNT(CASE WHEN first_session_booked_at IS NOT NULL THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0), 1) as session_rate,
                ROUND(COUNT(CASE WHEN first_purchase_at IS NOT NULL THEN 1 END) * 100.0 / 
                    NULLIF(COUNT(*), 0), 1) as conversion_rate
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
                    'conversion_rate': result[16] or 0
                }
            else:
                stats = self.get_empty_stats()
                
        except Exception as e:
            print(f"Database query error: {e}")
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
            'connection_rate': 0, 'session_rate': 0, 'conversion_rate': 0
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
            print(f"Error getting best call times: {e}")
            best_times = []
        
        conn.close()
        return best_times
    
    def log_webhook_event(self, event_type, contact_id, location_id, raw_data, error_message=None):
        """Log webhook events for debugging"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO webhook_events 
            (event_type, contact_id, location_id, raw_data, error_message)
            VALUES (?, ?, ?, ?, ?)
        ''', (event_type, contact_id, location_id, json.dumps(raw_data), error_message))
        
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
            .status {{ background: #e3f2fd; padding: 15px; border-radius: 10px; margin: 20px 0; color: #0277bd; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Real-Time GHL Lead Analytics</h1>
            <p>Advanced lead performance tracking with precise time calculations</p>
            
            <div class="status">
                <strong>Enhanced Features:</strong><br>
                Real-time webhook processing<br>
                Accurate time interval calculations<br>
                Custom field tracking for session status<br>
                Call performance analytics<br>
                Task and tag management
            </div>
            
            <div class="features">
                <h3>What You'll Track:</h3>
                <ul>
                    <li><strong>Contact Created</strong> to First Call: Minutes/Hours</li>
                    <li><strong>Contact Created</strong> to First Connection: Minutes/Hours</li>
                    <li><strong>Contact Created</strong> to First Session: Hours</li>
                    <li><strong>Contact Created</strong> to Purchase: Days</li>
                    <li><strong>Custom Fields:</strong> Session status, no-shows, cancellations</li>
                    <li><strong>Tags & Tasks:</strong> Lead quality and follow-up tracking</li>
                    <li>Best performing call times by actual data</li>
                </ul>
            </div>
            
            <a href="{install_url}" class="install-btn">Install on GoHighLevel</a>
            <br>
            <a href="/dashboard" class="btn">View Real-Time Dashboard</a>
            <a href="/api/sync-locations" class="btn">Sync Locations</a>
        </div>
    </body>
    </html>
    '''

@app.route('/dashboard')
def dashboard():
    """Enhanced real-time dashboard"""
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
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px; margin-bottom: 30px;
        }
        .metric-card {
            background: rgba(255, 255, 255, 0.95); padding: 25px; border-radius: 15px;
            text-align: center; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }
        .metric-card:hover { transform: translateY(-5px); }
        .metric-value {
            font-size: 2.5em; font-weight: bold; margin-bottom: 8px;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .metric-label { color: #666; font-size: 1em; font-weight: 500; }
        .metric-sublabel { color: #999; font-size: 0.85em; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Real-Time Lead Performance Dashboard</h1>
            <p>Advanced tracking with precise time calculations</p>
        </div>

        <div class="status-bar">
            <div>
                <span class="status-indicator status-connected" id="dataStatus"></span>
                <span id="dataStatusText">Connected - Last sync: <span id="lastSync">Never</span></span>
            </div>
            <div>
                <button onclick="syncLocations()">Sync Locations</button>
                <button onclick="syncAllData()">Refresh Data</button>
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
            <button onclick="updateDashboard()">Update Dashboard</button>
        </div>

        <div class="metrics-grid" id="metricsGrid">
            <!-- Populated by JavaScript -->
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
                    option.textContent = location.name + (location.address ? ' - ' + location.address : '');
                    select.appendChild(option);
                });
                
                console.log('Loaded ' + locations.length + ' real locations');
            } catch (error) {
                console.error('Error loading locations:', error);
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
                updateDataStatus('connected', 'Last sync: ' + new Date().toLocaleTimeString());
                
            } catch (error) {
                console.error('Error loading dashboard:', error);
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

            const metrics = [
                { 
                    label: 'Total Leads', 
                    value: dashboardData.total_leads || 0,
                    sublabel: 'This period'
                },
                { 
                    label: 'Avg Time to First Call', 
                    value: (dashboardData.avg_minutes_to_first_call || 0) + 'm',
                    sublabel: (dashboardData.avg_hours_to_first_call || 0) + 'h total'
                },
                { 
                    label: 'Avg Time to Connection', 
                    value: Math.round(dashboardData.avg_minutes_to_first_connection || 0) + 'm',
                    sublabel: (dashboardData.avg_hours_to_first_connection || 0) + 'h total'
                },
                { 
                    label: 'Connection Rate', 
                    value: (dashboardData.connection_rate || 0) + '%',
                    sublabel: (dashboardData.leads_connected || 0) + ' of ' + (dashboardData.leads_called || 0) + ' calls'
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

        function updateDashboard() {
            currentFilters.location = document.getElementById('locationFilter').value;
            currentFilters.dateRange = document.getElementById('dateRange').value;
            loadDashboard();
        }

        async function syncLocations() {
            updateDataStatus('syncing', 'Syncing real GHL locations...');
            try {
                const response = await fetch('/api/sync-locations');
                const result = await response.json();
                
                if (result.status === 'success') {
                    updateDataStatus('connected', 'Synced ' + result.count + ' locations');
                    loadLocations();
                } else {
                    updateDataStatus('error', 'Location sync failed');
                }
            } catch (error) {
                updateDataStatus('error', 'Location sync failed');
            }
        }

        async function syncAllData() {
            updateDataStatus('syncing', 'Syncing all data...');
            try {
                const response = await fetch('/api/sync-all', { method: 'POST' });
                const result = await response.json();
                
                updateDataStatus('connected', 'Data sync completed');
                loadDashboard();
            } catch (error) {
                updateDataStatus('error', 'Data sync failed');
            }
        }

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
    """Handle OAuth callback"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f"<h1>Installation Error</h1><p>{error}</p><a href='/'>Try Again</a>"
    
    if not code:
        return "<h1>No authorization code received</h1><a href='/'>Try Again</a>"
    
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
        
        locations_synced = analytics.sync_real_locations(tokens['access_token'], tokens.get('companyId'))
        
        return f'''
        <div style="text-align: center; padding: 50px; font-family: Arial;">
            <h1>Installation Successful!</h1>
            <p>Real-Time Lead Analytics is now connected and ready.</p>
            <p><strong>Client Key:</strong> {client_key}</p>
            <p><strong>Locations Synced:</strong> {locations_synced}</p>
            <div style="background: #e8f5e8; padding: 15px; border-radius: 10px; margin: 20px 0;">
                <strong>Next Steps:</strong><br>
                1. Create a test contact in GHL to verify webhook tracking<br>
                2. Make test calls to build call performance data<br>
                3. View real-time results in your dashboard
            </div>
            <a href="/dashboard" style="display: inline-block; background: #28a745; color: white; 
               padding: 15px 30px; text-decoration: none; border-radius: 5px; margin: 20px;">
                Open Real-Time Dashboard
            </a>
        </div>
        '''
        
    except Exception as e:
        return f"<h1>Installation Failed</h1><p>{str(e)}</p><a href='/'>Try Again</a>"

# API Routes
@app.route('/api/locations')
def api_locations():
    """Get real GHL locations"""
    locations = analytics.get_real_locations()
    return jsonify(locations)

@app.route('/api/sync-locations')
def api_sync_locations():
    """Manually sync locations from GHL"""
    token_data = get_valid_token()
    if not token_data:
        return jsonify({'status': 'error', 'message': 'No valid token found'})
    
    count = analytics.sync_real_locations(token_data['access_token'], token_data.get('company_id'))
    return jsonify({'status': 'success', 'count': count, 'message': f'Synced {count} locations'})

@app.route('/api/realtime-stats')
def api_realtime_stats():
    """Get real-time statistics"""
    location_id = request.args.get('location', 'all')
    days = int(request.args.get('days', 30))
    
    data = analytics.get_enhanced_stats(location_id, days)
    
    response = data['stats'].copy()
    response['best_times'] = data['best_times']
    
    return jsonify(response)

@app.route('/webhook', methods=['POST'])
def webhook_handler():
    """Enhanced webhook handler"""
    try:
        webhook_data = request.json
        event_type = webhook_data.get('type')
        contact_id = webhook_data.get('contactId') or webhook_data.get('contact', {}).get('id')
        location_id = webhook_data.get('locationId')
        
        print(f"Webhook received: {event_type} for contact {contact_id} at location {location_id}")
        
        analytics.log_webhook_event(event_type, contact_id, location_id, webhook_data)
        
        if event_type == 'ContactCreate':
            contact = webhook_data.get('contact', {})
            if contact.get('id') and location_id:
                success = analytics.record_contact_created(contact, location_id)
                if success:
                    print(f"Contact creation recorded: {contact.get('id')}")
                return jsonify({'status': 'success', 'message': 'Contact created and tracked'})
        
        elif event_type == 'OutboundMessage':
            message_type = webhook_data.get('messageType', '').lower()
            if 'call' in message_type and contact_id and location_id:
                analytics.record_call_attempt(contact_id, location_id)
                print(f"Call attempt recorded for {contact_id}")
                return jsonify({'status': 'success', 'message': 'Call attempt tracked'})
        
        elif event_type == 'InboundMessage':
            message_type = webhook_data.get('messageType', '').lower()
            if 'call' in message_type and contact_id and location_id:
                duration = webhook_data.get('duration', 0)
                if duration > 0:
                    analytics.record_call_connected(contact_id, location_id, duration_minutes=duration//60)
                    print(f"Call connection recorded for {contact_id} ({duration}s)")
                return jsonify({'status': 'success', 'message': 'Call connection tracked'})
        
        return jsonify({'status': 'success', 'message': f'Webhook {event_type} received'})
        
    except Exception as e:
        error_msg = str(e)
        print(f"Webhook error: {error_msg}")
        
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
    """Debug endpoint"""
    conn = sqlite3.connect(analytics.db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT event_type, contact_id, location_id, processed, error_message, received_at
        FROM webhook_events 
        ORDER BY received_at DESC 
        LIMIT 20
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

@app.route('/api/sync-all', methods=['POST'])
def api_sync_all():
    """Sync all data"""
    try:
        token_data = get_valid_token()
        if not token_data:
            return jsonify({'status': 'error', 'message': 'No valid token found'})
        
        locations_count = analytics.sync_real_locations(token_data['access_token'], token_data.get('company_id'))
        
        return jsonify({
            'status': 'success', 
            'message': f'Synced {locations_count} locations',
            'locations_synced': locations_count
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/health')
def health_check():
    """Health check"""
    conn = sqlite3.connect(analytics.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM contact_journey')
    total_contacts = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM ghl_locations WHERE is_active = TRUE')
    total_locations = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM webhook_events WHERE received_at >= date("now", "-1 day")')
    recent_webhooks = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'base_url': BASE_URL,
        'redirect_uri': REDIRECT_URI,
        'database_health': {
            'total_contacts': total_contacts,
            'total_locations': total_locations,
            'recent_webhooks_24h': recent_webhooks
        },
        'scopes_configured': SCOPES,
        'features': [
            'realtime_webhook_processing',
            'accurate_time_calculations', 
            'real_ghl_location_sync',
            'call_performance_tracking'
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Real-Time GHL Lead Analytics starting on port {port}")
    print(f"Base URL: {BASE_URL}")
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Dashboard: {BASE_URL}/dashboard")
    print(f"Scopes: {', '.join(SCOPES)}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
