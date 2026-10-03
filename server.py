import os
import requests
from flask import Flask, request, jsonify, send_file, render_template_string

app = Flask(__name__)

# ===========================
# FAST2SMS CONFIGURATION
# ===========================
FAST2SMS_API_KEY = " BMEk1yoSKlcCaWAUtgI248ZsV7ODGJdmQ0Pz3TfFjRYh5q6HNwuAa4FLy20PclYIwkWfzmVG3oN1qseJ"
YOUR_PHONE_NUMBER = "9363730659"

# ===========================
# STORAGE SETUP
# ===========================
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
PHOTO_PATH = os.path.join(UPLOAD_FOLDER, 'esp32_cam.jpg')

# Global state to track if the alarm is triggered
system_status = "Secure"

def send_sms_alert():
    """Triggers the Fast2SMS API to send a text message."""
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = {
        "route": "q",
        "message": "⚠️ SECURITY ALERT: Lock Sentinel detected a breach! Check the dashboard.",
        "language": "english",
        "flash": 0,
        "numbers": YOUR_PHONE_NUMBER
    }
    headers = {
        "authorization": FAST2SMS_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = requests.post(url, data=payload, headers=headers)
        print("Fast2SMS Response:", response.text)
    except Exception as e:
        print("Failed to send SMS:", e)

# ===========================
# ESP32 HARDWARE ENDPOINTS
# ===========================
@app.route('/api/esp/door-opened', methods=['POST'])
def handle_esp_trigger():
    global system_status
    system_status = "BREACH DETECTED"
    
    # Send the SMS immediately when the ESP32 pings this route
    send_sms_alert()
    
    return jsonify({"status": "success", "message": "Alert received and SMS sent"}), 200

@app.route('/api/esp/upload-snapshot', methods=['POST'])
def handle_photo_upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    # Save the incoming image, overwriting the old one
    file.save(PHOTO_PATH)
    return jsonify({"status": "success", "message": "Photo uploaded"}), 200

# ===========================
# WEB DASHBOARD ENDPOINTS
# ===========================
@app.route('/latest-photo')
def serve_photo():
    """Serves the most recently uploaded ESP32 image."""
    if os.path.exists(PHOTO_PATH):
        return send_file(PHOTO_PATH, mimetype='image/jpeg')
    return "No photo uploaded yet.", 404

@app.route('/')
def dashboard():
    """A simple auto-refreshing HTML dashboard."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lock Sentinel Dashboard</title>
        <!-- Auto-refresh the page every 5 seconds -->
        <meta http-equiv="refresh" content="5">
        <style>
            body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; background-color: #121212; color: white; }
            .status { font-size: 28px; font-weight: bold; padding: 20px; border-radius: 10px; display: inline-block; margin-bottom: 20px; }
            .secure { background-color: #2e7d32; }
            .breach { background-color: #d32f2f; animation: blinker 1s linear infinite; }
            @keyframes blinker { 50% { opacity: 0; } }
            img { max-width: 90%; max-height: 60vh; border: 3px solid #555; border-radius: 10px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>Lock Sentinel Security System</h1>
        
        <div class="status {% if status == 'Secure' %}secure{% else %}breach{% endif %}">
            System Status: {{ status }}
        </div>
        
        <h3>Latest Camera Snapshot:</h3>
        <img src="/latest-photo" alt="ESP32-CAM Stream" onerror="this.src=''; this.alt='Waiting for first image upload...';">
    </body>
    </html>
    """
    return render_template_string(html, status=system_status)

if __name__ == '__main__':
    # Render binds dynamic ports automatically. This handles it smoothly.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
