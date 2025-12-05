import cv2
import time
import os
from dotenv import load_dotenv
from ultralytics import YOLO
from pymongo import MongoClient
import certifi
from datetime import datetime

# 1. SETUP KONEKSI DATABASE
load_dotenv() # Baca file .env
mongo_uri = os.getenv("MONGO_URI")

try:
    # certifi dibutuhkan untuk koneksi SSL yang aman ke Atlas
    client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
    db = client["I_MBG"] # Pastikan nama DB sama dengan di Atlas
    collection = db["visitor_logs"]
    print("✅ Berhasil konek ke MongoDB Atlas!")
except Exception as e:
    print(f"❌ Gagal konek DB: {e}")
    exit()

# 2. LOAD MODEL AI
print("⏳ Loading model YOLOv8... (bisa agak lama saat pertama kali)")
model = YOLO('yolov8n.pt') # 'n' artinya nano (paling ringan/cepat)

# 3. BUKA KAMERA
# Ganti angka 0 dengan link RTSP jika pakai CCTV beneran
# Contoh: cap = cv2.VideoCapture("rtsp://admin:password@192.168.1.10:554/...")
cap = cv2.VideoCapture(0) 

# Timer untuk pengiriman data (agar tidak spam database)
last_sent_time = time.time()
SEND_INTERVAL = 5 # Kirim data setiap 5 detik

print("📷 Kamera dimulai. Tekan 'q' untuk keluar.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 4. PROSES DETEKSI
    # conf=0.5 artinya hanya deteksi jika yakin 50% ke atas
    # classes=0 artinya hanya deteksi kelas 'person' (manusia)
    results = model(frame, classes=0, conf=0.5, verbose=False)
    
    # Hitung jumlah orang di frame ini
    # results[0].boxes adalah daftar kotak yang terdeteksi
    jumlah_orang = len(results[0].boxes)

    # Gambar kotak di layar (Visualisasi)
    annotated_frame = results[0].plot()

    # Tampilkan jumlah di layar video
    cv2.putText(annotated_frame, f"Orang: {jumlah_orang}", (10, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # 5. LOGIKA KIRIM KE DATABASE
    current_time = time.time()
    if current_time - last_sent_time > SEND_INTERVAL:
        try:
            # Data yang akan dikirim
            data = {
                "timestamp": datetime.now(),
                "camera_id": "CAM_LAPTOP_01",
                "current_occupancy": jumlah_orang,
                "total_in": 0, # Nanti kita update logic ini untuk tracking in/out
                "total_out": 0 
            }
            
            # Insert ke MongoDB
            collection.insert_one(data)
            print(f"📡 Data Terkirim: {jumlah_orang} orang detected.")
            
            last_sent_time = current_time # Reset timer
        except Exception as e:
            print(f"⚠️ Gagal kirim data: {e}")

    # Tampilkan jendela video
    cv2.imshow("Smart Cafe CCTV - AI View", annotated_frame)

    # Tekan 'q' untuk stop
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()