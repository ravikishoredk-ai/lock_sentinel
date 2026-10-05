import os
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "lock-sentinel-super-secret-key")
CORS(app)

system_status = "SAFE"
last_snapshot_url = ""

# Set your authorized email here (the one you use for Brevo/receiving alerts)
AUTHORIZED_EMAIL = "ravikishore.rtl@gmail.com"

# --- SIGN-IN LOGIN TEMPLATE ---
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LockSentinel | Sign In</title>
    <style>
        :root {
            --bg-primary: #090d16;
            --bg-card: #131c31;
            --border-color: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-blue-hover: #2563eb;
            --alarm-color: #ef4444;
        }
        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .login-card {
            width: 100%;
            max-width: 400px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 35px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6);
            box-sizing: border-box;
            text-align: center;
        }
        h2 { margin-top: 0; color: #f1f5f9; font-size: 22px; }
        p { color: var(--text-muted); font-size: 13px; margin-bottom: 25px; }
        input[type="email"] {
            width: 100%;
            padding: 12px;
            background: #0b1120;
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: white;
            font-size: 14px;
            margin-bottom: 15px;
            box-sizing: border-box;
            outline: none;
        }
        input[type="email"]:focus { border-color: var(--accent-blue); }
        button {
            background-color: var(--accent-blue);
            color: white;
            border: none;
            width: 100%;
            padding: 12px;
            font-size: 15px;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        button:hover { background-color: var(--accent-blue-hover); }
        .error { color: var(--alarm-color); font-size: 12px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login-card">
        <h2>🔒 LockSentinel Access</h2>
        <p>Enter your authorized security email to sign in.</p>
        <form method="POST" action="/login">
            <input type="email" name="email" placeholder="name@example.com" required autocomplete="email">
            <button type="submit">Access Command Center</button>
            {% if error %}
                <div class="error">{{ error }}</div>
            {% endif %}
        </form>
    </div>
</body>
</html>
"""

# --- SECURE DASHBOARD TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LockSentinel | Security Command Center</title>
    <style>
        :root {
            --bg-primary: #090d16;
            --bg-card: #131c31;
            --border-color: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --safe-color: #10b981;
            --warning-color: #f59e0b;
            --alarm-color: #ef4444;
        }
        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-main);
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .dashboard-container {
            width: 100%;
            max-width: 550px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 35px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6);
            box-sizing: border-box;
            text-align: center;
        }
        .header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        h2 { margin: 0; font-size: 22px; color: #f1f5f9; text-align: left; }
        .logout-btn { background: #334155; color: #cbd5e1; border: none; padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer; text-decoration: none; }
        .logout-btn:hover { background: #475569; }
        p.subtitle { color: var(--text-muted); font-size: 13px; margin-bottom: 20px; text-align: left; }
        .status-badge {
            font-size: 20px;
            font-weight: 700;
            padding: 16px;
            border-radius: 10px;
            margin: 20px 0;
            letter-spacing: 1px;
            transition: all 0.3s ease;
        }
        .SAFE { background: rgba(16, 185, 129, 0.15); color: var(--safe-color); border: 1px solid var(--safe-color); }
        .WARNING { background: rgba(245, 158, 11, 0.15); color: var(--warning-color); border: 1px solid var(--warning-color); }
        .ALARM { background: rgba(239, 68, 68, 0.2); color: var(--alarm-color); border: 1px solid var(--alarm-color); animation: pulse-animation 1.2s infinite; }
        @keyframes pulse-animation {
            0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
            70% { transform: scale(1.02); box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
            100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .timer-box {
            background: rgba(245, 158, 11, 0.1);
            border: 1px dashed var(--warning-color);
            border-radius: 8px;
            padding: 12px;
            margin: 15px 0;
            font-size: 15px;
            font-weight: bold;
            color: var(--warning-color);
            display: none;
        }
        .snapshot-section {
            margin: 20px 0;
            border-radius: 10px;
            overflow: hidden;
            background: #0b1120;
            border: 1px solid var(--border-color);
            padding: 10px;
            display: none;
        }
        .snapshot-section h3 { font-size: 13px; color: var(--text-muted); margin: 0 0 10px 0; text-transform: uppercase; }
        img { width: 100%; height: auto; border-radius: 6px; display: block; }
        .action-button {
            background-color: var(--safe-color);
            color: white;
            border: none;
            width: 100%;
            padding: 14px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: background-color 0.2s, transform 0.1s;
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
            margin-top: 15px;
        }
        .action-button:hover { background-color: #059669; }
        .footer-note { margin-top: 20px; font-size: 11px; color: #64748b; }
    </style>
    <script>
        let countdownInterval = null;
        let remainingTime = 55;
        let lastStatus = "{{ status }}";

        function startCountdown(seconds) {
            clearInterval(countdownInterval);
            remainingTime = seconds;
            const timerBox = document.getElementById('timer-box');
            const countdownEl = document.getElementById('countdown');
            timerBox.style.display = "block";

            countdownInterval = setInterval(() => {
                remainingTime--;
                countdownEl.innerText = remainingTime;
                if (remainingTime <= 0) {
                    clearInterval(countdownInterval);
                    timerBox.style.display = "none";
                }
            }, 1000);
        }

        function stopCountdown() {
            clearInterval(countdownInterval);
            document.getElementById('timer-box').style.display = "none";
        }

        setInterval(() => {
            fetch('/api/status')
                .then(res => res.json())
                .then(data => {
                    const badge = document.getElementById('status-badge');
                    badge.innerText = "STATUS: " + data.status;
                    badge.className = "status-badge " + data.status;
                    
                    if (data.status === 'WARNING' && lastStatus !== 'WARNING') {
                        startCountdown(55);
                    } else if (data.status !== 'WARNING') {
                        stopCountdown();
                    }
                    lastStatus = data.status;

                    const imgContainer = document.getElementById('snapshot-container');
                    const imgElement = document.getElementById('snapshot-img');
                    
                    if (data.snapshot_url) {
                        imgElement.src = data.snapshot_url;
                        imgContainer.style.display = "block";
                    } else {
                        imgContainer.style.display = "none";
                    }
                })
                .catch(err => console.error("Sync error:", err));
        }, 3000);

        function disarmSystem() {
            fetch('/api/disarm', { method: 'POST' })
                .then(res => res.json())
                .then(data => { 
                    stopCountdown();
                    alert("System successfully disarmed!"); 
                    location.reload(); 
                })
                .catch(err => alert("Disarm request failed."));
        }
    </script>
</head>
<body>
    <div class="dashboard-container">
        <div class="header-row">
            <h2>🔒 LockSentinel</h2>
            <a href="/logout" class="logout-btn">Sign Out</a>
        </div>
        <p class="subtitle">Logged in as: <strong>{{ user_email }}</strong></p>
        
        <div id="status-badge" class="status-badge {{ status }}">
            STATUS: {{ status }}
        </div>

        <div id="timer-box" class="timer-box">
            ⏱️ Entry Grace Period: <span id="countdown">55</span>s remaining
        </div>
        
        <div id="snapshot-container" class="snapshot-section">
            <h3>Latest Incident Snapshot</h3>
            <img id="snapshot-img" src="" alt="ESP32 Breach Snapshot">
        </div>
        
        <button class="action-button" onclick="disarmSystem()">Disarm Alarm</button>
        
        <div class="footer-note">
            Securely protected via email verification &bull; Render Cloud
        </div>
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
        "sender": {"name": "Lock Sentinel", "email": AUTHORIZED_EMAIL},
        "to": [{"email": AUTHORIZED_EMAIL}],
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_email = request.form.get('email', '').strip().lower()
        if user_email == AUTHORIZED_EMAIL.lower():
            session['authenticated'] = True
            session['email'] = user_email
            return redirect(url_for('index'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error="Access Denied: Email not authorized.")
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template_string(HTML_TEMPLATE, status=system_status, snapshot_url=last_snapshot_url, user_email=session.get('email'))

@app.route('/api/status', methods=['GET'])
def get_status():
    if not session.get('authenticated'):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"status": system_status, "snapshot_url": last_snapshot_url})

@app.route('/api/esp/grace-period', methods=['POST'])
def esp_grace_period():
    global system_status, last_snapshot_url
    system_status = "WARNING"
    data = request.get_json(silent=True) or {}
    last_snapshot_url = data.get("snapshot_url", "")
    send_brevo_email("⚠️️ WARNING: Entry Grace Period Started", "Door opened or motion detected. 55-second entry grace period initiated.", last_snapshot_url)
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
