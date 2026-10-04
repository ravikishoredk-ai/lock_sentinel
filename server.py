import os
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

system_status = "SAFE"
last_snapshot_url = ""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lock Sentinel Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 20px; }
        .card { background: #1e293b; max-width: 500px; margin: 0 auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .status { font-size: 24px; font-weight: bold; padding: 15px; border-radius: 8px; margin: 20px 0; }
        .SAFE { background: #22c55e; color: white; }
        .WARNING { background: #eab308; color: black; }
        .ALARM { background: #ef4444; color: white; }
        button { background: #3b82f6; color: white; border: none; padding: 12px 20px; font-size: 16px; border-radius: 6px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #2563eb; }
        .btn-disarm { background: #10b981; }
        .btn-disarm:hover { background: #059669; }
        img { max-width: 100%; border-radius: 6px; margin-top: 15px; border: 2px solid #475569; }
    </style>
    <script>
        setInterval(() => {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('status-badge').innerText = "STATUS: " + data.status;
                    document.getElementById('status-badge').className = "status " + data.status;
                    if(data.snapshot_url) {
                        document.getElementById('snapshot-img').src = data.snapshot_url;
                        document.getElementById('snapshot-img').style.display = "block";
                    }
                });
        }, 3000);

        function disarmSystem() {
            fetch('/api/disarm', { method: 'POST' })
                .then(res => res.json())
                .then(data => { alert("System Disarmed!"); location.reload(); });
        }
    </script>
</head>
<body>
    <div class="card">
        <h2>Lock Sentinel Security</h2>
        <div id="status-badge" class="status {{ status }}">{{ status }}</div>
        <p>Real-time ESP32-CAM monitoring active.</p>
        
        <div>
            <img id="snapshot-img" src="{{ snapshot_url }}" alt="Incident Snapshot" style="display: {{ 'block' if snapshot_url else 'none' }};">
        </div>
        
        <br>
        <button class="btn-disarm" onclick="disarmSystem()">Disarm Alarm</button>
    </div>
</body>
</html>
"""

def send_brevo_email(subject, message_content, snapshot_url=""):
    api_key = os.environ.get("BREVO_API_KEY")
    if not api_key:
        print("[EMAIL ERROR] BREVO_API_KEY environment variable not set.")
        return
        
    url = "https://api.brevo.com/v3/smtp/email"
    html_content = f"<p>{message_content}</p>"
    
    if snapshot_url:
        html_content += f'<br><a href="{snapshot_url}" target="_blank"><button style="background:#3b82f6;color:white;padding:10px 15px;border:none;border-radius:5px;cursor:pointer;margin-right:10px;">View Incident Photo from ESP32</button></a>'
    
    disarm_link = "https://lock-sentinel.onrender.com/api/disarm"
    html_content += f'<a href="{disarm_link}" target="_blank"><button style="background:#10b981;color:white;padding:10px 15px;border:none;border-radius:5px;cursor:pointer;">Disarm Alarm Now</button></a>'

    payload = {
        "sender": {"name": "Lock Sentinel", "email": "ravikishore.rtl@gmail.com"},
        "to": [{"email": "ravikishore.rtl@gmail.com"}],
        "subject": subject,
        "htmlContent": html_content
    }
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print("Brevo API Response:", response.status_code, response.text)
    except Exception as e:
        print("[EMAIL ERROR] Failed to send email via Brevo:", e)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, status=system_status, snapshot_url=last_snapshot_url)

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({"status": system_status, "snapshot_url": last_snapshot_url})

@app.route('/api/esp/grace-period', methods=['POST'])
def esp_grace_period():
    global system_status, last_snapshot_url
    system_status = "WARNING"
    data = request.get_json(silent=True) or {}
    last_snapshot_url = data.get("snapshot_url", "")
    send_brevo_email("⚠️ WARNING: Entry Grace Period Started", "Door opened or motion detected. 55-second entry grace period initiated.", last_snapshot_url)
    return jsonify({"status": "received"}), 200

@app.route('/api/esp/door-opened', methods=['POST'])
def esp_door_opened():
    global system_status, last_snapshot_url
    system_status = "ALARM"
    data = request.get_json(silent=True) or {}
    last_snapshot_url = data.get("snapshot_url", "")
    send_brevo_email("🚨 CRITICAL ALERT: Alarm Triggered!", "The entry grace period expired or tamper detected. Full alarm active!", last_snapshot_url)
    return jsonify({"status": "received"}), 200

@app.route('/api/esp/status', methods=['GET'])
def esp_poll_status():
    return jsonify({"status": system_status})

@app.route('/api/esp/reset', methods=['POST'])
def esp_reset():
    global system_status, last_snapshot_url
    system_status = "SAFE"
    last_snapshot_url = ""
    return jsonify({"status": "reset_acknowledged"}), 200

@app.route('/api/disarm', methods=['POST', 'GET'])
def manual_disarm():
    global system_status, last_snapshot_url
    system_status = "SAFE"
    last_snapshot_url = ""
    if request.method == 'GET':
        return "<h3>System successfully disarmed via email link! You can close this tab.</h3>"
    return jsonify({"status": "disarmed"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
