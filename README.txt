Smart Health Monitoring System with X-ray Prediction
======================================================

Project Overview
----------------
This Flask application provides a comprehensive health monitoring system with:
- User registration and authentication
- Real-time health data processing (Heart Rate, SpO2, Temperature, GSR, Accelerometer)
- X-ray image classification for lung diseases using Vision Transformer (ViT)

Features
--------
1. User Management
   - /userregister - Register new users
   - /logincheck - User authentication

2. Health Data API
   - /senddata - POST endpoint for health sensor data
   - /getdata - GET endpoint to retrieve latest health records
   - /history - Get most recent health data

3. X-ray Prediction
   - /predict_vit/<lid> - Upload X-ray image for disease classification
   - /get_xray_history/<lid> - View prediction history

Prerequisites
-------------
- Python 3.8+
- MySQL Server (running locally)
- pip package manager

Installation
------------
1. Create and activate virtual environment (optional but recommended):
   python -m venv venv
   venv\Scripts\activate (Windows) or source venv/bin/activate (Linux/Mac)

2. Install dependencies:
   pip install -r requirements.txt

3. Create MySQL database:
   - Database name: smart_health
   - User: root, Password: root (or update credentials in main_vit.py)
   - Create required tables (login, patient_table, health_data, xray_results)

4. Download the model file:
   - Download lung_vit_model_full.keras from:
   https://drive.google.com/file/d/16zMLkma5Yo6HgVBpFU2VvT9PrwIU-rFp/view?usp=drive_link
   - Place it in the project root directory

Running the Application
-----------------------
python main_vit.py

The server will start at http://0.0.0.0:5000

Model File
----------
The trained ViT model is hosted on Google Drive due to size constraints:
https://drive.google.com/file/d/16zMLkma5Yo6HgVBpFU2VvT9PrwIU-rFp/view?usp=drive_link

Supported Diseases for X-ray Classification:
- Bacterial Pneumonia
- Corona Virus Disease (COVID)
- Normal
- Tuberculosis
- Viral Pneumonia