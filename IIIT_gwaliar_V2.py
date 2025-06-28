from flask import Flask, request, render_template_string, redirect, url_for, jsonify ,session
import threading
import time
from datetime import datetime
import logging
import xml.etree.ElementTree as ET
from werkzeug.middleware.proxy_fix import ProxyFix 
import requests  # Make sure this is imported at the top of the file
import json
import os
from werkzeug.security import generate_password_hash, check_password_hash

USER_FILE = 'users.json'

def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f)

users = load_users()

ESP32_URL = "http://192.168.214.66/receive_medication"  # Update with ESP32's IP or hostname

pending_command = None

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Login - Saathi</title>
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #fff;
            display: flex;
            height: 100vh;
            justify-content: center;
            align-items: center;
        }
        .form-container {
            background: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
            width: 300px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.2);
        }
        h2 {
            margin-bottom: 20px;
            text-align: center;
        }
        input {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: none;
            border-radius: 10px;
        }
        button {
            width: 100%;
            padding: 10px;
            background: #4299e1;
            border: none;
            color: white;
            border-radius: 10px;
            cursor: pointer;
            font-weight: bold;
        }
        button:hover {
            background: #3182ce;
        }
        .link {
            margin-top: 15px;
            text-align: center;
        }
    </style>
</head>
<body>
<div class="form-container">
    <h2>Login</h2>
    <form method="POST">
        <input type="text" name="username" placeholder="Username" required/>
        <input type="password" name="password" placeholder="Password" required/>
        <button type="submit">Login</button>
    </form>
    <div class="link">
        <a href="/register" style="color:#fff;">Don't have an account? Register</a>
    </div>
