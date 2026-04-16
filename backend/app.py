from flask import Flask, jsonify
import requests
import mysql.connector
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    'host': 'db', # Oder 'localhost', falls nicht in Docker
    'user': 'root',
    'password': 'password123',
    'database': 'sbb_data'
}
API_CONNECTOR_URL = "http://api:5000/api/radar"

@app.route('/sync-trains', methods=['GET'])
def sync_trains():
    conn = None
    try:
        # 1. Daten vom API-Connector (Port 5000) abrufen
        response = requests.get(API_CONNECTOR_URL, timeout=15)
        response.raise_for_status()
        raw_data = response.json().get('data', [])
        
        if not raw_data:
            return jsonify({"status": "error", "message": "Keine Daten von API erhalten"}), 500

        # 2. DB-Verbindung aufbauen
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 3. Operational Reset: Live-Tabelle leeren
        # Damit entfernen wir Züge, die nicht mehr aktuell im Netz sind.
        cursor.execute("TRUNCATE TABLE active_trains")

        # SQL-Statements vorbereiten
        live_query = """
            INSERT INTO active_trains (trip_id, origin, destination, delay, latitude, longitude, route_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                delay = VALUES(delay),
                updated_at = CURRENT_TIMESTAMP
        """
        
        archive_query = """
            INSERT INTO delay_archive (trip_id, origin, destination, delay, route_data)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                delay = VALUES(delay),
                recorded_at = CURRENT_TIMESTAMP
        """

        sync_count = 0
        for item in raw_data:
            # Der Hub, an dem die Daten abgegriffen wurden (z.B. Zürich HB)
            hub_name = item.get('station', {}).get('name', 'Unbekannt')
            
            for train in item.get('stationboard', []):
                # Eindeutige ID: Name des Zuges + Endstation (stabil über mehrere Hubs)
                train_id_name = f"{train.get('category', '')}{train.get('number', '')}"
                dest_name = train.get('to', 'Unbekannt')
                trip_id = f"{train_id_name}_{dest_name}"
                
                # Verspätung und PassList extrahieren
                raw_delay = train.get('stop', {}).get('delay')
                delay = int(raw_delay) if raw_delay is not None else 0
                pass_list_json = json.dumps(train.get('passList', []))

                # --- LOGIK A: ARCHIVIERUNG (Unabhängig von Koordinaten) ---
                # Wenn der Zug die 20-Minuten-Marke knackt, wird er archiviert oder geupdated
                if delay >= 20:
                    cursor.execute(archive_query, (
                        trip_id, 
                        hub_name, 
                        dest_name, 
                        delay, 
                        pass_list_json
                    ))

                # --- LOGIK B: LIVE-RADAR (Benötigt Koordinaten für die Karte) ---
                coords = train.get('stop', {}).get('station', {}).get('coordinate', {})
                lat, lon = coords.get('x'), coords.get('y')
                
                if lat and lon:
                    cursor.execute(live_query, (
                        trip_id, 
                        hub_name, 
                        dest_name, 
                        delay, 
                        lat, 
                        lon, 
                        pass_list_json
                    ))
                    sync_count += 1

        # 4. Transaktion abschliessen
        conn.commit()
        cursor.close()
        
        return jsonify({
            "status": "success", 
            "message": f"Sync abgeschlossen. {sync_count} Züge live. Archiv-Check durchgeführt."
        }), 200

    except Exception as e:
        if conn:
            conn.rollback() # Bei Fehlern alles zurücksetzen
        print(f"CRITICAL SYNC ERROR: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/view-live', methods=['GET'])
def view_live():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT trip_id, origin, destination, delay, CAST(latitude AS CHAR) as latitude, CAST(longitude AS CHAR) as longitude FROM active_trains")
        data = cursor.fetchall()
        
        # Sicherstellen, dass Koordinaten Zahlen sind für das Frontend
        for row in data:
            row['latitude'] = float(row['latitude']) if row['latitude'] else 0
            row['longitude'] = float(row['longitude']) if row['longitude'] else 0
            
        cursor.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)