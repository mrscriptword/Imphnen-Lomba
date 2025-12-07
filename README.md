# 👁️ CCTV Smart Monitor & Visitor Counter

Sistem pemantauan cerdas berbasis AI untuk menditeksi aktivitas pegawai dan menghitung jumlah pengunjung. Proyek ini menggabungkan **Computer Vision (Python)** untuk deteksi, **Backend API (Express.js)** untuk manajemen data, dan **Frontend Dashboard** untuk visualisasi statistik. Proyek ini akan menditeksi berapa banyak kopi yang telah dibuat dalam sehari berdasarkan nama pegawai selain itu menditeksi pelanggaran pegawai seperti bermain hp. 

---

## ✨ Fitur Utama

* **Real-time Human Detection:** Menggunakan model AI YOLOv8 untuk mendeteksi manusia secara akurat.
* **Live Visitor Counter:** Menghitung jumlah orang yang tertangkap kamera saat ini (Live Count).
* **Daily Statistics:** Akumulasi jumlah pengunjung harian (reset otomatis setiap hari).
* **Web Dashboard:** Antarmuka visual untuk memantau trafik pengunjung dari browser.
* **Fast API Integration:** Komunikasi data realtime antara Python Engine dan Node.js Server.
* **Staff Accountability Tracker:** Memantau aktivitas di area kerja vital (seperti: Coffee Station). Sistem memvalidasi siapa yang sebenarnya berada di zona tersebut saat pesanan dibuat, **mencegah karyawan saling klaim pekerjaan (mengaku-ngaku)**.

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
pip install cmake
pip install -r requirements.txt
```

### Jalankan AI Engine:

```bash
python main-detector.py
```

Jika berhasil berjalan, akan muncul jendela kamera.
pada proses pertama kali akan muncul folder baru bernama data wajah pada folder ai-engine ini berfungsi untuk memasukan data pegawai
untuk menambahkan pegawai cukup tambahkan satu foto dengan nama file 
nama.jpg
contoh 
Rendy.jpg
---

## 📝 Konfigurasi `.env`

### File: `backend/.env`

```
PORT=5000
MONGO_URI=mongodb+srv://rendydatabase:anjayfree@cluster0.uavcqiz.mongodb.net/?appName=Cluster0
```
bisa gunakan contoh diatas untuk melakukan uji coba pada konfigurasi database
### File: `ai-engine/.env`

```
PORT=5000
MONGO_URI=mongodb+srv://rendydatabase:anjayfree@cluster0.uavcqiz.mongodb.net/?appName=Cluster0
```

---

## 📄 Lisensi

Proyek ini dibuat untuk kepentingan edukasi & research.

## 🤝 Kontribusi

