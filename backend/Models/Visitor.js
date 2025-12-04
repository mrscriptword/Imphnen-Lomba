const mongoose = require('mongoose');

const VisitorSchema = new mongoose.Schema({
    timestamp: { 
        type: Date, 
        default: Date.now 
    },
    camera_id: String,       // Misal: "CAM_DEPAN"
    total_in: Number,        // Akumulasi orang masuk hari ini
    total_out: Number,       // Akumulasi orang keluar
    current_occupancy: Number // Jumlah orang saat ini di ruangan
});

module.exports = mongoose.model('Visitor', VisitorSchema);