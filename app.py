# New app.py for Mock API Tool
from flask import Flask, request, jsonify, render_template
import json
import os
import requests

app = Flask(__name__)

DATA_FILE = "endpoints.json"

def load_endpoints():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_endpoints(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route("/")
def index():
    endpoints = load_endpoints()
    return render_template("dashboard.html", endpoints=endpoints)

@app.route("/create", methods=["POST"])
def create():
    new_data = request.get_json()
    endpoints = load_endpoints()

    for ep in endpoints:
        if ep['path'] == new_data['path']:
            ep['responses'].update(new_data['responses'])
            break
    else:
        new_data['id'] = len(endpoints) + 1
        endpoints.append(new_data)

    save_endpoints(endpoints)
    return jsonify({"message": "Endpoint created/updated successfully."})

@app.route("/edit/<int:endpoint_id>", methods=["PUT"])
def edit(endpoint_id):
    updated_data = request.get_json()
    endpoints = load_endpoints()
    found = False

    for i, ep in enumerate(endpoints):
        if ep['id'] == endpoint_id:
            endpoints[i]['path'] = updated_data.get('path', ep['path'])
            endpoints[i]['responses'] = updated_data.get('responses', ep['responses'])
            found = True
            break

    if not found:
        return jsonify({"error": "Endpoint not found."}), 404

    save_endpoints(endpoints)
    return jsonify({"message": "Endpoint updated successfully."})

@app.route("/delete/<int:endpoint_id>", methods=["DELETE"])
def delete(endpoint_id):
    endpoints = load_endpoints()
    endpoints = [ep for ep in endpoints if ep['id'] != endpoint_id]
    save_endpoints(endpoints)
    return jsonify({"message": "Endpoint deleted."})

@app.route("/api/<path:subpath>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def handle_api(subpath):
    full_path = f"/{subpath}"
    method = request.method
    endpoints = load_endpoints()
    print(full_path)
    for ep in endpoints:
        print(ep['path'])
        if ep['path'] == full_path and method in ep['responses']:
            details = ep['responses'][method]
            actual_api = details.get("actual_api")
            schema = details.get("schema")

            # Schema validation if provided
            if schema:
                req_data = request.get_json(silent=True) or {}
                missing_fields = [field for field in schema if field not in req_data]
                if missing_fields:
                    return jsonify({"error": f"Missing fields in request: {missing_fields}"}), 400

            if actual_api:
                try:
                    resp = requests.request(
                        method,
                        actual_api,
                        headers={k: v for k, v in request.headers if k != 'Host'},
                        json=request.get_json(silent=True)
                    )
                    return (resp.content, resp.status_code, resp.headers.items())
                except Exception as e:
                    return jsonify({"error": str(e)}), 500

            return jsonify(details.get("response", {})), details.get("status", 200)

    return jsonify({"error": "No matching endpoint."}), 404

if __name__ == '__main__':
    app.run(debug=True)
