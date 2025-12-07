require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const path = require('path');
const multer = require('multer'); 
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 5000; // Backend berjalan di port 5000

// --- MIDDLEWARE ---
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// =========================================================
// 1. KONFIGURASI PATH FOLDER (DISESUAIKAN DENGAN SCREENSHOT)
// =========================================================

// A. Folder Static Frontend (HTML/CSS/JS)
// Dari 'backend', kita naik satu level (..), lalu masuk ke 'frontend/public'
const FRONTEND_PATH = path.join(__dirname, '../frontend/public');
app.use(express.static(FRONTEND_PATH));

// B. Folder Penyimpanan Foto Wajah
// Dari 'backend', kita naik satu level (..), lalu masuk ke 'ai-engine/data_wajah'
const FACE_DATA_DIR = path.join(__dirname, '../ai-engine/data_wajah');

// Buat folder otomatis jika belum ada (Safe check)
if (!fs.existsSync(FACE_DATA_DIR)){
    fs.mkdirSync(FACE_DATA_DIR, { recursive: true });
    console.log(`📂 Membuat folder baru: ${FACE_DATA_DIR}`);
}

// =========================================================
// 2. KONFIGURASI DATABASE
// =========================================================
const mongoURI = process.env.MONGO_URI;

mongoose.connect(mongoURI, { dbName: 'I_MBG' }) 
    .then(() => {
        console.log('✅ Backend: Terkoneksi ke MongoDB Atlas');
        console.log('📂 Database Aktif: I_MBG');
    })
    .catch(err => console.error('❌ Backend Error:', err));

// =========================================================
// 3. MODEL DATA (SCHEMA)
// =========================================================

const EmployeeSchema = new mongoose.Schema({
    name: String,
    cups: Number,
    last_seen: Date,
    status: String
}, { collection: 'employee_performance' });
const Employee = mongoose.model('Employee', EmployeeSchema);

const LogSchema = new mongoose.Schema({
    timestamp: Date,
    event: String,
    detail: String
}, { collection: 'system_logs' });
const SystemLog = mongoose.model('SystemLog', LogSchema);

// =========================================================
// 4. KONFIGURASI MULTER (UPLOAD FOTO)
// =========================================================

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        // Simpan file ke folder ai-engine/data_wajah
        cb(null, FACE_DATA_DIR);
    },
    filename: (req, file, cb) => {
        // Format: NAMA_PEGAWAI.jpg (Huruf kapital, spasi jadi underscore)
        const name = req.body.name.replace(/\s+/g, '_').toUpperCase(); 
        const ext = path.extname(file.originalname);
        cb(null, `${name}${ext}`);
    }
});

const upload = multer({ storage: storage });

// =========================================================
// 5. API ROUTES
// =========================================================

// Route Utama: Tampilkan index.html dari folder frontend/public
app.get('/', (req, res) => {
    res.sendFile(path.join(FRONTEND_PATH, 'index.html'));
});

// Route Khusus Absensi: Tampilkan absensi.html
app.get('/absensi', (req, res) => {
    res.sendFile(path.join(FRONTEND_PATH, 'absensi.html'));
});

// --- API REGISTRASI ABSENSI (UPLOAD FOTO) ---
app.post('/api/attendance/register', upload.single('photo'), async (req, res) => {
    try {
        if (!req.file || !req.body.name) {
            return res.status(400).json({ error: "Nama dan Foto wajib diisi!" });
        }

        const employeeName = req.body.name.toUpperCase();
        const fileName = req.file.filename;

        // 1. Simpan Log
        const newLog = new SystemLog({
            timestamp: new Date(),
            event: "ATTENDANCE",
            detail: `Absensi Masuk: ${employeeName}`
        });
        await newLog.save();

        // 2. Update Data Pegawai
        await Employee.updateOne(
            { name: employeeName },
            { 
                $set: { last_seen: new Date(), status: "Active" },
                $setOnInsert: { cups: 0 }
            },
            { upsert: true }
        );

        console.log(`📸 [ABSENSI] Foto tersimpan di AI Engine: ${fileName}`);
        
        res.json({ 
            message: `✅ Absensi Berhasil! Foto ${employeeName} telah dikirim ke AI.`,
            filename: fileName
        });

    } catch (error) {
        console.error("❌ Error Absensi:", error);
        res.status(500).json({ error: error.message });
    }
});

// --- API DASHBOARD (DATA LAMA) ---
app.get('/api/dashboard/summary', async (req, res) => {
    try {
        const employees = await Employee.find().sort({ cups: -1 });
        const totalCups = employees.reduce((acc, curr) => acc + (curr.cups || 0), 0);
        const totalVisitors = await SystemLog.countDocuments({ event: "VISITOR" });
        const violations = await SystemLog.countDocuments({ event: "VIOLATION" });

        const prodLogs = await SystemLog.find({ event: "PRODUCTION" });
        let avgSpeed = 0;
        let totalDuration = 0;
        let countProd = 0;
        const durationRegex = /Durasi: (\d+)s/;

        prodLogs.forEach(log => {
            const match = log.detail.match(durationRegex);
            if (match) {
                totalDuration += parseInt(match[1]);
                countProd++;
            }
        });

        if (countProd > 0) avgSpeed = Math.round(totalDuration / countProd);

        const hourlyLogs = await SystemLog.find({
            event: { $in: ['VISITOR', 'PRODUCTION'] }
        }).select('timestamp event');

        const recentLogs = await SystemLog.find().sort({ timestamp: -1 }).limit(50);

        res.json({
            kpi: {
                total_cups: totalCups,
                total_visitors: totalVisitors,
                avg_speed: avgSpeed,
                violations: violations
            },
            leaderboard: employees,
            hourly_activity: hourlyLogs,
            recent_logs: recentLogs
        });

    } catch (error) {
        console.error("❌ ERROR API Dashboard:", error);
        res.status(500).json({ error: error.message });
    }
});

// =========================================================
// START SERVER
// =========================================================
app.listen(PORT, () => {
    console.log(`=============================================`);
    console.log(`🚀 SERVER BACKEND SIAP DI PORT ${PORT}`);
    console.log(`📂 Static Frontend: ${FRONTEND_PATH}`);
    console.log(`📂 Target Foto AI:  ${FACE_DATA_DIR}`);
    console.log(`=============================================`);
});