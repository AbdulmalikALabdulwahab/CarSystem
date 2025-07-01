from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = 'System.db'

# -------- Database Connection --------
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

    # Join sessions with car & client info
    sessions = conn.execute('''
        SELECT ws.id, c.license_plate, c.car_type, c.car_brand, c.car_model, c.car_color,
               cl.client_name, cl.client_phone, ws.status, ws.parking_slot
        FROM washing_sessions ws
        JOIN cars c ON ws.car_id = c.id
        JOIN clients cl ON c.client_id = cl.id
        ORDER BY ws.arrival_time ASC
    ''').fetchall()

    # Get raw washing_sessions table
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


@app.route('/management')
def management():
    conn = get_db_connection()
    clients = conn.execute('SELECT * FROM clients ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('management.html', clients=clients)

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


# -------- Main --------
if __name__ == '__main__':
    app.run(debug=True)
