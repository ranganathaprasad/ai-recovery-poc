const express = require('express');
const router  = express.Router();

// ================================================
// GET /api/patients
// Returns patient list with latest week summary
// Query params: ?procedure_type=Hip+Replacement
// ================================================
router.get('/', async (req, res) => {
  try {
    const { procedure_type } = req.query;

    const conditions = procedure_type
      ? `AND prl.procedure_type = $1`
      : '';

    const params = procedure_type ? [procedure_type] : [];

    const result = await req.db.query(`
      SELECT
        p.id                    AS patient_id,
        p.name,
        prl.age,
        p.gender,
        prl.procedure_type,
        prl.week_number         AS current_week,
        prl.rom_percent         AS latest_rom,
        prl.pain_score          AS latest_pain,
        prl.walking_steps       AS latest_steps,
        prl.exercise_adherence  AS latest_adherence,
        prl.program_start_date,
        prl.record_date         AS last_record_date
      FROM patients p
      JOIN patient_recovery_logs prl
        ON p.id = prl.patient_id
      WHERE prl.week_number = (
        SELECT MAX(week_number)
        FROM patient_recovery_logs
        WHERE patient_id = p.id
      )
      ${conditions}
      ORDER BY p.name ASC
    `, params);

    res.json({
      patients: result.rows,
      total:    result.rowCount
    });

  } catch (err) {
    console.error('GET /patients error:', err.message);
    res.status(500).json({ error: err.message });
  }
});


// ================================================
// GET /api/patients/:id
// Single patient with full week history
// ================================================
router.get('/:id', async (req, res) => {
  try {
    const { id } = req.params;

    const patient = await req.db.query(`
      SELECT id, name, age, gender
      FROM patients
      WHERE id = $1
    `, [id]);

    if (patient.rowCount === 0) {
      return res.status(404).json({ error: 'Patient not found' });
    }

    const history = await req.db.query(`
      SELECT
        week_number,
        record_date,
        procedure_type,
        rom_percent,
        pain_score,
        walking_steps,
        exercise_adherence,
        survey_completed,
        program_start_date
      FROM patient_recovery_logs
      WHERE patient_id = $1
      ORDER BY week_number ASC
    `, [id]);

    res.json({
      patient: patient.rows[0],
      history: history.rows
    });

  } catch (err) {
    console.error('GET /patients/:id error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
