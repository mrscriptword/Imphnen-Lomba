# 👁️ Smart Cafe Monitor — Employee Performance & Visitor Counter

Sistem pemantauan cerdas berbasis AI (End-to-End) untuk kafe:
menggunakan **Computer Vision (Python)** untuk analisis CCTV, **Backend (Express.js)** untuk manajemen data realtime, dan **Frontend** untuk dashboard visualisasi.
Fitur utama: menghitung pengunjung, menilai kinerja pegawai (KPI: jumlah kopi yang dibuat), dan mendeteksi pelanggaran SOP (mis. bermain HP saat bekerja).

---

## ✨ Fitur Unggulan

* **Real-time Human Detection** (YOLOv8 + ByteTrack) untuk pelacakan presisi.
* **Live Visitor Counter**: hitung pengunjung unik dan beri sapaan TTS otomatis.
* **Face Recognition dengan Hot-Reload**: pendaftaran wajah lewat web otomatis memperbarui database wajah tanpa restart AI.
* **Employee Performance Tracker (KPI)**: menghitung pembuatan kopi per pegawai, validasi durasi di zona mesin kopi, dan leaderboard real-time.
* **Violation Detection (SOP)**: deteksi penggunaan HP dan catat pelanggaran kalau melebihi ambang waktu.
* **Live Attendance (Absensi via Webcam)**: pegawai daftar dan absen lewat browser (foto diupload ke AI untuk dipelajari langsung).

---

## 🗂️ Struktur Project (Contoh)

```
/project-root
  ├── backend/                # Server Express.js & API
  │     ├── server.js
  │     └── /models           # Schema MongoDB (Mongoose)
  │
  ├── frontend/               # Static files + UI
  │     └── public/
  │           ├── index.html
  │           └── absensi.html
  │
  └── ai-engine/              # Computer Vision (Python)
        ├── main.py
        ├── helpers.py
        └── /data_wajah       # Foto wajah (auto-generated)
```

---

## 🛠️ Persyaratan Sistem

* Node.js v16+ (direkomendasikan v18+)
* Python 3.10 / 3.11
* MongoDB Atlas (atau MongoDB yang dapat diakses)
* Webcam (internal atau USB)
* Visual Studio Code (direkomendasikan)

---

## 🚀 Cara Menjalankan (Local)

> Pastikan Anda membuka dua terminal atau split terminal: satu untuk `backend`, satu untuk `ai-engine`.

### 1) Setup Backend

```bash
cd backend
npm install
npm install multer
npm install dotenv
# pastikan file .env ada (lihat contoh di bawah)
node server.js
```

**Indikator sukses:** `🚀 SERVER BACKEND SIAP DI PORT 5000` (atau port sesuai .env)

### 2) Akses Frontend

Buka browser:

* Dashboard Statistik: `http://localhost:5000/`
* Halaman Absensi (Daftar Wajah): `http://localhost:5000/absensi.html`

Pastikan browser diberi izin kamera saat membuka halaman absensi.

### 3) Jalankan AI Engine (Python)

```bash
cd ai-engine
pip install -r requirements.txt
python main.py
```

**Indikator sukses:** Jendela kamera akan muncul berjudul `CCTV AI (Modular)` (atau log yang menunjukkan kamera aktif dan model ter-load).

---

## 🔧 Contoh Isi `.env`

Letakkan `.env` di folder `backend` dan `ai-engine` (sesuaikan kalau Anda menyimpan satu file pusat).

```
# backend/.env (contoh)
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/mydatabase?retryWrites=true&w=majority
PORT=5000

# ai-engine/.env (contoh)
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/mydatabase?retryWrites=true&w=majority
PORT=5000
```

> Ganti `<username>`, `<password>`, dan `MODEL_PATH` sesuai konfig Anda.

---

## 🧪 Alur Fitur Penting (singkat)

* **Absensi / Pendaftaran Wajah:** pengguna mengisi nama di `absensi.html` dan mengambil foto. Frontend mengupload gambar ke endpoint backend. Backend menyimpan file dan mengirim sinyal ke AI (atau AI memonitor folder) -> AI memuat wajah baru tanpa restart (hot-reload).
* **Deteksi Kopi / KPI:** AI memantau zona mesin kopi (area yang ditandai). Jika pegawai terlihat berada di zona mesin dengan gelas selama ambang waktu (mis. ≥ 4 detik), sistem menambah poin otomatis dengan validasi kehadiran wajah.
* **Pelanggaran HP:** deteksi objek `cell phone`. Jika durasi penggunaan melebihi threshold (mis. 3 detik), AI mencatat pelanggaran di DB dan mengeluarkan peringatan suara.

---

## ⚙️ Konfigurasi Zona & Threshold

* Lokasi zona (mis. area mesin kopi) dikonfig di `ai-engine` (biasanya berupa koordinat bounding box atau persentase frame).
* Threshold durasi (mis. 3 detik untuk HP, 4 detik untuk pembuatan kopi) dikonfig di `config.py` atau file konfigurasi sejenis di `ai-engine`.


## 🔍 Troubleshooting Umum

**1. Gagal install `dlib` pada Windows**

* Pastikan Anda menginstall *Desktop Development with C++* lewat Visual Studio Installer.
* Alternatif: gunakan wheel prebuilt untuk versi Python dan arsitektur Anda, atau jalankan pada WSL (Windows Subsystem for Linux).

**2. `ModuleNotFoundError: No module named 'dotenv'`**

* Jalankan `pip install python-dotenv` di environment yang aktif.

**3. OpenCV (`cv2`) tidak ter-import di Colab**

* Colab butuh instalasi `opencv-python-headless` dan mungkin konfigurasi display. Untuk realtime webcam lokal, Colab bukan lingkungan yang cocok.

**4. Remote contains work that you do not have locally (git push ditolak)**

* Gunakan `git pull --rebase origin main` lalu `git push`.

**5. Kamera tidak terbuka**

* Pastikan `CAMERA_INDEX` benar (0 internal, 1 USB), dan aplikasi lain tidak memegang akses kamera.

---

## ✅ Pengujian (Skenario)

1. Buka `http://localhost:5000/absensi.html`, ambil foto baru. Periksa log AI: harus muncul log `Perubahan data wajah detected -> reloading face DB`.
2. Lakukan simulasi pembuatan kopi di zona mesin (tampilkan gelas di zona) selama ≥ 4 detik. Periksa leaderboard di dashboard.
3. Pegang HP di depan kamera selama >3 detik. Periksa apakah pelanggaran tercatat di DB dan notifikasi suara keluar.

---

Terima kasih — dibuat dengan rasa syukur  dan segelas kopi ☕
