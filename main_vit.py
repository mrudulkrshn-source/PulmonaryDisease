from datetime import datetime
from email.mime import image
import math

from flask import *
import numpy as np
import psycopg2
import os
import tensorflow as tf
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"  # Folder path
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)  # Create folder if not exists

con = psycopg2.connect(host='localhost',user='root',password='root',db='smart_health')
cmd = con.cursor()
@app.route("/userregister", methods=['POST'])
def userregister():
    try:
        data = request.json
        print(data)

        name = data.get("name")
        phone = data.get("phone")
        dob = data.get("dob")
        email = data.get("email")
        password = data.get("password")

        if not all([name, phone, dob, email, password]):
            return jsonify({"message": "All fields are required"}), 400

        usertype = "user"  # fixed role

        # Check if username (email) already exists in login table
        cmd.execute("SELECT id FROM login WHERE username=%s", (email,))
        res = cmd.fetchone()
        if res:
            return jsonify({"message": "User already exists"}), 409

        # Insert into login table
        cmd.execute(
            "INSERT INTO login (username, password, usertype) VALUES (%s, %s, %s)",
            (email, password, usertype)
        )
        con.commit()

        loginid = cmd.lastrowid  # get inserted login id

        # Insert into patient table
        cmd.execute(
            "INSERT INTO patient_table (name, phone, dob, email, loginid) VALUES (%s, %s, %s, %s, %s)",
            (name, phone, dob, email, loginid)
        )
        con.commit()

        return jsonify({
            "message": "User registered successfully",
            "loginid": loginid
        }), 200

    except Exception as e:
        con.rollback()
        print("Error:", e)
        return jsonify({"message": "Server error"}), 500

    except Exception as e:
        con.rollback()
        print("Error:", e)
        return jsonify({"message": "Server error"}), 500


@app.route("/logincheck", methods=['POST'])
def logincheck():
    try:
        data = request.json
        print(data)

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({'task': "missing fields"}), 400

        # Correct query (removed email column)
        cmd.execute(
            "SELECT id, username, password, usertype FROM login WHERE username=%s AND password=%s",
            (email, password)
        )

        result = cmd.fetchone()
        print(result)

        if result is None:
            return jsonify({'task': "invalid"}), 401

        loginid, username, _, usertype = result

        return jsonify({
            'loginid': loginid,
            'username': username,
            'type': usertype,
            'task': "success"
        }), 200

    except Exception as e:
        print("Error:", e)
        return jsonify({'task': "failed"}), 500
    


# ================= DATABASE CONNECTION =================
def get_db():
    return pymysql.connect(host='localhost', user='root', password='root', db='smart_health', charset='utf8')

# ================= STATUS DETECTION =================
def detect_status(data):

    hr = data['HeartRate']
    spo2 = data['SpO2']
    temp = data['TempC']
    gsr = data['GSR']
    x = data['LSM_AccX']
    y = data['LSM_AccY']
    z = data['LSM_AccZ']

    magnitude = math.sqrt(x*x + y*y + z*z)

    # Heart Rate
    if hr < 60:
        hr_status = "Low"
    elif hr > 100:
        hr_status = "High"
    else:
        hr_status = "Normal"

    # SpO2
    if spo2 < 90:
        spo2_status = "Critical"
    elif spo2 < 95:
        spo2_status = "Low"
    else:
        spo2_status = "Normal"

    # Temperature
    if temp < 35:
        temp_status = "Low"
    elif temp > 38:
        temp_status = "High"
    else:
        temp_status = "Normal"

    # Stress (GSR)
    if gsr < 0.3:
        stress = "Relaxed"
    elif gsr < 0.7:
        stress = "Moderate"
    else:
        stress = "High Stress"

    # Movement (XYZ magnitude)
    if magnitude < 0.5:
        movement = "Free Fall"
    elif magnitude > 2.5:
        movement = "Impact"
    elif magnitude > 1.5:
        movement = "Abnormal"
    else:
        movement = "Normal"

    return hr_status, spo2_status, temp_status, stress, movement

