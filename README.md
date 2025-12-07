# 👁️ CCTV Smart Monitor & Visitor Counter

Sistem pemantauan cerdas berbasis AI untuk menghitung jumlah pengunjung secara real-time. Proyek ini menggabungkan **Computer Vision (Python)** untuk deteksi, **Backend API (Express.js)** untuk manajemen data, dan **Frontend Dashboard** untuk visualisasi statistik.

---

## ✨ Fitur Utama

* **Real-time Human Detection:** Menggunakan model AI YOLOv8 untuk mendeteksi manusia secara akurat.
* **Live Visitor Counter:** Menghitung jumlah orang yang tertangkap kamera saat ini (Live Count).
* **Daily Statistics:** Akumulasi jumlah pengunjung harian (reset otomatis setiap hari).
* **Web Dashboard:** Antarmuka visual untuk memantau trafik pengunjung dari browser.
* **Fast API Integration:** Komunikasi data realtime antara Python Engine dan Node.js Server.

---

## 🗂️ Struktur Project

```
/project-root
  ├── /backend        # REST API & Business Logic (Node.js + Express)
  ├── /frontend       # Dashboard Interface (Node.js + HTML/EJS/React)
  └── /ai-engine      # Computer Vision Script (Python + YOLO)
```

---

## 🛠️ Persyaratan Sistem

* **Node.js** minimal versi 16
* **Python** minimal versi 3.10
* **Webcam** (internal atau USB)

---

# 🚀 Cara Menjalankan Project

> **Penting:** Buka **3 terminal** berbeda untuk setiap service.

---

## 1️⃣ Backend (Server API)

Jembatan komunikasi data Python → Node.js.

```bash
cd backend
npm install
node server.js
```

Output normal: `Server running on port 5000`

---

## 2️⃣ Frontend (Dashboard UI)

Antarmuka visual untuk memantau statistik.

```bash
cd frontend
npm install
node app.js
```

Akses melalui browser:
👉 `http://localhost:3000`

---

## 3️⃣ AI Engine (Python Detector)

Melakukan deteksi manusia dari kamera.

### Install dependency (sekali saja):

```bash
cd ai-engine
pip install opencv-python ultralytics requests python-dotenv numpy
```

### Jalankan AI Engine:

```bash
python main-detector.py
```

Jika berhasil berjalan, akan muncul jendela kamera.

---

## 📝 Konfigurasi `.env`

### File: `backend/.env`

```
PORT=5000
# MONGO_URI=mongodb://localhost:27017/cctv_db
```

### File: `ai-engine/.env`

```
API_URL=http://localhost:5000/api/update-visitor
CAMERA_INDEX=0
```

---

## ⚠️ Troubleshooting

### ❌ Kamera tidak bisa dibuka (`Error -2147024865`)

Solusi:

1. Tutup Zoom/Meet/Discord/OBS.
2. Ubah code:

   ```python
   cv2.VideoCapture(0)
   ```

   menjadi:

   ```python
   cv2.VideoCapture(0, cv2.CAP_DSHOW)
   ```

---

### ❌ Data tidak tampil di Frontend

1. Cek terminal backend — apakah ada data masuk?
2. Pastikan URL API di `.env` Python sesuai port backend.

---

## 📄 Lisensi

Proyek ini dibuat untuk kepentingan edukasi & research.

## 🤝 Kontribusi

Silakan fork project ini dan buat PR untuk fitur tambahan seperti:

* Deteksi masker
* Demografi (gender, usia)
* Multi-camera support

---