</div>
</body>
</html>
"""

REGISTER_HTML = LOGIN_HTML.replace("Login", "Register").replace("/register", "/login").replace("Login</button>", "Register</button>")

# HTML Template (same as original)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Health Monitor Dashboard</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
            animation: fadeInDown 1s ease-out;
        }
        
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .header .subtitle {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            animation: fadeInUp 0.8s ease-out;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
        }
        
        .card-header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            color: #4a5568;
        }
        
        .card-header i {
            font-size: 1.5rem;
            margin-right: 15px;
            padding: 10px;
            border-radius: 10px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }
        
        .card-header h2 {
            font-size: 1.3rem;
            font-weight: 600;
        }
        
        .temperature-display {
            font-size: 3rem;
            font-weight: bold;
            text-align: center;
            color: #2d3748;
            margin: 20px 0;
        }
        
        .temperature-unit {
            font-size: 1.5rem;
            color: #718096;
        }
        
        .status-indicator {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 25px;
            font-size: 0.9rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .status-normal { background: #c6f6d5; color: #22543d; }
        .status-warning { background: #fed7d7; color: #742a2a; }
        .status-critical { 
            background: #fed7d7; 
            color: #742a2a; 
            animation: pulse 2s infinite;
        }
        .status-unknown { background: #e2e8f0; color: #4a5568; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .emergency-alert {
            background: linear-gradient(135deg, #fc8181, #f56565);
            color: white;
            padding: 20px;
            border-radius: 15px;
            margin: 15px 0;
            text-align: center;
            font-weight: bold;
            font-size: 1.1rem;
            animation: alertPulse 1.5s infinite;
            box-shadow: 0 5px 15px rgba(245, 101, 101, 0.4);
        }
        
        @keyframes alertPulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.02); }
        }
        
        .map-container {
            margin: 20px 0;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .map {
            width: 100%;
            height: 250px;
            border: none;
        }
        
        .medicine-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .med-btn {
            background: linear-gradient(135deg, #4299e1, #3182ce);
            color: white;
            border: none;
            padding: 15px 20px;
            border-radius: 12px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .med-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(66, 153, 225, 0.4);
        }
        
        .med-btn:active {
            transform: translateY(0);
        }
        
        .med-btn.dispensing {
            background: linear-gradient(135deg, #f6ad55, #ed8936);
            animation: dispensing 2s infinite;
        }
        
        @keyframes dispensing {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .status-item {
            text-align: center;
            padding: 15px;
            background: rgba(79, 172, 254, 0.1);
            border-radius: 12px;
            border: 2px solid rgba(79, 172, 254, 0.2);
        }
        
        .status-item.active {
            background: rgba(245, 101, 101, 0.1);
            border-color: rgba(245, 101, 101, 0.3);
            animation: activeGlow 2s infinite;
        }
        
        @keyframes activeGlow {
            0%, 100% { box-shadow: 0 0 5px rgba(245, 101, 101, 0.3); }
            50% { box-shadow: 0 0 20px rgba(245, 101, 101, 0.6); }
        }
        
        .vital-signs {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .vital-item {
            text-align: center;
            padding: 15px 10px;
        }
        
        .vital-value {
            font-size: 1.8rem;
            font-weight: bold;
            color: #2d3748;
        }
        
        .vital-label {
            font-size: 0.8rem;
            color: #718096;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 5px;
        }
        
        .last-updated {
            text-align: center;
            color: #718096;
            font-size: 0.9rem;
            margin-top: 20px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.5);
            border-radius: 10px;
        }
        
        .no-data {
            text-align: center;
            color: #a0aec0;
            font-style: italic;
            padding: 20px;
        }
        
        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @media (max-width: 768px) {
            .container { padding: 15px; }
            .header h1 { font-size: 2rem; }
            .temperature-display { font-size: 2.5rem; }
            .card { padding: 20px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-heartbeat"></i> Saathi</h1>
            <div class="subtitle">Real-time Health Monitoring & Emergency Response System</div>
        </div>
        
        <div class="dashboard-grid">
            <!-- Temperature Card -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-thermometer-half"></i>
                    <h2>Body Temperature</h2>
                </div>
                {% if temperature is not none %}
                    <div class="temperature-display">
                        {{ "%.1f"|format(temperature) }}<span class="temperature-unit">°C</span>
                    </div>
                    <div class="status-indicator {{ 'status-critical' if temperature > 38 else 'status-warning' if temperature > 37.5 else 'status-normal' if temperature is not none else 'status-unknown' }}">
                        {{ 'Critical' if temperature > 38 else 'Elevated' if temperature > 37.5 else 'Normal' if temperature is not none else 'Unknown' }}
                    </div>
                {% else %}
                    <div class="no-data">No temperature data available</div>
                {% endif %}
            </div>
            
            <!-- Emergency Status Card -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h2>Emergency Status</h2>
                </div>
                {% if emergency == "fall" %}
                    <div class="emergency-alert">
                        <i class="fas fa-falling"></i> FALL DETECTED!
                        <br><small>Immediate assistance required</small>
                    </div>
                {% elif emergency == "health" %}
                    <div class="emergency-alert">
                        <i class="fas fa-heart-broken"></i> HEALTH EMERGENCY!
                        <br><small>Medical attention needed</small>
                    </div>
                {% else %}
                    <div class="status-indicator status-normal">
                        <i class="fas fa-check-circle"></i> All Clear
                    </div>
                {% endif %}
            </div>
            
            <!-- Vital Signs Card -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-activity"></i>
                    <h2>Vital Signs</h2>
                </div>
                <div class="vital-signs">
                    <div class="vital-item">
                        <div class="vital-value">{{ heart_rate if heart_rate is not none else "--" }}</div>
                        <div class="vital-label">Heart Rate</div>
                    </div>
                    <div class="vital-item">
                        <div class="vital-value">{{ battery_level if battery_level is not none else "--" }}%</div>
                        <div class="vital-label">Battery</div>
                    </div>
                </div>
            </div>
            
            <!-- Location Card -->
            <div class="card">
                <div class="card-header">
                    <i class="fas fa-map-marker-alt"></i>
                    <h2>Current Location</h2>
                </div>
                {% if location and location.lat is not none and location.lon is not none %}
                    <div class="map-container">
                        <div id="map" class="map"></div>
                    </div>
                    <div style="text-align: center; font-size: 0.9rem; color: #718096;">
                        Lat: {{ "%.6f"|format(location.lat) }}, Lon: {{ "%.6f"|format(location.lon) }}
                    </div>
                {% else %}
                    <div class="no-data">
                        <i class="fas fa-map-marker-slash"></i><br>
                        No location data available
                    </div>
                {% endif %}
            </div>
        </div>
        
        <!-- Medicine Vending Machine Card -->
        <div class="card">
            <div class="card-header">
                <i class="fas fa-pills"></i>
                <h2>Medicine Vending Machine</h2>
            </div>
            <form method="post" action="/dispense">
                <div class="medicine-grid">
                    {% for port in medicine_ports %}
                        <button class="med-btn {{ 'dispensing' if port.dispensing else '' }}" 
                                name="port" value="{{ port.port_id }}" 
                                {{ 'disabled' if port.dispensing else '' }}>
                            <i class="fas fa-prescription-bottle"></i>
                            {{ port.medication }}
                            {% if port.dispensing %}
                                <br><small>Dispensing...</small>
                            {% endif %}
                        </button>
                    {% endfor %}
                </div>
            </form>
            
            <div class="status-grid">
                {% for port in medicine_ports %}
                    <div class="status-item {{ 'active' if port.dispensing else '' }}">
                        <strong>Port {{ port.port_id }}</strong><br>
                        <small>{{ "Dispensing" if port.dispensing else "Ready" }}</small>
                        {% if port.last_dispensed %}
                            <br><small style="color: #a0aec0;">Last: {{ port.last_dispensed }}</small>
                        {% endif %}
                    </div>
                {% endfor %}
            </div>
        </div>
        
        {% if last_updated %}
            <div class="last-updated">
                <i class="fas fa-clock"></i> Last updated: {{ last_updated }}
            </div>
        {% endif %}
    </div>
    
    {% if location and location.lat is not none and location.lon is not none %}
        <script>
            function initMap() {
                var loc = {lat: {{ location.lat }}, lng: {{ location.lon }} };
                var map = new google.maps.Map(document.getElementById('map'), {
                    zoom: 16,
                    center: loc,
                    styles: [
                        {
                            "featureType": "all",
                            "elementType": "geometry.fill",
                            "stylers": [{"weight": "2.00"}]
                        },
                        {
                            "featureType": "all",
                            "elementType": "geometry.stroke",
                            "stylers": [{"color": "#9c9c9c"}]
                        },
                        {
                            "featureType": "all",
                            "elementType": "labels.text",
                            "stylers": [{"visibility": "on"}]
                        }
                    ]
                });
                var marker = new google.maps.Marker({
                    position: loc, 
                    map: map,
                    title: 'Patient Location',
                    icon: {
                        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="#4299e1"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>'),
                        scaledSize: new google.maps.Size(40, 40)
                    }
                });
            }
        </script>
        <script src="https://maps.googleapis.com/maps/api/js?key=YOUR_GOOGLE_MAPS_API_KEY&callback=initMap"
        async defer></script>
    {% endif %}
    
    <script>
        // Auto-refresh page every 30 seconds
        setTimeout(function() {
            location.reload();
        }, 30000);
    </script>
</body>
</html>
"""

