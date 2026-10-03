import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List

app = FastAPI(title="Lock Sentinel Security System")

# ====================================================
# EMAIL NOTIFICATION CONFIGURATION
# ====================================================
# Put your Gmail address and 16-character app password here:
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "ravikishore.rtl@gmail.com")
APP_PASSWORD = os.getenv("APP_PASSWORD", "pawz ktrv bzsy nmmp")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "ravikishore.rtl@gmail.com") # Can be the same as SENDER_EMAIL

# ====================================================
# CLOUDINARY CONFIGURATION
# ====================================================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "w8jdhijo"),
    api_key=os.getenv("CLOUDINARY_API_KEY", "439362228187961"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", "LK0eKy_c13qtBUdfqNRGhP8Q35c")
)

system_state = {"status": "Secure", "latest_image_url": ""}

# ====================================================
# WEBSOCKET MANAGER FOR LIVE FEED
# ====================================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

# ====================================================
# GMAIL ALERT HELPER FUNCTION
# ====================================================
def send_email_alert():
    """Sends an HTML email with dashboard and disarm links."""
    try:
        # Render automatically provides RENDER_EXTERNAL_URL during deployment
        app_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:5000")
        disarm_link = f"{app_url}/api/disarm"
        dashboard_link = f"{app_url}/"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "⚠️ SECURITY ALERT: Lock Sentinel Breach Detected!"
        msg["From"] = f"Lock Sentinel <{SENDER_EMAIL}>"
        msg["To"] = RECEIVER_EMAIL

        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; text-align: center; padding: 20px;">
            <h2 style="color: #d32f2f;">⚠️ SECURITY ALERT: Breach Detected!</h2>
            <p>Your ESP32-CAM has detected an intrusion at the door.</p>
            <br><br>
            <a href="{dashboard_link}" style="padding: 12px 24px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">View Live Camera</a>
            <br><br><br>
            <a href="{disarm_link}" style="padding: 12px 24px; background-color: #28a745; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">Disarm System</a>
          </body>
        </html>
        """
        
        part = MIMEText(html, "html")
        msg.attach(part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("Alert email sent successfully!")
    except Exception as e:
        print("Failed to send email:", e)

# ====================================================
# ESP32 HARDWARE ENDPOINTS
# ====================================================
@app.post("/api/esp/door-opened")
async def door_opened_trigger():
    system_state["status"] = "BREACH DETECTED"
    
    send_email_alert()
    
    await manager.broadcast({
        "event": "breach",
        "status": system_state["status"]
    })
    
    return JSONResponse(status_code=200, content={"status": "success", "message": "Email alert sent"})

@app.post("/api/esp/upload-snapshot")
async def upload_snapshot(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        upload_result = cloudinary.uploader.upload(
            contents,
            folder="lock_sentinel"
        )
        image_url = upload_result.get("secure_url", "")
        system_state["latest_image_url"] = image_url

        await manager.broadcast({
            "event": "new_snapshot",
            "image_url": image_url
        })

        return JSONResponse(status_code=200, content={"status": "success", "url": image_url})
    except Exception as e:
        print("Cloudinary upload failed:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})

# ====================================================
# NEW: ONE-CLICK DISARM ENDPOINT (GET)
# ====================================================
@app.get("/api/disarm", response_class=HTMLResponse)
async def disarm_system_via_email():
    system_state["status"] = "Secure"
    await manager.broadcast({
        "event": "reset",
        "status": system_state["status"]
    })
    
    # This HTML is what you see on your phone when you click the email link
    html_content = """
    <!DOCTYPE html>
    <html>
    <body style="background-color: #121212; color: #fff; text-align: center; padding: 50px; font-family: Arial;">
        <h1 style="color: #4caf50;">✅ System Disarmed</h1>
        <p>The Lock Sentinel is now Secure.</p>
        <a href="/" style="color: #90caf9; text-decoration: none;">Return to Dashboard</a>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Keep the old POST reset route just in case the ESP32 needs it
@app.post("/api/esp/reset")
async def reset_system():
    system_state["status"] = "Secure"
    await manager.broadcast({"event": "reset", "status": system_state["status"]})
    return JSONResponse(status_code=200, content={"status": "success"})

# ====================================================
# WEBSOCKET ENDPOINT
# ====================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await websocket.send_json({
        "event": "init",
        "status": system_state["status"],
        "image_url": system_state["latest_image_url"]
    })
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# ====================================================
# HTML WEB DASHBOARD
# ====================================================
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Lock Sentinel Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #121212; color: #fff; text-align: center; padding: 40px; }
            .badge { font-size: 24px; padding: 15px 30px; border-radius: 8px; display: inline-block; margin-bottom: 25px; font-weight: bold; }
            .Secure { background-color: #2e7d32; }
            .BREACH { background-color: #d32f2f; animation: pulse 1s infinite alternate; }
            @keyframes pulse { from { opacity: 1; } to { opacity: 0.5; } }
            img { max-width: 80%; max-height: 500px; border: 2px solid #444; border-radius: 8px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>Lock Sentinel Security Hub</h1>
        <div id="statusBadge" class="badge Secure">Status: Secure</div>
        <br>
        <img id="cameraView" src="" alt="Awaiting camera snapshot..." onerror="this.style.display='none';">

        <script>
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const ws = new WebSocket(protocol + '//' + window.location.host + '/ws');
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                const badge = document.getElementById('statusBadge');
                const img = document.getElementById('cameraView');

                if (data.status) {
                    badge.innerText = 'Status: ' + data.status;
                    badge.className = 'badge ' + (data.status.includes('BREACH') ? 'BREACH' : 'Secure');
                }
                if (data.image_url) {
                    img.src = data.image_url;
                    img.style.display = 'inline-block';
                }
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
