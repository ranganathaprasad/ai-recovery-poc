const { Pool } = require('pg');

const pool = new Pool({
  host:     process.env.DB_HOST,
  port:     parseInt(process.env.DB_PORT),
  user:     process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  max:      10,
  idleTimeoutMillis: 30000
});

pool.on('error', (err) => {
  console.error('Unexpected DB error:', err.message);
});

module.exports = pool;
