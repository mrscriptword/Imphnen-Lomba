const express = require('express');
const path = require('path');
const app = express();
const PORT = 3000; // Frontend jalan di port 3000

// Set folder 'public' sebagai folder statis (untuk HTML/CSS/JS)
app.use(express.static(path.join(__dirname, 'public')));

// Route utama dashboard
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
    console.log(`🌐 Frontend Dashboard running at http://localhost:${PORT}`);
});