const mongoose = require('mongoose');

const ProductivitySchema = new mongoose.Schema({
    timestamp: { 
        type: Date, 
        default: Date.now 
    },
    employee_name: String,   // Misal: "Budi"
    task_name: String,       // Misal: "Membuat Kopi", "Membersihkan Meja"
    duration_seconds: Number, // Lama pengerjaan dalam detik
    status: String           // "Selesai", "Dibatalkan"
});

module.exports = mongoose.model('Productivity', ProductivitySchema);