class DeviceData:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {
            "temperature": None,
            "emergency": None,
            "location": {"lat": None, "lon": None},
            "last_updated": None,
            "battery_level": None,
            "heart_rate": None,
            "device_status": "disconnected"
        }
    
    def update(self, new_data):
        with self.lock:
            # Only update fields that are provided
            for key, value in new_data.items():
                if key == "location" and isinstance(value, dict):
                    self.data["location"].update(value)
                elif value is not None:
                    self.data[key] = value
            self.data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"Data updated: {self.data}")

class MedicineDispenser:
    def __init__(self, num_ports=7):  # Changed to 7 ports to match ESP32
        self.lock = threading.Lock()
        self.ports = [{
            "port_id": i+1,
            "dispensing": False,
            "last_dispensed": None,
            "medication": f"Med-{i+1}",
            "taken": False,
            "schedule": []
        } for i in range(num_ports)]

    def dispense(self, port_id):
        with self.lock:
            port = next((p for p in self.ports if p["port_id"] == port_id), None)
            if port and not port["dispensing"]:
                port["dispensing"] = True
                port["taken"] = False
                
                def dispensing_task():
                    time.sleep(5)  # Simulate dispensing time
                    with self.lock:
                        port["dispensing"] = False
                        port["last_dispensed"] = datetime.now().strftime("%H:%M:%S")
                        logger.info(f"Port {port_id} dispensed")
                
                threading.Thread(target=dispensing_task).start()
                return True
            return False
    
    def confirm_taken(self, port_id, taken):
        with self.lock:
            port = next((p for p in self.ports if p["port_id"] == port_id), None)
            if port:
                port["taken"] = taken
                return True
            return False

# Initialize components with default values
esp32_data = DeviceData()
dispenser = MedicineDispenser()

def parse_xml_data(xml_string):
    """Parse XML data from ESP32"""
    try:
        root = ET.fromstring(xml_string)
        data = {}
        
        # Extract temperature
        temp_elem = root.find('temperature')
        if temp_elem is not None:
            data['temperature'] = float(temp_elem.text)
        
        # Extract emergency status
        emergency_elem = root.find('emergency')
        if emergency_elem is not None:
            data['emergency'] = emergency_elem.text
        
        # Extract location
        location_elem = root.find('location')
        if location_elem is not None:
            lat_elem = location_elem.find('lat')
            lon_elem = location_elem.find('lon')
            if lat_elem is not None and lon_elem is not None:
                data['location'] = {
                    'lat': float(lat_elem.text),
                    'lon': float(lon_elem.text)
                }
        # Extract heart rate
        hr_elem = root.find('heart_rate')
        if hr_elem is not None:
            data['heart_rate'] = int(hr_elem.text)
        
        # Extract battery level
        battery_elem = root.find('battery_level')
        if battery_elem is not None:
            data['battery_level'] = int(battery_elem.text)
        return data
    except Exception as e:
        logger.error(f"Error parsing XML: {str(e)}")
        return {}

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in users:
            return REGISTER_HTML + "<script>alert('User already exists');</script>"

        users[username] = generate_password_hash(password)
        save_users(users)
        return redirect(url_for('login'))

    return REGISTER_HTML

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username in users and check_password_hash(users[username], password):
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            return LOGIN_HTML + "<script>alert('Invalid credentials');</script>"

    return LOGIN_HTML


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    with esp32_data.lock, dispenser.lock:
        # Ensure all required fields exist
        data = {
            "temperature": esp32_data.data.get("temperature"),
            "emergency": esp32_data.data.get("emergency"),
            "location": esp32_data.data.get("location", {}),
            "medicine_ports": dispenser.ports,
            "last_updated": esp32_data.data.get("last_updated"),
            "heart_rate": esp32_data.data.get("heart_rate"),
            "battery_level": esp32_data.data.get("battery_level")
        }
        return render_template_string(DASHBOARD_HTML, **data)

