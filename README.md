# 👁️ Smart Cafe Monitor: Employee Performance & Visitor Counter

Sistem pemantauan cerdas berbasis AI yang terintegrasi (End-to-End). Proyek ini menggabungkan **Computer Vision (Python)** untuk analisis CCTV, **Backend API (Express.js)** untuk manajemen data real-time, dan **Frontend Dashboard** untuk visualisasi statistik.

Sistem ini tidak hanya menghitung pengunjung, tetapi juga **menilai kinerja pegawai** (jumlah kopi yang dibuat) dan **mendeteksi pelanggaran SOP** (seperti bermain HP saat jam kerja).

---

## ✨ Fitur Unggulan

### 1. 🤖 AI Surveillance & Analytics
* **Real-time Human Detection:** Menggunakan **YOLOv8** dan **ByteTrack** untuk pelacakan objek yang presisi.
* **Live Visitor Counter:** Menghitung pengunjung unik yang masuk dan memberikan sapaan suara (TTS) otomatis.
* **Face Recognition dengan "Hot Reload":** Mengenali wajah pegawai. Jika ada pegawai baru mendaftar foto via web, AI **otomatis memperbarui database wajah** tanpa perlu restart program.

### 2. ☕ Employee Performance Tracker (KPI)
* **Smart Coffee Tracking:** Menghitung berapa gelas kopi yang dibuat oleh spesifik pegawai.
* **Anti-Claim System:** Mencegah klaim palsu. Sistem memvalidasi durasi dan keberadaan pegawai di zona mesin kopi sebelum memberikan poin.
* **Leaderboard:** Menampilkan peringkat pegawai paling rajin secara real-time.

### 3. 📵 Violation Detection (SOP)
* **Phone Usage Detection:** AI mendeteksi jika pegawai bermain HP.
* **Alert System:** Jika penggunaan HP melebihi batas waktu (misal: 3 detik), sistem mencatat pelanggaran ke database dan memberikan peringatan suara.

### 4. 📸 Live Attendance System
* **Webcam Registration:** Pegawai melakukan absensi dan pendaftaran wajah langsung melalui browser (Laptop/HP).
* **Seamless Integration:** Foto yang diambil di web langsung dikirim ke AI Engine untuk dipelajari detik itu juga.

---

## 🗂️ Struktur Project

```text
/project-root
  ├── /backend                # Server (Express.js) & API
  │     ├── server.js         # Entry point server
  │     └── /Models           # Schema Database MongoDB
  │
  ├── /frontend               # Antarmuka Pengguna
  │     └── /public           # File statis (HTML, CSS, JS)
  │           ├── index.html  # Dashboard Utama
  │           └── absensi.html# Halaman Absensi Live Camera
  │
  └── /ai-engine              # Computer Vision (Python)
        ├── main.py           # Logika Utama (Looping & Deteksi)
        ├── helpers.py        # Helper (Database, Math, Face Loader)
        └── /data_wajah       # Folder penyimpanan foto wajah (Auto-generated)
🛠️ Persyaratan Sistem
Node.js (v16 ke atas)

Python (v3.10 atau v3.11)

MongoDB Atlas (Cloud Database)

Webcam (Internal Laptop atau USB Webcam)

Visual Studio Code (Recommended Editor)

🚀 Cara Menjalankan Project
Tips: Gunakan fitur "Split Terminal" di VS Code untuk menjalankan Backend dan AI secara bersamaan.

Langkah 1: Jalankan Backend Server
Backend berfungsi sebagai pusat data dan server file statis untuk frontend.

Bash

cd backend
npm install
node server.js
✅ Indikator Sukses: Terminal menampilkan: 🚀 SERVER BACKEND SIAP DI PORT 5000

Langkah 2: Akses Frontend (Web)
Setelah backend berjalan, buka browser (Chrome/Edge) dan akses URL berikut:

Dashboard Statistik: http://localhost:5000

Halaman Absensi (Daftar Wajah): http://localhost:5000/absensi.html

Catatan: Pastikan memberi izin akses kamera saat membuka halaman absensi.

Langkah 3: Jalankan AI Engine (Python)
AI akan menyalakan kamera CCTV/Webcam untuk mulai memantau.

Persiapan (Install Library):

Bash

cd ai-engine
pip install -r requirements.txt
Pastikan library cmake dan dlib terinstall dengan benar. Jika gagal install dlib, pastikan "Desktop Development with C++" sudah terinstall di Visual Studio Installer.

Menjalankan AI:

Bash

python main.py
✅ Indikator Sukses: Jendela kamera "CCTV AI (Modular)" akan muncul.

📝 Konfigurasi Database (.env)
Pastikan file .env ada di folder backend dan ai-engine.

Isi file .env (Contoh):

Cuplikan kode

PORT=5000
# Ganti dengan Connection String MongoDB milik Anda sendiri jika perlu
MONGO_URI=mongodb+srv://rendydatabase:anjayfree@cluster0.uavcqiz.mongodb.net/?appName=Cluster0
CAMERA_INDEX=0
CAMERA_INDEX=0 biasanya untuk webcam laptop. Ubah ke 1 jika menggunakan webcam eksternal USB.

🧪 Skenario Pengujian
Absensi: Buka http://localhost:5000/absensi.html, masukkan nama, dan ambil foto. Lihat terminal Python, AI akan mendeteksi "Perubahan data wajah" dan melakukan reload otomatis.

Deteksi Kopi: Bawa gelas ke area yang ditentukan (zona merah di layar), tahan selama 4-5 detik. Poin pegawai akan bertambah.

Pelanggaran HP: Pegang HP dan mainkan di depan kamera. AI akan mendeteksi objek "Cell Phone" dan memberikan peringatan jika terlalu lama.

🤝 Kontribusi & Lisensi
Proyek ini dibuat untuk kepentingan Kompetisi Inovasi AI & Riset Edukasi. Dilarang keras menyalin kode untuk tujuan komersial tanpa izin.

Dibuat dengan ❤️ dan Kopi ☕
