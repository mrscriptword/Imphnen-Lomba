# Project Setup Guide

Dokumentasi ini berisi langkah-langkah lengkap untuk menjalankan seluruh bagian dalam proyek yang terdiri dari **Backend**, **Frontend**, dan **AI Engine**.

---

## 🗂️ Struktur Project
```
/backend
  ├── server.js
  └── ...
/frontend
  ├── app.js
  └── ...
/ai-engine
  ├── main-detector.py
  ├── requirements.txt
  └── ...
```

---

# 🚀 Cara Menjalankan Project

## 1️⃣ Backend (Node.js + Express)

### **Masuk ke folder backend**
```bash
cd backend
```

### **Install dependencies**
```bash
npm install dotenv
```

### **Menjalankan server**
```bash
node server.js
```

Jika menggunakan nodemon:
```bash
nodemon server.js
```

---

## 2️⃣ Frontend (Node.js + Express)

### **Masuk ke folder frontend**
```bash
cd frontend
```

### **Inisialisasi project (jika belum ada package.json)**
```bash
npm init -y
```

### **Install dependencies**
```bash
npm install express mongoose cors
```

### **Menjalankan aplikasi**
```bash
node app.js
```

---

## 3️⃣ AI Engine (Python)

### **Masuk ke folder ai-engine**
```bash
cd ai-engine
```

### **Install CMake (dibutuhkan untuk beberapa library)**
```bash
pip install cmake
```

### **Install semua library Python yang diperlukan**
```bash
pip install -r requirements.txt
```

### **Menjalankan AI Engine**
```bash
python main-detector.py
```

---

## 📝 Catatan Penting

- Pastikan Python versi **3.10+** sudah terpasang.
- Pastikan Node.js versi **16+**.
- Untuk AI Engine yang memerlukan akses kamera, pastikan perangkat mendukung.
- Untuk koneksi database MongoDB, file `.env` wajib diisi dengan konfigurasi yang benar (misalnya `MONGO_URI`).

---

## 📄 Lisensi
Proyek ini hanya untuk kebutuhan internal dan pengembangan. Silakan modifikasi sesuai kebutuhan Anda.

---

## 🤝 Kontribusi
Pull request dan perbaikan sangat diterima!  
Silakan buat branch baru sebelum melakukan perubahan besar.

---

# 💬 Kontak
Jika terdapat bug atau butuh bantuan lebih lanjut, silakan hubungi developer.

