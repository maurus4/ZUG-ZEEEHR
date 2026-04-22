from flask import Flask, jsonify
from flask_cors import CORS
import requests
import mysql.connector
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_CONFIG: dict = {
    'host': 'db',
    'user': 'root',
    'password': 'password123',
    'database': 'sbb_data',
}
API_CONNECTOR_URL = "http://api:5000/api/radar"
ARCHIVE_DELAY_THRESHOLD = 20

def parse_departure(raw: str | None) -> str | None:
    """Parse ISO 8601 departure string from the transport API.
    Keeps CEST local time — no UTC conversion. Returns MySQL-compatible string."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def extract_train_record(train: dict, hub_name: str) -> dict | None:
    """Extract and normalise all fields for one train entry.
    Returns None when coordinates are missing (train cannot appear on map)."""
    stop: dict = train.get('stop', {})
    coords: dict = stop.get('station', {}).get('coordinate', {})
    lat, lon = coords.get('x'), coords.get('y')
    if not lat or not lon:
        return None

    raw_delay = stop.get('delay')
    category = train.get('category', '')
    number = train.get('number', '')
    destination = train.get('to', 'Unbekannt')

    return {
        'trip_id': f"{category}{number}_{destination}",
        'origin': hub_name,
        'destination': destination,
        'delay': int(raw_delay) if raw_delay is not None else 0,
        'departure_time': parse_departure(stop.get('departure')),
        'latitude': lat,
        'longitude': lon,
    }

@app.route('/sync-trains', methods=['GET'])
def sync_trains():
    conn = None
    try:
        response = requests.get(API_CONNECTOR_URL, timeout=15)
        response.raise_for_status()
        raw_data: list = response.json().get('data', [])

        if not raw_data:
            return jsonify({"status": "error", "message": "Keine Daten von API erhalten"}), 500

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("TRUNCATE TABLE active_trains")

        live_query = """
            INSERT INTO active_trains
                (trip_id, origin, destination, delay, departure_time, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                delay          = VALUES(delay),
                departure_time = VALUES(departure_time),
                updated_at     = CURRENT_TIMESTAMP
        """

        archive_query = """
            INSERT INTO delay_archive
                (trip_id, origin, destination, delay, departure_time)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                delay          = VALUES(delay),
                departure_time = VALUES(departure_time),
                recorded_at    = CURRENT_TIMESTAMP
        """

        sync_count = 0
        for item in raw_data:
            hub_name: str = item.get('station', {}).get('name', 'Unbekannt')

            for train in item.get('stationboard', []):
                record = extract_train_record(train, hub_name)
                if record is None:
                    continue

                # LOGIK A: Archiv – koordinatenunabhängig, nur bei hoher Verspätung
                if record['delay'] >= ARCHIVE_DELAY_THRESHOLD:
                    cursor.execute(archive_query, (
                        record['trip_id'],
                        record['origin'],
                        record['destination'],
                        record['delay'],
                        record['departure_time'],
                    ))

                # LOGIK B: Live-Radar
                cursor.execute(live_query, (
                    record['trip_id'],
                    record['origin'],
                    record['destination'],
                    record['delay'],
                    record['departure_time'],
                    record['latitude'],
                    record['longitude'],
                ))
                sync_count += 1

        conn.commit()
        cursor.close()

        return jsonify({
            "status": "success",
            "message": f"Sync abgeschlossen. {sync_count} Züge live. Archiv-Check durchgeführt.",
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"CRITICAL SYNC ERROR: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        if conn and conn.is_connected():
            conn.close()


@app.route('/view-live', methods=['GET'])
def view_live():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                trip_id,
                origin,
                destination,
                delay,
                departure_time,
                CAST(latitude  AS CHAR) AS latitude,
                CAST(longitude AS CHAR) AS longitude
            FROM active_trains
            WHERE departure_time IS NULL
               OR departure_time >= NOW() - INTERVAL 60 MINUTE
        """)
        data: list[dict] = cursor.fetchall()
        cursor.close()
        conn.close()

        for row in data:
            row['latitude'] = float(row['latitude']) if row['latitude'] else 0.0
            row['longitude'] = float(row['longitude']) if row['longitude'] else 0.0
            # departure_time is a datetime object from the driver; serialise to ISO 8601
            dt = row.get('departure_time')
            row['departure_time'] = dt.strftime("%Y-%m-%dT%H:%M:%S") if dt else None

        return jsonify(data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
