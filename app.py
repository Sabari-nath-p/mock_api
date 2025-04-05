from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import json
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mockapi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class MockEndpoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    response_json = db.Column(db.Text, nullable=False)
    status_code = db.Column(db.Integer, default=200)
    auth_key = db.Column(db.String(255), nullable=True)
    validation_schema = db.Column(db.Text, nullable=True)

@app.before_request
def create_tables():
    db.create_all()

@app.route('/')
def index():
    endpoints = MockEndpoint.query.all()
    return render_template('dashboard.html', endpoints=endpoints)

@app.route('/create', methods=['POST'])
def create_endpoint():
    data = request.json
    path = data.get('path')
    responses = data.get('responses')

    if not path or not responses:
        return jsonify({"error": "Missing required data"}), 400

    for method, config in responses.items():
        try:
            response = config.get('response', {})
            status = int(config.get('status', 200))
            auth_key = config.get('auth_key')
            validation = config.get('validation') or {}

            response_json = json.dumps(response)
            validation_json = json.dumps(validation)

            existing = MockEndpoint.query.filter_by(path=path, method=method).first()
            if existing:
                existing.response_json = response_json
                existing.status_code = status
                existing.auth_key = auth_key
                existing.validation_schema = validation_json
            else:
                db.session.add(MockEndpoint(
                    path=path, method=method,
                    response_json=response_json,
                    status_code=status,
                    auth_key=auth_key,
                    validation_schema=validation_json
                ))
        except Exception as e:
            return jsonify({"error": f"Invalid config for {method}: {str(e)}"}), 400

    db.session.commit()
    return jsonify({"message": "Endpoint created"}), 201

@app.route('/delete/<int:endpoint_id>', methods=['DELETE'])
def delete_endpoint(endpoint_id):
    endpoint = MockEndpoint.query.get(endpoint_id)
    if not endpoint:
        return jsonify({"error": "Endpoint not found"}), 404

    db.session.delete(endpoint)
    db.session.commit()
    return jsonify({"message": "Endpoint deleted"})

@app.route('/<path:custom_path>', methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def handle_mock(custom_path):
    path = "/" + custom_path
    method = request.method
    ep = MockEndpoint.query.filter_by(path=path, method=method).first()

    if not ep:
        return jsonify({"error": "Not found or method not allowed"}), 404

    # Check for Authorization header
    if ep.auth_key:
        provided_key = request.headers.get("Authorization")
        if provided_key != ep.auth_key:
            return jsonify({"error": "Unauthorized"}), 401

    # Validate input JSON if method requires body
    if method in ['POST', 'PUT', 'PATCH']:
        try:
            input_data = request.get_json(force=True)
            schema = json.loads(ep.validation_schema) if ep.validation_schema else {}

            for field, rule in schema.items():
                value = input_data.get(field)

                if rule.get("required") and field not in input_data:
                    return jsonify({"error": f"'{field}' is required"}), 400

                if "type" in rule and field in input_data:
                    expected_type = rule["type"]
                    if expected_type == "int" and not isinstance(value, int):
                        return jsonify({"error": f"'{field}' must be an integer"}), 400
                    if expected_type == "str" and not isinstance(value, str):
                        return jsonify({"error": f"'{field}' must be a string"}), 400

                if "match" in rule and field in input_data:
                    allowed_values = rule["match"]
                    if value not in allowed_values:
                        return jsonify({"error": f"'{field}' must be one of {allowed_values}"}), 400

        except Exception as e:
            return jsonify({"error": f"Validation error: {str(e)}"}), 400

    return jsonify(json.loads(ep.response_json)), ep.status_code

if __name__ == '__main__':
    app.run(debug=True)
