require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 5000;

// --- MIDDLEWARE ---
app.use(cors());
app.use(express.json());

// --- KONEKSI DATABASE ---
const mongoURI = process.env.MONGO_URI;

mongoose.connect(mongoURI)
    .then(() => console.log('✅ Backend: Terkoneksi ke MongoDB Atlas'))
    .catch(err => console.error('❌ Backend Error:', err));

// --- DEFINISI SCHEMA (MODEL DATA) ---
// Kita definisikan di sini agar satu file langsung jalan (tanpa perlu folder models terpisah)

// 1. Schema Pegawai (Untuk Leaderboard)
const EmployeeSchema = new mongoose.Schema({
    name: String,
    cups: Number,
    last_seen: Date,
    status: String
}, { collection: 'employee_performance' });
const Employee = mongoose.model('Employee', EmployeeSchema);

// 2. Schema Log Sistem (Untuk Audit & Grafik Aktivitas)
const LogSchema = new mongoose.Schema({
    timestamp: Date,
    event: String,
    detail: String
}, { collection: 'system_logs' });
const SystemLog = mongoose.model('SystemLog', LogSchema);

// 3. Schema Visitor (Untuk Data Statistik Pengunjung)
const VisitorSchema = new mongoose.Schema({
    timestamp: Date,
    camera_id: String,
    total_in: Number,
    current_occupancy: Number
}, { collection: 'visitor_logs' });
const Visitor = mongoose.model('Visitor', VisitorSchema);


// =========================================================
// API ROUTES
// =========================================================

// Test Route
app.get('/', (req, res) => {
    res.send('☕ Smart Cafe API Server is Running...');
});

// --- API KHUSUS DASHBOARD (AGGREGATION) ---
// Ini adalah "Otak" yang memberi makan frontend Glassmorphism
app.get('/api/dashboard/summary', async (req, res) => {
    try {
        // Tentukan rentang waktu "Hari Ini" (Mulai jam 00:00)
        const todayStart = new Date();
        todayStart.setHours(0, 0, 0, 0);

        // --- 1. HITUNG KPI ---
        
        // A. Total Cups (Semua Waktu)
        const employees = await Employee.find().sort({ cups: -1 }); // Sekalian buat leaderboard
        const totalCups = employees.reduce((acc, curr) => acc + (curr.cups || 0), 0);

        // B. Total Visitor (Hari Ini)
        // Kita hitung berapa kali event "VISITOR" tercatat di logs hari ini
        // (Lebih akurat daripada total_in kumulatif jika server restart)
        const totalVisitors = await SystemLog.countDocuments({
            event: "VISITOR",
            timestamp: { $gte: todayStart }
        });

        // C. Avg Speed (Rata-rata durasi pembuatan kopi hari ini)
        const prodLogs = await SystemLog.find({
            event: "PRODUCTION",
            timestamp: { $gte: todayStart }
        });

        let avgSpeed = 0;
        let totalDuration = 0;
        let countProd = 0;
        const durationRegex = /Durasi: (\d+)s/; // Regex ambil angka dari teks "Durasi: 45s"

        prodLogs.forEach(log => {
            const match = log.detail.match(durationRegex);
            if (match) {
                totalDuration += parseInt(match[1]);
                countProd++;
            }
        });
        if (countProd > 0) avgSpeed = Math.round(totalDuration / countProd);

        // D. Pelanggaran (Hari Ini)
        const violations = await SystemLog.countDocuments({
            event: "VIOLATION",
            timestamp: { $gte: todayStart }
        });

        // --- 2. DATA GRAFIK AKTIVITAS ---
        // Ambil log hari ini untuk diplot jam-nya di Frontend
        const hourlyLogs = await SystemLog.find({
            timestamp: { $gte: todayStart },
            event: { $in: ['VISITOR', 'PRODUCTION'] } // Hanya ambil event penting
        }).select('timestamp event');

        // --- 3. RECENT LOGS (TABEL) ---
        const recentLogs = await SystemLog.find()
            .sort({ timestamp: -1 })
            .limit(50);

        // --- KIRIM JSON KE FRONTEND ---
        res.json({
            kpi: {
                total_cups: totalCups,
                total_visitors: totalVisitors,
                avg_speed: avgSpeed,
                violations: violations
            },
            leaderboard: employees,     // Untuk Pie Chart
            hourly_activity: hourlyLogs, // Untuk Bar/Line Chart
            recent_logs: recentLogs     // Untuk Tabel Bawah
        });

    } catch (error) {
        console.error("Dashboard Error:", error);
        res.status(500).json({ error: error.message });
    }
});

// --- API TAMBAHAN (Opsional/Legacy) ---
// Jika Frontend butuh data spesifik visitor
app.get('/api/visitor/latest', async (req, res) => {
    try {
        const data = await Visitor.findOne().sort({ timestamp: -1 });
        res.json(data || {});
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// START SERVER
app.listen(PORT, () => {
    console.log(`🚀 Server Backend berjalan di http://localhost:${PORT}`);
});