import os
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BREVO_API_KEY = os.environ.get("BREVO_API_KEY")

system_data = {
    "status": "SAFE",               
    "snapshot_url": ""              
}

def send_email_alert(subject, html_content):
    if not BREVO_API_KEY:
        print("Warning: BREVO_API_KEY is not set. Email not sent.")
        return
        
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }
    payload = {
        "sender": {"email": "alert@sentinel.com", "name": "Sentinel Security"},
        "to": [{"email": "ravikishore.rtl@gmail.com", "name": "Admin"}], # CHANGE THIS
        "subject": subject,
        "htmlContent": html_content
    }
    
    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Failed to send email: {e}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/esp/grace-period", methods=["POST"])
def grace_period():
    body = request.get_json(silent=True) or {}
    system_data["status"] = "GRACE_PERIOD"
    
    if "snapshot_url" in body and body["snapshot_url"]:
        system_data["snapshot_url"] = body["snapshot_url"]
        
    send_email_alert(
        "Security Alert: Grace Period Started", 
        f"<p>The door was opened. The 55-second disarm grace period has started.</p><p>Snapshot available on local network: <a href='{system_data['snapshot_url']}'>View Photo</a></p>"
    )
        
    return jsonify({"success": True, "status": system_data["status"]}), 200

@app.route("/api/esp/door-opened", methods=["POST"])
def door_opened():
    body = request.get_json(silent=True) or {}
    system_data["status"] = "TRIGGERED"
    
    if "snapshot_url" in body and body["snapshot_url"]:
        system_data["snapshot_url"] = body["snapshot_url"]
        
    send_email_alert(
        "CRITICAL: System Triggered!", 
        f"<p>The alarm has been triggered!</p><p>Snapshot available on local network: <a href='{system_data['snapshot_url']}'>View Photo</a></p>"
    )
        
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
