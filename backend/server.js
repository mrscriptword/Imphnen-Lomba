require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');

// Import Model yang sudah kita buat
const Visitor = require('./Models/Visitor.js');
const Productivity = require('./Models/Productivity.js');

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors()); // Wajib, agar Frontend (Port 3000) bisa akses
app.use(express.json()); // Agar bisa baca data JSON dari Python

// Koneksi Database
mongoose.connect(process.env.MONGO_URI)
    .then(() => console.log('✅ Connected to MongoDB Atlas'))
    .catch(err => console.error('❌ Connection Error:', err));


// ==========================================
// 1. API UNTUK PENGUNJUNG (VISITOR)
// ==========================================

// [POST] Python mengirim data pengunjung terbaru
// Endpoint: http://localhost:5000/api/visitor
app.post('/api/visitor', async (req, res) => {
    try {
        const newData = new Visitor(req.body);
        await newData.save();
        res.status(201).json({ message: "Data Visitor tersimpan", data: newData });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// [GET] Frontend mengambil data pengunjung TERBARU (Real-time)
// Endpoint: http://localhost:5000/api/visitor/latest
app.get('/api/visitor/latest', async (req, res) => {
    try {
        // Ambil 1 data paling akhir (sort timestamp descending)
        const latestData = await Visitor.findOne().sort({ timestamp: -1 });
        
        // Handle jika database kosong
        if (!latestData) {
            return res.json({ current_occupancy: 0, total_in: 0, total_out: 0 });
        }
        res.json(latestData);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});


// ==========================================
// 2. API UNTUK PRODUKTIVITAS PEGAWAI
// ==========================================

// [POST] Python mengirim data pegawai selesai kerja
// Endpoint: http://localhost:5000/api/productivity
app.post('/api/productivity', async (req, res) => {
    try {
        const newTask = new Productivity(req.body);
        await newTask.save();
        res.status(201).json({ message: "Data Produktivitas tersimpan", data: newTask });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// [GET] Frontend mengambil list pekerjaan hari ini (Untuk Grafik)
// Endpoint: http://localhost:5000/api/productivity
app.get('/api/productivity', async (req, res) => {
    try {
        // Ambil semua data, urutkan dari yang terbaru
        const tasks = await Productivity.find().sort({ timestamp: -1 }).limit(50);
        res.json(tasks);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// [GET] Frontend mengambil rangkuman performa (Total kopi per pegawai)
// Endpoint: http://localhost:5000/api/productivity/summary
app.get('/api/productivity/summary', async (req, res) => {
    try {
        // Aggregation: Group by employee_name dan hitung jumlah task
        const summary = await Productivity.aggregate([
            {
                $group: {
                    _id: "$employee_name", // Kelompokkan berdasar nama
                    total_tasks: { $sum: 1 }, // Hitung jumlah tugas
                    avg_duration: { $avg: "$duration_seconds" } // Rata-rata kecepatan
                }
            }
        ]);
        res.json(summary);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});
app.get('/api/visitor', async (req, res) => {
    try {
        // Ambil semua data, urutkan dari yang terbaru
        const allData = await Visitor.find().sort({ timestamp: -1 });
        res.json(allData);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});
// Start Server
app.listen(PORT, () => {
    console.log(`🚀 Backend Server siap di http://localhost:${PORT}`);
});