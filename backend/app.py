from flask import Flask, jsonify
import requests
import mysql.connector
import json
import re
from flask_cors import CORS
from datetime import datetime
import pytz

app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    'host': 'db',
    'user': 'root',
    'password': 'password123',
    'database': 'sbb_data'
}
API_CONNECTOR_URL = "http://api:5000/api/radar"

def parse_sbb_date(date_str):
    """Hilfsfunktion: Macht SBB-Daten (+0200) kompatibel für Python (+02:00)"""
    if not date_str: return None
    # Fügt den Doppelpunkt in die Zeitzone ein, falls er fehlt (z.B. +0200 -> +02:00)
    date_str = re.sub(r'(\d{2})(\d{2})$', r'\1:\2', date_str.replace('Z', '+00:00'))
    return datetime.fromisoformat(date_str)

@app.route('/sync-trains', methods=['GET'])
def sync_trains():
    try:
        response = requests.get(API_CONNECTOR_URL)
        data_list = response.json().get('data', [])

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        live_query = """
            INSERT INTO active_trains (trip_id, origin, destination, delay, latitude, longitude, route_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                delay = VALUES(delay), latitude = VALUES(latitude), 
                longitude = VALUES(longitude), origin = VALUES(origin), updated_at = CURRENT_TIMESTAMP
        """

        swiss_tz = pytz.timezone('Europe/Zurich')
        now = datetime.now(swiss_tz)
        sync_count = 0

        for item in data_list:
            stationboard = item.get('stationboard', [])
            for train in stationboard:
                planned_dep = train.get('stop', {}).get('departure', '0000')
                trip_id = f"{train.get('category', '')}{train.get('number', '')}_{planned_dep}"
                
                pass_list = train.get('passList', [])
                
                # Startwerte setzen
                current_station = item.get('station', {}).get('name', 'Unbekannt')
                coords = train.get('stop', {}).get('station', {}).get('coordinate', {})
                lat, lon = coords.get('x', 0.0), coords.get('y', 0.0)

                # --- VERBESSERTE INTERPOLATION ---
                for i in range(len(pass_list) - 1):
                    stop_a = pass_list[i]
                    stop_b = pass_list[i+1]
                    
                    time_a = parse_sbb_date(stop_a.get('departure') or stop_a.get('arrival'))
                    time_b = parse_sbb_date(stop_b.get('arrival'))
                    
                    if time_a and time_b:
                        if time_a <= now <= time_b:
                            # Wir sind zwischen zwei Bahnhöfen!
                            diff = (time_b - time_a).total_seconds()
                            elapsed = (now - time_a).total_seconds()
                            progress = elapsed / diff if diff > 0 else 0
                            
                            c_a = stop_a.get('station', {}).get('coordinate', {})
                            c_b = stop_b.get('station', {}).get('coordinate', {})
                            
                            lat = c_a.get('x', 0.0) + (c_b.get('x', 0.0) - c_a.get('x', 0.0)) * progress
                            lon = c_a.get('y', 0.0) + (c_b.get('y', 0.0) - c_a.get('y', 0.0)) * progress
                            current_station = f"Zwischen {stop_a['station']['name']} und {stop_b['station']['name']}"
                            break
                        elif now > time_b:
                            # Zug ist schon an Station B vorbei
                            current_station = stop_b['station']['name']
                            lat = stop_b['station']['coordinate']['x']
                            lon = stop_b['station']['coordinate']['y']

                raw_delay = train.get('stop', {}).get('delay')
                delay = int(raw_delay) if raw_delay is not None else 0
                
                cursor.execute(live_query, (trip_id, current_station, train.get('to', 'Unbekannt'), delay, lat, lon, json.dumps(pass_list)))
                sync_count += 1

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": f"{sync_count} Züge live."}), 200
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/view-live', methods=['GET'])
def view_live():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM active_trains")
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/view-archive', methods=['GET'])
def view_archive():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM delay_archive ORDER BY delay DESC")
        data = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)