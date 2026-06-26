const express        = require('express');
const router         = express.Router();
const { runPython }  = require('./python');
const { sendAlertEmail } = require('./mailer');


// ================================================
// Helper: fetch last 2 weeks from DB and build
// the input object predict.py expects
// ================================================
async function buildPredictInput(patientId, db) {
  const result = await db.query(`
    SELECT
      prl.*,
      p.name,
      prl.age,
      p.gender
    FROM patient_recovery_logs prl
    JOIN patients p ON p.id = prl.patient_id
    WHERE prl.patient_id = $1
    ORDER BY prl.week_number DESC
    LIMIT 2
  `, [patientId]);

  if (result.rowCount === 0) {
    throw new Error(`No recovery data found for patient ${patientId}`);
  }

  const current = result.rows[0];           // latest week
  const prev    = result.rows[1] || null;   // previous week (null if week 1)

  return {
    patient_id:         parseInt(patientId),
    program_id:         current.program_id,
    procedure_type:     current.procedure_type,
    current_week:       current.week_number,
    age:                current.age,
    gender:             current.gender,
    rom_percent:        parseFloat(current.rom_percent),
    pain_score:         parseFloat(current.pain_score),
    walking_steps:      parseInt(current.walking_steps),
    exercise_adherence: parseFloat(current.exercise_adherence),
    survey_completed:   current.survey_completed ? 1 : 0,
    prev_rom:           prev ? parseFloat(prev.rom_percent)   : parseFloat(current.rom_percent),
    prev_pain:          prev ? parseFloat(prev.pain_score)    : parseFloat(current.pain_score),
    prev_steps:         prev ? parseInt(prev.walking_steps)   : parseInt(current.walking_steps)
  };
}


// ================================================
// Helper: save prediction to DB
// ================================================
async function savePrediction(db, input, prediction, narrative, agent) {
  await db.query(`
    INSERT INTO prediction_logs (
      patient_id,
      program_id,
      week_number,
      predicted_rom,
      predicted_pain,
      predicted_steps,
      rom_confidence,
      pain_confidence,
      steps_confidence,
      agent_decision,
      agent_reasoning,
      narrative
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
  `, [
    input.patient_id,
    input.program_id,
    input.current_week,
    prediction.forecast.rom.prediction,
    prediction.forecast.pain.prediction,
    prediction.forecast.steps.prediction,
    prediction.forecast.rom.confidence,
    prediction.forecast.pain.confidence,
    prediction.forecast.steps.confidence,
    agent?.decision    || null,
    agent?.reasoning   || null,
    narrative?.narrative || null
  ]);
}


// ================================================
// Helper: save alert to DB
// ================================================
async function saveAlert(db, input, agent) {
  await db.query(`
    INSERT INTO ai_alerts (
      patient_id,
      week_number,
      alert_reason,
      email_subject,
      email_sent
    ) VALUES ($1,$2,$3,$4,$5)
  `, [
    input.patient_id,
    input.current_week,
    agent.alert_reason,
    agent.email_subject,
    false
  ]);
}


// ================================================
// POST /api/predict/:patientId
// Prediction only — fastest response
// ================================================
router.post('/:patientId', async (req, res) => {
  try {
    const input = await buildPredictInput(req.params.patientId, req.db);

    const prediction = await runPython('predict.py', input);

    if (prediction.error) {
      return res.status(400).json({
        error:   prediction.error,
        details: prediction.details
      });
    }

    // Save to DB (no narrative or agent yet)
    await savePrediction(req.db, input, prediction, null, null);

    res.json({ prediction });

  } catch (err) {
    console.error('POST /predict error:', err.message);
    res.status(500).json({ error: err.message });
  }
});


// ================================================
// POST /api/predict-narrate/:patientId
// Prediction + Ollama clinical narrative
// ================================================
router.post('/narrate/:patientId', async (req, res) => {
  try {
    const input = await buildPredictInput(req.params.patientId, req.db);

    const prediction = await runPython('predict.py', input);

    if (prediction.error) {
      return res.status(400).json({ error: prediction.error });
    }

    const narrative = await runPython('narrate.py', prediction);

    await savePrediction(req.db, input, prediction, narrative, null);

    res.json({ prediction, narrative });

  } catch (err) {
    console.error('POST /predict-narrate error:', err.message);
    res.status(500).json({ error: err.message });
  }
});


// ================================================
// POST /api/predict-full/:patientId
// Prediction + narrative + agent alert decision
// Sends email + writes alert to DB if ALERT
// ================================================
router.post('/full/:patientId', async (req, res) => {
  try {
    const input = await buildPredictInput(req.params.patientId, req.db);

    // Run pipeline sequentially
    const prediction = await runPython('predict.py', input);

    if (prediction.error) {
      return res.status(400).json({ error: prediction.error });
    }

    const narrative = await runPython('narrate.py', prediction);
    const agent     = await runPython('agent.py',   prediction);

    // Save prediction to DB
    await savePrediction(req.db, input, prediction, narrative, agent);

    // Handle ALERT
    if (agent.decision === 'ALERT') {
      agent.email_sent      = true;
      agent.email_message_id = Date.now();
      
      // await saveAlert(req.db, input, agent);

      // try {
      //   const messageId = await sendAlertEmail(agent, input);

      //   // Mark email as sent
      //   await req.db.query(`
      //     UPDATE ai_alerts
      //     SET email_sent = true, email_sent_at = NOW()
      //     WHERE patient_id = $1
      //       AND week_number = $2
      //       AND email_sent = false
      //   `, [input.patient_id, input.current_week]);

      //   agent.email_sent      = true;
      //   agent.email_message_id = messageId;

      // } catch (mailErr) {
      //   // Don't fail the whole request if email fails
      //   console.error('Email send failed:', mailErr.message);
      //   agent.email_sent  = false;
      //   agent.email_error = mailErr.message;
      // }
    }

    res.json({ prediction, narrative, agent });

  } catch (err) {
    console.error('POST /predict-full error:', err.message);
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