# ================= HEALTH POST API =================
@app.route('/senddata', methods=['POST'])
def send_data():
    print("---------------------")
    try:
        print("SEND DATA API HIT")   
        data = request.get_json()
        print("Received:", data)

        if not data:
            return jsonify({"status": "fail"}), 400

        hr_s, spo2_s, temp_s, stress_s, move_s = detect_status(data)

        db = get_db()
        cursor = db.cursor()
        tm=str(datetime.datetime.now().strftime("%y-%m-%d %H:%M:%S"))
        cursor.execute("""
        INSERT INTO health_data
        (IR, HeartRate, SpO2, TempC, TempF, GSR,
         LSM_AccX, LSM_AccY, LSM_AccZ,
         HR_Status, SpO2_Status, Temp_Status,
         Stress_Level, Movement_Status,timestamp)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data['IR'], data['HeartRate'], data['SpO2'],
            data['TempC'], data['TempF'], data['GSR'],
            data['LSM_AccX'], data['LSM_AccY'], data['LSM_AccZ'],
            hr_s, spo2_s, temp_s, stress_s, move_s,tm
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

# ================= HEALTH GET API =================
@app.route('/getdata', methods=['GET'])
def get_data():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM health_data ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    cursor.close()
    db.close()

    data_list = [dict(zip(columns, row)) for row in rows]
    return jsonify(data_list)

# ================= HOME PAGE =================
@app.route("/")
def home():
    return render_template("index.html")

# ================= XRAY PREDICTION =================
# from keras.utils import load_img, img_to_array
# import numpy as np

# @app.route("/predict/<int:lid>", methods=["POST"])
# def predict(lid):
#     try:

#         if "file" not in request.files:
#             return jsonify({"error": "No file uploaded"}), 400

#         file = request.files["file"]

#         if file.filename == "":
#             return jsonify({"error": "No selected file"}), 400

#         filename = secure_filename(file.filename)
#         filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#         file.save(filepath)

#         # Load image
#         img = load_img(filepath, target_size=(IMG_SIZE, IMG_SIZE))
#         img_array = img_to_array(img)
#         img_array = tf.keras.applications.efficientnet.preprocess_input(img_array)
#         img_array = np.expand_dims(img_array, axis=0)

#         # Predict
#         predictions = model.predict(img_array)
#         predicted_class = class_names[np.argmax(predictions)]
#         confidence = float(np.max(predictions) * 100)

#         # Save to DB
#         db = get_db()
#         cursor = db.cursor()
#         cursor.execute("""
#             INSERT INTO xray_results (image_name, predicted_class, confidence, lid)
#             VALUES (%s, %s, %s, %s)
#         """, (filename, predicted_class, confidence, lid))
#         db.commit()
#         cursor.close()
#         db.close()

#         return jsonify({
#             "prediction": predicted_class,
#             "confidence": f"{confidence:.2f}%",
#             "image": filename,
#             "lid": lid
#         }), 200

#     except Exception as e:
#         print("Error:", str(e))
#         return jsonify({"error": str(e)}), 500
    
@app.route("/get_xray_history/<int:lid>", methods=["GET"])
def view_history(lid):
    
        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
            SELECT id, image_name, predicted_class, confidence, uploaded_at
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
                "uploaded_at": str(row[4]) if row[4] else ""
            })

        cursor.close()
        db.close()

        return jsonify({"status": "success", "data": result}), 200

# ================= HISTORY PAGE =================
@app.route("/history", methods=["POST", "GET"])
def history():

    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM health_data ORDER BY timestamp DESC LIMIT 1")
    
    rows = cursor.fetchall()   # Fetch only once
    columns = [col[0] for col in cursor.description]

    cursor.close()
    db.close()

    data_list = [dict(zip(columns, row)) for row in rows]

    print("***************")
    print(data_list)
    print("***************")

    return jsonify(data_list)

# --------------------------------------Vit------------------------------------------------------


# import tensorflow as tf
# import numpy as np
# from PIL import Image
# from transformers import TFViTModel
# from tensorflow.keras.layers import Dense, Dropout, Flatten
# from tensorflow.keras.models import Model

# IMG_SIZE = 224

# class_names = [
#     "Bacterial Pneumonia",
#     "Corona Virus Disease",
#     "Normal",
#     "Tuberculosis",
#     "Viral Pneumonia"
# ]

# print("Loading Vision Transformer model...")