@app.route('/esp32', methods=['POST'])
def esp32_endpoint():
    try:
        # Check if data is JSON or XML
        content_type = request.headers.get('Content-Type', '')
        
        if 'application/json' in content_type:
            # Handle JSON data (original format)
            data = request.get_json()
            if not data:
                return jsonify({"error": "No data provided"}), 400
            
            update_data = {
                "temperature": data.get("temperature"),
                "emergency": data.get("emergency"),
                "heart_rate": data.get("heart_rate"),
                "battery_level": data.get("battery_level"),
                "device_status": "connected"
            }
            
            if "location" in data:
                update_data["location"] = {
                    "lat": data["location"].get("lat"),
                    "lon": data["location"].get("lon")
                }
                
        elif 'application/xml' in content_type:
            # Handle XML data from ESP32
            xml_data = request.get_data(as_text=True)
            if not xml_data:
                return jsonify({"error": "No XML data provided"}), 400
            
            update_data = parse_xml_data(xml_data)
            update_data["device_status"] = "connected"
            
        else:
            return jsonify({"error": "Unsupported content type"}), 400
        
        esp32_data.update(update_data)
        return jsonify({"status": "ok", "timestamp": esp32_data.data["last_updated"]})
    
    except Exception as e:
        logger.error(f"Error processing ESP32 data: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
@app.route('/dispense', methods=['POST'])
def dispense_medicine():
    global pending_command
    try:
        port = int(request.form.get("port", 0))
        if 1 <= port <= 7:
            if dispenser.dispense(port):
                pending_command = {"medication_id": port}  # <-- store here
                try:
                    requests.post(ESP32_URL, json={"medication_id": port}, timeout=2)
                    logger.info(f"Sent medication ID {port} to ESP32")
                except Exception as esp_err:
                    logger.warning(f"Failed to notify ESP32: {esp_err}")
                return redirect(url_for('dashboard'))
        return redirect(url_for('dashboard')), 400
    except Exception as e:
        logger.error(f"Dispense error: {str(e)}")
        return redirect(url_for('dashboard')), 500

# New API endpoint for dispenser confirmation from ESP32
@app.route('/api/dispenser/confirm', methods=['POST'])
def dispenser_confirm():
    try:
        content_type = request.headers.get('Content-Type', '')
        
        if 'application/xml' in content_type:
            xml_data = request.get_data(as_text=True)
            root = ET.fromstring(xml_data)
            
            port_elem = root.find('port')
            status_elem = root.find('status')
            
            if port_elem is not None and status_elem is not None:
                port_id = int(port_elem.text)
                status = status_elem.text
                
                logger.info(f"Dispenser confirmation - Port: {port_id}, Status: {status}")
                
                # Update dispenser status if needed
                with dispenser.lock:
                    port = next((p for p in dispenser.ports if p["port_id"] == port_id), None)
                    if port:
                        if status == "dispensed":
                            port["last_dispensed"] = datetime.now().strftime("%H:%M:%S")
                
                return jsonify({"status": "ok"})
        
        return jsonify({"error": "Invalid request format"}), 400
    
    except Exception as e:
        logger.error(f"Dispenser confirm error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

# API endpoint to send dispense commands to ESP32
@app.route('/api/dispenser/command', methods=['GET'])
def dispenser_command():
    global pending_command
    if pending_command:
        cmd = pending_command
        pending_command = None  # Clear after sending
        return jsonify(cmd)
    return jsonify({"medication_id": None})

@app.route('/api/status', methods=['GET'])
def api_status():
    with esp32_data.lock, dispenser.lock:
        return jsonify({
            "patient_data": esp32_data.data,
            "dispenser": {
                "ports": dispenser.ports,
                "status": "online"
            },
            "timestamp": datetime.now().isoformat()
        })

if __name__ == '__main__':
    app.secret_key = 'meow1208'  # 🔒 Replace this with a secure key in production
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=True)
    
