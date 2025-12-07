require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 5000;

// --- MIDDLEWARE ---
app.use(cors());
app.use(express.json());

// --- KONEKSI DATABASE (PERBAIKAN UTAMA DISINI) ---
const mongoURI = process.env.MONGO_URI;

// [FIX] Tambahkan { dbName: 'I_MBG' } agar backend tidak nyasar ke database 'test'
mongoose.connect(mongoURI, { dbName: 'I_MBG' }) 
    .then(() => {
        console.log('✅ Backend: Terkoneksi ke MongoDB Atlas');
        console.log('📂 Database Aktif: I_MBG'); // Konfirmasi visual di terminal
    })
    .catch(err => console.error('❌ Backend Error:', err));

// =========================================================
// DEFINISI SCHEMA (MODEL DATA)
// =========================================================

// 1. Schema Pegawai
const EmployeeSchema = new mongoose.Schema({
    name: String,
    cups: Number,
    last_seen: Date,
    status: String
}, { collection: 'employee_performance' });
const Employee = mongoose.model('Employee', EmployeeSchema);

// 2. Schema Log Sistem
const LogSchema = new mongoose.Schema({
    timestamp: Date,
    event: String,
    detail: String
}, { collection: 'system_logs' });
const SystemLog = mongoose.model('SystemLog', LogSchema);

// =========================================================
// API ROUTES
// =========================================================

app.get('/', (req, res) => {
    res.send('☕ Smart Cafe API is Running (All Time Mode)...');
});

// --- API DASHBOARD UTAMA (MODE: BACA SEMUA SEJARAH DATA) ---
app.get('/api/dashboard/summary', async (req, res) => {
    try {
        console.log("\n🔄 [REQ] Frontend meminta data dashboard...");

        // --- 1. AMBIL DATA DARI MONGO (TANPA FILTER TANGGAL) ---
        
        // A. KPI: Total Cups (Akumulasi semua waktu)
        const employees = await Employee.find().sort({ cups: -1 });
        const totalCups = employees.reduce((acc, curr) => acc + (curr.cups || 0), 0);

        // B. KPI: Total Visitors (SEMUA DATA)
        const totalVisitors = await SystemLog.countDocuments({
            event: "VISITOR"
        });

        // C. KPI: Pelanggaran (SEMUA DATA)
        const violations = await SystemLog.countDocuments({
            event: "VIOLATION"
        });

        // D. KPI: Avg Speed (Rata-rata durasi pembuatan kopi - SEMUA DATA)
        const prodLogs = await SystemLog.find({
            event: "PRODUCTION"
        });

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

        if (countProd > 0) {
            avgSpeed = Math.round(totalDuration / countProd);
        }

        // --- 2. DATA UNTUK GRAFIK (SEMUA DATA) ---
        
        // Ambil log aktivitas untuk grafik
        const hourlyLogs = await SystemLog.find({
            event: { $in: ['VISITOR', 'PRODUCTION'] }
        }).select('timestamp event');

        // Ambil 50 log terakhir untuk Tabel Bawah
        const recentLogs = await SystemLog.find()
            .sort({ timestamp: -1 }) // Paling baru diatas
            .limit(50);

        // --- 3. DEBUG LOGGING ---
        console.log(`   📊 Stats: ${totalVisitors} Visitors | ${totalCups} Cups | ${violations} Violations`);
        if (totalVisitors > 0) {
             console.log("   ✅ Data ditemukan (termasuk data lama).");
        } else {
             console.log("   ⚠️ Data masih 0. Pastikan database 'I_MBG' -> 'system_logs' ada isinya.");
        }

        // --- 4. KIRIM KE FRONTEND ---
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
        console.error("❌ ERROR di API Dashboard:", error);
        res.status(500).json({ error: error.message });
    }
});

// Jalankan Server
app.listen(PORT, () => {
    console.log(`=============================================`);
    console.log(`🚀 SERVER BACKEND SIAP DI PORT ${PORT}`);
    console.log(`📡 Mode: ALL TIME DATA (Database forced: I_MBG)`);
    console.log(`=============================================`);
});