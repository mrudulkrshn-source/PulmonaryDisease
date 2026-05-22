from datetime import datetime
import math
import os

from flask import Flask, request, jsonify, render_template
import numpy as np
import psycopg2
from werkzeug.utils import secure_filename

# =========================================
# FLASK APP
# =========================================
app = Flask(__name__)

app.config["UPLOAD_FOLDER"] = "static/uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =========================================
# POSTGRESQL DATABASE CONNECTION
# =========================================
def get_db():
    return psycopg2.connect(
        host="localhost",
        user="postgres",          # change if needed
        password="root",          # change your password
        database="smart_health"
    )

# =========================================
# CREATE TABLES AUTOMATICALLY
# =========================================
def create_tables():
    con = get_db()
    cur = con.cursor()

    # LOGIN TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS login (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        password VARCHAR(100) NOT NULL,
        usertype VARCHAR(50) NOT NULL
    )
    """)

    # PATIENT TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS patient_table (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        phone VARCHAR(20),
        dob DATE,
        email VARCHAR(100),
        loginid INTEGER REFERENCES login(id) ON DELETE CASCADE
    )
    """)

    # HEALTH DATA TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS health_data (
        id SERIAL PRIMARY KEY,

        IR FLOAT,
        HeartRate FLOAT,
        SpO2 FLOAT,
        TempC FLOAT,
        TempF FLOAT,
        GSR FLOAT,

        LSM_AccX FLOAT,
        LSM_AccY FLOAT,
        LSM_AccZ FLOAT,

        HR_Status VARCHAR(50),
        SpO2_Status VARCHAR(50),
        Temp_Status VARCHAR(50),
        Stress_Level VARCHAR(50),
        Movement_Status VARCHAR(50),

        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # XRAY RESULTS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS xray_results (
        id SERIAL PRIMARY KEY,

        image_name VARCHAR(255),
        predicted_class VARCHAR(100),
        confidence FLOAT,

        lid INTEGER REFERENCES login(id) ON DELETE CASCADE,

        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    con.commit()
    cur.close()
    con.close()

    print("Database tables created successfully")

# =========================================
# USER REGISTER API
# =========================================
@app.route("/userregister", methods=['POST'])
def userregister():
    try:
        data = request.json

        name = data.get("name")
        phone = data.get("phone")
        dob = data.get("dob")
        email = data.get("email")
        password = data.get("password")

        if not all([name, phone, dob, email, password]):
            return jsonify({"message": "All fields are required"}), 400

        con = get_db()
        cur = con.cursor()

        # CHECK USER EXISTS
        cur.execute(
            "SELECT id FROM login WHERE username=%s",
            (email,)
        )

        res = cur.fetchone()

        if res:
            cur.close()
            con.close()
            return jsonify({"message": "User already exists"}), 409

        # INSERT LOGIN
        cur.execute("""
        INSERT INTO login (username, password, usertype)
        VALUES (%s,%s,%s)
        RETURNING id
        """, (email, password, "user"))

        loginid = cur.fetchone()[0]

        # INSERT PATIENT
        cur.execute("""
        INSERT INTO patient_table
        (name, phone, dob, email, loginid)
        VALUES (%s,%s,%s,%s,%s)
        """, (name, phone, dob, email, loginid))

        con.commit()

        cur.close()
        con.close()

        return jsonify({
            "message": "User registered successfully",
            "loginid": loginid
        })

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)})

# =========================================
# LOGIN API
# =========================================
@app.route("/logincheck", methods=['POST'])
def logincheck():
    try:

        data = request.json

        email = data.get("email")
        password = data.get("password")

        con = get_db()
        cur = con.cursor()

        cur.execute("""
        SELECT id, username, usertype
        FROM login
        WHERE username=%s AND password=%s
        """, (email, password))

        result = cur.fetchone()

        cur.close()
        con.close()

        if result is None:
            return jsonify({'task': "invalid"}), 401

        return jsonify({
            'loginid': result[0],
            'username': result[1],
            'type': result[2],
            'task': "success"
        })

    except Exception as e:
        print(e)
        return jsonify({"error": str(e)})

