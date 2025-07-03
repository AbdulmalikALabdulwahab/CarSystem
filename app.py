from flask import Flask, render_template, request, redirect, url_for,jsonify
import requests
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = 'System.db'

# -------- Database Connection ------
def get_db_connection():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# -------- Homepage: Show Registration Form + Clients + Cars --------
@app.route('/')
def index():
    conn = get_db_connection()
    clients = conn.execute('SELECT * FROM clients').fetchall()
    cars = conn.execute('SELECT * FROM cars').fetchall()
    conn.close()
    return render_template('index.html', clients=clients, cars=cars)

# -------- Handle Registration --------
@app.route('/register', methods=['POST'])
def register():
    # Get form data
    client_name = request.form['client_name']
    client_phone = request.form['client_phone']
    license_plate = request.form['license_plate']
    car_type = request.form['car_type']
    car_brand = request.form['car_brand']
    car_model = request.form['car_model']
    car_year = request.form['car_year']
    car_color = request.form['car_color']

    conn = get_db_connection()

    # Check waiting queue
    waiting_sessions = conn.execute(
        "SELECT COUNT(*) as count FROM washing_sessions WHERE status = 'waiting'"
    ).fetchone()
    if waiting_sessions['count'] >= 3:
        conn.close()
        return "no space"

    # Insert client if not exists
    client = conn.execute(
        'SELECT id FROM clients WHERE client_phone = ?', (client_phone,)
    ).fetchone()
    if client is None:
        conn.execute(
            'INSERT INTO clients (client_name, client_phone) VALUES (?, ?)',
            (client_name, client_phone)
        )
        conn.commit()
        client = conn.execute(
            'SELECT id FROM clients WHERE client_phone = ?', (client_phone,)
        ).fetchone()
    client_id = client['id']

    # Insert car if not exists
    car = conn.execute(
        'SELECT id FROM cars WHERE license_plate = ?', (license_plate,)
    ).fetchone()
    if car is None:
        conn.execute(
            '''INSERT INTO cars 
               (license_plate, car_type, car_brand, car_model, car_year, car_color, client_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (license_plate, car_type, car_brand, car_model, car_year, car_color, client_id)
        )
        conn.commit()
        car = conn.execute(
            'SELECT id FROM cars WHERE license_plate = ?', (license_plate,)
        ).fetchone()
    car_id = car['id']

    # Assign parking slot
    parking_slot = None
    for slot in [1, 2, 3]:
        taken = conn.execute(
            'SELECT 1 FROM washing_sessions WHERE status = "waiting" AND parking_slot = ?',
            (slot,)
        ).fetchone()
        if not taken:
            parking_slot = slot
            break

    # Insert new washing session
    conn.execute(
        '''INSERT INTO washing_sessions (car_id, arrival_time, status, parking_slot)
           VALUES (?, ?, ?, ?)''',
        (car_id, datetime.now(), 'waiting', parking_slot)
    )
    conn.commit()
    conn.close()
    return redirect('/')

# -------- Dashboard --------
@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()

    sessions = conn.execute('''
        SELECT ws.id, c.license_plate, c.car_type, c.car_brand, c.car_model, c.car_color,
               cl.client_name, cl.client_phone, ws.status, ws.parking_slot
        FROM washing_sessions ws
        JOIN cars c ON ws.car_id = c.id
        JOIN clients cl ON c.client_id = cl.id
        ORDER BY ws.arrival_time ASC
    ''').fetchall()

    database = conn.execute('SELECT * FROM washing_sessions').fetchall()

    conn.close()
    return render_template('dashboard.html', sessions=sessions, database=database)

# -------- Start Washing --------
@app.route('/start/<int:session_id>', methods=['POST'])
def start_washing(session_id):
    conn = get_db_connection()
    conn.execute('''
        UPDATE washing_sessions
        SET status = 'washing',
            washing_start_time = ?,
            parking_slot = NULL
        WHERE id = ?
    ''', (datetime.now(), session_id))
    conn.commit()
    conn.close()
    return redirect('/dashboard')

# -------- Finish Washing --------
@app.route('/finish/<int:session_id>', methods=['POST'])
def finish_washing(session_id):
    conn = get_db_connection()
    conn.execute('''
        UPDATE washing_sessions
        SET status = 'done',
            washing_end_time = ?
        WHERE id = ?
    ''', (datetime.now(), session_id))
    conn.commit()
    conn.close()
    return redirect('/dashboard')

# -------- Management --------
@app.route('/management')
def management():
    conn = get_db_connection()
    clients = conn.execute('SELECT * FROM clients ORDER BY id DESC').fetchall()
    cars = conn.execute('SELECT * FROM cars ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('management.html', clients=clients, cars=cars)

@app.route('/management/add', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        client_name = request.form.get('client_name')
        client_phone = request.form.get('client_phone')
        conn = get_db_connection()
        conn.execute('INSERT INTO clients (client_name, client_phone) VALUES (?, ?)', (client_name, client_phone))
        conn.commit()
        conn.close()
        return redirect(url_for('management'))
    return render_template('add_client.html')

@app.route('/management/edit/<int:id>', methods=['GET', 'POST'])
def edit_client(id):
    conn = get_db_connection()
    client = conn.execute('SELECT * FROM clients WHERE id = ?', (id,)).fetchone()

    if request.method == 'POST':
        client_name = request.form.get('client_name')
        client_phone = request.form.get('client_phone')
        conn.execute('UPDATE clients SET client_name = ?, client_phone = ? WHERE id = ?', (client_name, client_phone, id))
        conn.commit()
        conn.close()
        return redirect(url_for('management'))

    conn.close()
    return render_template('edit_client.html', client=client)

@app.route('/management/delete/<int:id>', methods=['POST'])
def delete_client(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM clients WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('management'))

# -------- Clear All Data --------
@app.route('/clear_all_data', methods=['POST'])
def clear_all_data():
    conn = get_db_connection()
    conn.execute('DELETE FROM washing_sessions')
    conn.execute('DELETE FROM cars')
    conn.execute('DELETE FROM clients')
    conn.execute('DELETE FROM sqlite_sequence WHERE name="cars"')
    conn.execute('DELETE FROM sqlite_sequence WHERE name="clients"')
    conn.execute('DELETE FROM sqlite_sequence WHERE name="washing_sessions"')
    conn.commit()
    conn.close()
    return redirect(url_for('management'))

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lambda = math.radians(float(lon2) - float(lon1))

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def get_nearby_car_washes(lat, lon, radius=15000):  # radius in meters
    overpass_url = "http://overpass-api.de/api/interpreter"
    query = f"""
    [out:json];
    (
      node["amenity"="car_wash"](around:{radius},{lat},{lon});
      way["amenity"="car_wash"](around:{radius},{lat},{lon});
      relation["amenity"="car_wash"](around:{radius},{lat},{lon});
    );
    out center;
    """

    response = requests.post(overpass_url, data=query)
    results = []

    if response.status_code == 200:
        data = response.json()
        for element in data['elements']:
            name = element.get('tags', {}).get('name', 'Car Wash')
            lat = element.get('lat') or element.get('center', {}).get('lat')
            lon = element.get('lon') or element.get('center', {}).get('lon')
            if lat and lon:
                results.append({'name': name, 'latitude': lat, 'longitude': lon})
    return results

@app.route('/nearest_station')
def get_nearest_stations():
    user_lat = request.args.get('lat')
    user_lon = request.args.get('lon')

    stations = []  # Initialize early so it's always defined

    if not user_lat or not user_lon:
        return render_template("nearest_station.html", stations=stations, error="Location not provided")

    try:
        # Call Overpass API (or your function that fetches stations)
        stations = get_nearby_car_washes(user_lat, user_lon)

        # Calculate distance and add to each station
        for station in stations:
            station["distance_km"] = round(haversine(user_lat, user_lon, station["latitude"], station["longitude"]), 2)

        # Sort by distance
        stations.sort(key=lambda x: x["distance_km"])

        return render_template("nearest_station.html", stations=stations)

    except Exception as e:
        print(f"Error: {e}")
        return render_template("nearest_station.html", stations=stations, error="Error retrieving nearby stations.")

# -------- Main --------
if __name__ == '__main__':
    app.run(debug=True)
