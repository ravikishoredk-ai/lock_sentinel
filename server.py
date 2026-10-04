import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Stores the system state and the local IP of the camera
system_data = {
    "status": "SAFE",               
    "snapshot_url": ""              
}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/esp/grace-period", methods=["POST"])
def grace_period():
    body = request.get_json(silent=True) or {}
    system_data["status"] = "GRACE_PERIOD"
    if "snapshot_url" in body and body["snapshot_url"]:
        system_data["snapshot_url"] = body["snapshot_url"]
    return jsonify({"success": True, "status": system_data["status"]}), 200

@app.route("/api/esp/door-opened", methods=["POST"])
def door_opened():
    body = request.get_json(silent=True) or {}
    system_data["status"] = "TRIGGERED"
    if "snapshot_url" in body and body["snapshot_url"]:
        system_data["snapshot_url"] = body["snapshot_url"]
    return jsonify({"success": True, "status": system_data["status"]}), 200

@app.route("/api/esp/status", methods=["GET"])
def get_status():
    return jsonify({
        "status": system_data["status"],
        "snapshot_url": system_data["snapshot_url"]
    }), 200

@app.route("/api/esp/reset", methods=["POST"])
def reset_system():
    system_data["status"] = "SAFE"
    return jsonify({"success": True, "status": "SAFE"}), 200

@app.route("/api/disarm", methods=["POST"])
def disarm_dashboard():
    system_data["status"] = "SAFE"
    return jsonify({"success": True, "status": "SAFE"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
