import requests
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Die extrahierten Hubs aus deinem HTML-Skript
HUBS = [
    "Zürich HB", "Bern", "Basel SBB", "Lausanne", "Genève", "Luzern", 
    "St. Gallen", "Lugano", "Olten", "Winterthur", "Chur", "Biel/Bienne"
]

@app.route('/api/radar', methods=['GET'])
def fetch_radar_data():
    results = []
    try:
        # Der API-Connector iteriert nun serverseitig über die Hubs
        for hub in HUBS:
            url = f"https://transport.opendata.ch/v1/stationboard?station={hub}&limit=40"
            response = requests.get(url)
            response.raise_for_status()
            results.append(response.json())
            
        return jsonify({
            "status": "success",
            "data": results
        }), 200
        
    except requests.exceptions.RequestException as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)