# =========================================
# STATUS DETECTION
# =========================================
def detect_status(data):

    hr = data['HeartRate']
    spo2 = data['SpO2']
    temp = data['TempC']
    gsr = data['GSR']

    x = data['LSM_AccX']
    y = data['LSM_AccY']
    z = data['LSM_AccZ']

    magnitude = math.sqrt(x*x + y*y + z*z)

    # HEART RATE
    if hr < 60:
        hr_status = "Low"
    elif hr > 100:
        hr_status = "High"
    else:
        hr_status = "Normal"

    # SPO2
    if spo2 < 90:
        spo2_status = "Critical"
    elif spo2 < 95:
        spo2_status = "Low"
    else:
        spo2_status = "Normal"

    # TEMPERATURE
    if temp < 35:
        temp_status = "Low"
    elif temp > 38:
        temp_status = "High"
    else:
        temp_status = "Normal"

    # STRESS
    if gsr < 0.3:
        stress = "Relaxed"
    elif gsr < 0.7:
        stress = "Moderate"
    else:
        stress = "High Stress"

    # MOVEMENT
    if magnitude < 0.5:
        movement = "Free Fall"
    elif magnitude > 2.5:
        movement = "Impact"
    elif magnitude > 1.5:
        movement = "Abnormal"
    else:
        movement = "Normal"

    return hr_status, spo2_status, temp_status, stress, movement

# =========================================
# SEND HEALTH DATA
# =========================================
@app.route('/senddata', methods=['POST'])
def send_data():

    try:

        data = request.get_json()

        if not data:
            return jsonify({"status": "fail"}), 400

        hr_s, spo2_s, temp_s, stress_s, move_s = detect_status(data)

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
        INSERT INTO health_data
        (
            IR, HeartRate, SpO2,
            TempC, TempF, GSR,
            LSM_AccX, LSM_AccY, LSM_AccZ,
            HR_Status, SpO2_Status, Temp_Status,
            Stress_Level, Movement_Status
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data['IR'],
            data['HeartRate'],
            data['SpO2'],
            data['TempC'],
            data['TempF'],
            data['GSR'],
            data['LSM_AccX'],
            data['LSM_AccY'],
            data['LSM_AccZ'],
            hr_s,
            spo2_s,
            temp_s,
            stress_s,
            move_s
        ))

        db.commit()

        cursor.close()
        db.close()

        return jsonify({
            "HR_Status": hr_s,
            "SpO2_Status": spo2_s,
            "Temp_Status": temp_s,
            "Stress_Level": stress_s,
            "Movement_Status": move_s
        })

    except Exception as e:
        return jsonify({"error": str(e)})

# =========================================
# GET HEALTH DATA
# =========================================
@app.route('/getdata', methods=['GET'])
def get_data():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    SELECT * FROM health_data
    ORDER BY id DESC
    LIMIT 20
    """)

    rows = cursor.fetchall()

    columns = [col[0] for col in cursor.description]

    cursor.close()
    db.close()

    data_list = [dict(zip(columns, row)) for row in rows]

    return jsonify(data_list)

# =========================================
# XRAY HISTORY
# =========================================
@app.route("/get_xray_history/<int:lid>", methods=["GET"])
def view_history(lid):

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    SELECT
        id,
        image_name,
        predicted_class,
        confidence,
        uploaded_at
    FROM xray_results
    WHERE lid = %s
    ORDER BY id DESC
    """, (lid,))

    rows = cursor.fetchall()

    result = []

    for row in rows:

        result.append({
            "id": row[0],
            "image_name": row[1],
            "predicted_class": row[2],
            "confidence": float(row[3]),
            "uploaded_at": str(row[4])
        })

    cursor.close()
    db.close()

    return jsonify({
        "status": "success",
        "data": result
    })

# =========================================
# HISTORY API
# =========================================
@app.route("/history", methods=["GET"])
def history():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("""
    SELECT *
    FROM health_data
    ORDER BY timestamp DESC
    LIMIT 1
    """)

    rows = cursor.fetchall()

    columns = [col[0] for col in cursor.description]

    cursor.close()
    db.close()

    data_list = [dict(zip(columns, row)) for row in rows]

    return jsonify(data_list)

# =========================================
# HOME PAGE
# =========================================
@app.route("/")
def home():
    return render_template("index.html")

# =========================================
# START SERVER
# =========================================
if __name__ == "__main__":

    create_tables()

    print("Server Started")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )