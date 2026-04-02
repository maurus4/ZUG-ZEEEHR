from flask import Flask, jsonify
import requests
import mysql.connector
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Interne Docker-Netzwerk-Adressen
API_CONNECTOR_URL = "http://api:5000/api/radar"

DB_CONFIG = {
    'host': 'db',          # Der Name des Datenbank-Containers
    'user': 'root',
    'password': 'password123',
    'database': 'sbb_data'
}

@app.route('/sync-trains', methods=['GET'])
def sync_trains():
    try:
        response = requests.get(API_CONNECTOR_URL)
        raw_json = response.json()

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # SQL-Query mit dem neuen Feld 'origin'
        insert_query = """
            INSERT INTO radar_logs (trip_id, latitude, longitude, delay, origin, destination)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        inserted_count = 0
        data_list = raw_json.get('data', [])

        for item in data_list:
            # Hier holen wir den Namen der Station (z.B. "Zürich HB")
            current_station_name = item.get('station', {}).get('name', 'Unbekannt')
            
            stationboard = item.get('stationboard', [])
            for train in stationboard:
                trip_id = f"{train.get('category', '')}{train.get('number', '')}"
                
                stop_info = train.get('stop', {})
                delay = stop_info.get('delay', 0)
                destination = train.get('to', 'Unbekannt')
                
                coords = stop_info.get('station', {}).get('coordinate', {})
                lat = coords.get('x', 0.0)
                lon = coords.get('y', 0.0)

                # Wir speichern jetzt auch 'current_station_name' als origin
                cursor.execute(insert_query, (trip_id, lat, lon, delay, current_station_name, destination))
                inserted_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": f"{inserted_count} Züge gespeichert!"}), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500
    
@app.route('/test-insert', methods=['GET'])
def test_insert():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # FIX: Auch hier die Spalten an das neue Schema anpassen (kein 'speed' mehr)
        insert_query = """
            INSERT INTO radar_logs (trip_id, latitude, longitude, delay, destination)
            VALUES (%s, %s, %s, %s, %s)
        """
        dummy_train = ('TEST_ZUG_001', 47.3769, 8.5417, 15, 'Basel SBB')

        cursor.execute(insert_query, dummy_train)
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success", 
            "message": "Erfolg! Dummy-Zug mit 15 Min Verspätung gespeichert."
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/top-delays', methods=['GET'])
def get_top_delays():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        query = """
            SELECT trip_id, destination, delay, recorded_at 
            FROM radar_logs 
            WHERE delay > 0 
            ORDER BY delay DESC 
            LIMIT 5
        """
        cursor.execute(query)
        bad_news_trains = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(bad_news_trains), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/view-trains', methods=['GET'])
def view_trains():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM radar_logs ORDER BY recorded_at DESC LIMIT 50")
        trains = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(trains), 200
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)