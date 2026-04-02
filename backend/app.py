from flask import Flask, jsonify
import requests
import mysql.connector
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_CONNECTOR_URL = "http://api:5000/api/radar"
DB_CONFIG = {
    'host': 'db',
    'user': 'root',
    'password': 'password123',
    'database': 'sbb_data'
}

@app.route('/sync-trains', methods=['GET'])
def sync_trains():
    try:
        # 1. Daten von der API abrufen
        response = requests.get(API_CONNECTOR_URL)
        raw_json = response.json()
        data_list = raw_json.get('data', [])

        # 2. Verbindung zur Datenbank herstellen
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # SQL für die Live-Tabelle: Schreibt Daten rein oder aktualisiert sie, falls trip_id existiert
        live_query = """
            INSERT INTO active_trains (trip_id, origin, destination, delay, latitude, longitude, route_data)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                delay = VALUES(delay),
                latitude = VALUES(latitude),
                longitude = VALUES(longitude),
                origin = VALUES(origin),
                updated_at = CURRENT_TIMESTAMP
        """

        # SQL für das Archiv: Speichert Züge permanent, wenn die Verspätung hoch ist
        archive_query = """
            INSERT INTO delay_archive (trip_id, origin, destination, delay, route_data)
            VALUES (%s, %s, %s, %s, %s)
        """

        sync_count = 0
        archive_count = 0

        for item in data_list:
            # Die Station, an der wir gerade messen (unser "Origin")
            current_station = item.get('station', {}).get('name', 'Unbekannt')
            stationboard = item.get('stationboard', [])

            for train in stationboard:
                # Eindeutige ID zusammenbauen (z.B. S7)
                # Alt: trip_id = f"{train.get('category', '')}{train.get('number', '')}"
                # Neu: Wir nehmen den Namen UND die geplante Abfahrtszeit
                # Das ergibt dann IDs wie "S7_2026-04-02T14:30:00"
                planned_departure = train.get('stop', {}).get('departure', '0000')
                trip_id = f"{train.get('category', '')}{train.get('number', '')}_{planned_departure}"
                destination = train.get('to', 'Unbekannt')
                
                stop_info = train.get('stop', {})
                
                # SICHERHEITS-CHECK: Falls delay None/null ist, setzen wir 0
                raw_delay = stop_info.get('delay')
                delay = int(raw_delay) if raw_delay is not None else 0
                
                # Koordinaten auslesen
                coords = stop_info.get('station', {}).get('coordinate', {})
                lat = coords.get('x', 0.0)
                lon = coords.get('y', 0.0)

                # Die komplette PassList (für die Streckenzeichnung) in JSON umwandeln
                pass_list = train.get('passList', [])
                route_json = json.dumps(pass_list)

                # A) Live-Tabelle füttern (Immer ein UPSERT)
                cursor.execute(live_query, (
                    trip_id, 
                    current_station, 
                    destination, 
                    delay, 
                    lat, 
                    lon, 
                    route_json
                ))
                sync_count += 1

                # B) Archiv-Check: Nur wenn die Verspätung >= 20 Minuten ist
                if delay >= 20:
                    cursor.execute(archive_query, (
                        trip_id, 
                        current_station, 
                        destination, 
                        delay, 
                        route_json
                    ))
                    archive_count += 1

        # Alles abspeichern
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"Synchronisation beendet: {sync_count} Züge im Live-System aktualisiert. {archive_count} Härtefälle archiviert.",
            "timestamp": "2026-04-02" # Nur als Info für dich
        }), 200

    except Exception as e:
        # Falls doch noch was schiefgeht, sehen wir genau was
        return jsonify({
            "status": "error", 
            "error": str(e)
        }), 500

# Neue Route: Nur die Archiv-Züge anzeigen
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

# Neue Route: Alle aktuellen Züge (für die Map)
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)