# # -------------------------
# # Rebuild architecture
# # -------------------------

# vit_model = TFViTModel.from_pretrained("google/vit-base-patch16-224-in21k")

# for layer in vit_model.layers:
#     layer.trainable = False

# inputs = tf.keras.Input(shape=(224,224,3))

# x = tf.transpose(inputs, perm=[0,3,1,2])

# vit_output = vit_model(pixel_values=x).last_hidden_state

# x = Flatten()(vit_output)
# x = Dense(512, activation="relu")(x)
# x = Dropout(0.5)(x)

# outputs = Dense(5, activation="softmax")(x)

# model = Model(inputs=inputs, outputs=outputs)

# model.load_weights("lung_vit_model.keras")

# print("Model Loaded Successfully")


# @app.route("/predict_vit/<int:lid>", methods=["POST"])
# def predict(lid):
#     try:

#         if "file" not in request.files:
#             return jsonify({"error": "No file uploaded"}), 400

#         file = request.files["file"]

#         if file.filename == "":
#             return jsonify({"error": "No selected file"}), 400

#         filename = secure_filename(file.filename)
#         filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
#         file.save(filepath)

#         # preprocess image
#         img = preprocess_image(filepath)

#         # prediction
#         predictions = model.predict(img)

#         predicted_class = class_names[np.argmax(predictions)]
#         confidence = float(np.max(predictions) * 100)

#         # save to database
#         db = get_db()
#         cursor = db.cursor()

#         cursor.execute("""
#             INSERT INTO xray_results (image_name, predicted_class, confidence, lid)
#             VALUES (%s,%s,%s,%s)
#         """, (filename, predicted_class, confidence, lid))

#         db.commit()
#         cursor.close()
#         db.close()

#         return jsonify({
#             "prediction": predicted_class,
#             "confidence": f"{confidence:.2f}%",
#             "image": filename,
#             "lid": lid
#         }), 200

#     except Exception as e:
#         print("Error:", str(e))
#         return jsonify({"error": str(e)}), 500

# ---------------------------------------------------------------------------

from flask import Flask, request, jsonify
# import tensorflow as tf
import numpy as np
# from tensorflow.keras.preprocessing import image
# from transformers import TFViTModel
import os

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# =========================
# LOAD MODEL (LOAD ONCE)
# =========================
# from transformers import TFViTModel

# model = tf.keras.models.load_model(
#     "lung_vit_model_full.keras",
#     compile=False,
#     custom_objects={"TFViTModel": TFViTModel}
# )

print("Model Loaded Successfully")

# =========================
# CLASS LABELS
# =========================
class_names = [
    "Bacterial Pneumonia",
    "Corona Virus Disease",
    "Normal",
    "Tuberculosis",
    "Viral Pneumonia"
]

# =========================
# PREDICTION API
# =========================
# @app.route("/predict_vit/<int:lid>", methods=["POST"])
# def predict_vit(lid):
#     print("PREDICTION API HIT-------------------")

#     try:

#         if "file" not in request.files:
#             return jsonify({"error": "No file uploaded"}), 400

#         file = request.files["file"]

#         filename = secure_filename(file.filename)
#         filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

#         file.save(filepath)

#         # Image preprocess
#         img = image.load_img(filepath, target_size=(224,224))
#         img_array = image.img_to_array(img)

#         img_array = img_array / 255.0
#         img_array = np.expand_dims(img_array, axis=0)

#         # Prediction
#         prediction = model.predict(img_array)

#         predicted_class = class_names[np.argmax(prediction)]
#         confidence = float(np.max(prediction) * 100)

#         # Save result to DB
#         db = get_db()
#         cursor = db.cursor()

#         cursor.execute("""
#         INSERT INTO xray_results (image_name, predicted_class, confidence, lid)
#         VALUES (%s,%s,%s,%s)
#         """, (filename, predicted_class, confidence, lid))

#         db.commit()
#         cursor.close()
#         db.close()
#         print("-------class------>", predicted_class, confidence)

#         return jsonify({
#             "prediction": predicted_class,
#             "confidence": f"{confidence:.2f}%",
#             "image": filename,
#             "lid": lid
#         })

#     except Exception as e:
#         return jsonify({"error": str(e)})
    

# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)