require('dotenv').config();

const express  = require('express');
const cors     = require('cors');
const pool     = require('./db');

const patientsRouter = require('./patients');
const predictRouter  = require('./predict');

const app  = express();
const PORT = process.env.PORT || 3000;

// ================================================
// Middleware
// ================================================
app.use(cors());
app.use(express.json());

// Attach DB pool to every request
app.use((req, res, next) => {
  req.db = pool;
  next();
});

// ================================================
// Routes
// ================================================
app.use('/api/patients', patientsRouter);
app.use('/api/predict',  predictRouter);

// ================================================
// Health check
// ================================================
app.get('/health', async (req, res) => {
  try {
    await pool.query('SELECT 1');
    res.json({ status: 'ok', db: 'connected' });
  } catch (err) {
    res.status(500).json({ status: 'error', db: err.message });
  }
});

// ================================================
// 404
// ================================================
app.use((req, res) => {
  res.status(404).json({ error: `Route not found: ${req.method} ${req.path}` });
});

// ================================================
// Error handler
// ================================================
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: err.message });
});

// ================================================
// Start
// ================================================
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
  console.log(`Patients:     GET  http://localhost:${PORT}/api/patients`);
  console.log(`Predict:      POST http://localhost:${PORT}/api/predict/:patientId`);
  console.log(`Narrate:      POST http://localhost:${PORT}/api/predict/narrate/:patientId`);
  console.log(`Full:         POST http://localhost:${PORT}/api/predict/full/:patientId`);
});
