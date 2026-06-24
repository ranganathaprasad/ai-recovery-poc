# AI Recovery POC — API Contract

Node calls Python scripts via `child_process.spawn`.
All Python scripts read from **stdin**, write to **stdout**.

---

## Python Pipeline

```
Node → predict.py (stdin) → stdout → narrate.py (stdin) → stdout → agent.py (stdin) → stdout → Node
```

Node runs these as 3 separate spawns, piping output of each as input to next.
Or run sequentially and accumulate results.

---

## 1. predict.py

### Input (JSON via stdin)
```json
{
  "patient_id": 1,
  "procedure_type": "Hip Replacement",
  "current_week": 3,
  "age": 29,
  "gender": "Female",
  "rom_percent": 42.05,
  "pain_score": 6,
  "walking_steps": 1613,
  "exercise_adherence": 46.0,
  "survey_completed": 1,
  "prev_rom": 41.45,
  "prev_pain": 6,
  "prev_steps": 1274
}
```

Valid procedure_type values: `"Hip Replacement"`, `"Knee Replacement"`, `"Shoulder Surgery"`, `"ACL Surgery"`

### Output (JSON via stdout)
```json
{
  "input_summary": {
    "patient_id": 1,
    "procedure_type": "Hip Replacement",
    "current_week": 3,
    "age": 29,
    "gender": "Female"
  },
  "forecast": {
    "rom":   { "prediction": 46.35, "range": [42.1, 50.6], "confidence": 78.5, "label": "Medium", "unit": "%" },
    "pain":  { "prediction": 5.2,   "range": [4.1, 6.3],   "confidence": 81.0, "label": "High",   "unit": "/10" },
    "steps": { "prediction": 1880,  "range": [1500, 2260],  "confidence": 72.3, "label": "Medium", "unit": "steps/day" }
  },
  "insight": "Recovery is progressing well — mobility is improving and pain is decreasing.",
  "drivers": {
    "positive": [
      { "key": "mobility",   "label": "Mobility improving (ROM: 42.1, Δ +0.6)" },
      { "key": "pain",       "label": "Pain reducing (Score: 6.0, Δ 0.0)" }
    ],
    "concern": [
      { "key": "adherence",  "label": "Low exercise adherence (46%)" }
    ]
  },
  "cohort": {
    "similar_patients_count": 10,
    "averages": { "rom": 44.2, "pain": 5.8, "steps": 1720 },
    "comparison": {
      "rom": "Above average",
      "pain": "Low and improving",
      "activity": "Above average"
    }
  },
  "severity": {
    "is_severe": false,
    "flags": ["Low exercise adherence (46%)"]
  },
  "model_meta": {
    "rom_test_mae": 3.12,
    "pain_test_mae": 0.48,
    "steps_test_mae": 187.4
  }
}
```

### Error output
```json
{ "error": "Validation failed", "details": ["pain_score out of range: 11 (expected 0-10)"] }
```

---

## 2. narrate.py

### Input: full predict.py output (JSON via stdin)

### Output
```json
{
  "narrative": "This patient is showing encouraging recovery signs at week 3 post Hip Replacement, with improving mobility and reducing pain levels. However, exercise adherence at 46% remains a concern and may limit long-term ROM gains. It is recommended to contact the patient to reinforce the importance of the home exercise program.",
  "source": "ollama",
  "model": "llama3.2"
}
```

Fallback if Ollama is down:
```json
{
  "narrative": "Recovery monitoring in progress.",
  "source": "fallback",
  "warning": "Cannot reach Ollama at http://localhost:11434..."
}
```

---

## 3. agent.py

### Input: full predict.py output (JSON via stdin)

### Output
```json
{
  "reasoning": "Week 3 Hip Replacement patient. Pain is 6/10, predicted to reduce to 5.2. ROM is above cohort average. Only concern is exercise adherence at 46%, which is borderline in week 3. Trend is positive overall. No immediate alert warranted — monitoring recommended.",
  "decision": "MONITOR",
  "confidence": "High",
  "alert_reason": null,
  "email_subject": null,
  "email_body": null,
  "recommended_action": "Flag for next scheduled review",
  "source": "llm_agent"
}
```

Decision values: `"ALERT"` | `"MONITOR"` | `"OK"`

When decision is `"ALERT"`:
```json
{
  "reasoning": "...",
  "decision": "ALERT",
  "confidence": "High",
  "alert_reason": "Pain score 9/10, below cohort ROM by 30%, adherence 22% in week 5",
  "email_subject": "[Alert] Patient recovery concern - Week 5",
  "email_body": "Patient X shows critical recovery signals in week 5 post Knee Replacement. Pain remains at 9/10 and mobility is 30% below similar patients. Immediate clinician review is recommended.",
  "recommended_action": "Schedule review call within 24 hours",
  "source": "llm_agent"
}
```

---

## Node API Endpoints

### GET /api/patients
Returns patient list from DB.

Query params: `?page=1&limit=20&procedure_type=Hip+Replacement`

Response:
```json
{
  "patients": [
    {
      "patient_id": 1,
      "name": "Jane Doe",
      "procedure_type": "Hip Replacement",
      "current_week": 3,
      "latest_rom": 42.05,
      "latest_pain": 6,
      "latest_steps": 1613,
      "program_start_date": "2024-03-02"
    }
  ],
  "total": 150
}
```

### POST /api/predict/:patientId
Triggers full pipeline: predict → narrate → agent.

Node fetches latest week data from `patient_recovery_logs`, calls Python, returns combined result.

Response:
```json
{
  "prediction": { ...predict.py output... },
  "narrative": { ...narrate.py output... },
  "agent": { ...agent.py output... }
}
```

On agent ALERT: Node also writes to `alerts` table and sends email via Nodemailer.

---

## DB Queries Node needs

### Get patient list with latest week
```sql
SELECT
  p.id AS patient_id,
  p.name,
  prl.procedure_type,
  prl.week_number AS current_week,
  prl.rom_percent AS latest_rom,
  prl.pain_score AS latest_pain,
  prl.walking_steps AS latest_steps,
  prl.program_start_date
FROM patients p
JOIN patient_recovery_logs prl
  ON p.id = prl.patient_id
WHERE prl.week_number = (
  SELECT MAX(week_number)
  FROM patient_recovery_logs
  WHERE patient_id = p.id
)
ORDER BY p.name;
```

### Get latest 2 weeks for a patient (for prev_ values)
```sql
SELECT *
FROM patient_recovery_logs
WHERE patient_id = $1
ORDER BY week_number DESC
LIMIT 2;
```

### New tables to create

```sql
CREATE TABLE public.patient_recovery_logs (
	id serial4 NOT NULL,
	patient_id int4 NOT NULL,
	procedure_type varchar(100) NOT NULL,
	age int4 NULL,
	gender varchar(10) NULL,
	program_start_date date NOT NULL,
	program_end_date date NULL,
	is_program_incomplete bool DEFAULT false NULL,
	week_number int4 NOT NULL,
	record_date date NOT NULL,
	rom_percent float8 NULL,
	pain_score int4 NULL,
	walking_steps int4 NULL,
	exercise_adherence float8 NULL,
	survey_completed bool NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	program_id int4 NOT NULL,
	CONSTRAINT chk_adherence CHECK (((exercise_adherence >= (0)::double precision) AND (exercise_adherence <= (100)::double precision))),
	CONSTRAINT chk_pain_score CHECK (((pain_score >= 0) AND (pain_score <= 10))),
	CONSTRAINT chk_program_week CHECK ((week_number > 0)),
	CONSTRAINT chk_rom_percent CHECK (((rom_percent >= (0)::double precision) AND (rom_percent <= (100)::double precision))),
	CONSTRAINT chk_week_number CHECK ((week_number > 0)),
	CONSTRAINT patient_recovery_logs_pkey PRIMARY KEY (id),
	CONSTRAINT unique_program_week UNIQUE (program_id, week_number)
);
CREATE INDEX idx_patient_id ON public.patient_recovery_logs USING btree (patient_id);
CREATE INDEX idx_patient_week ON public.patient_recovery_logs USING btree (patient_id, week_number);
CREATE INDEX idx_procedure ON public.patient_recovery_logs USING btree (procedure_type);
```

```sql
CREATE TABLE public.patients (
	id serial4 NOT NULL,
	"name" varchar(100) NOT NULL,
	height float8 NULL,
	gender varchar(20) NULL,
	CONSTRAINT patients_pkey PRIMARY KEY (id)
);
```

```sql
-- Store prediction results
CREATE TABLE prediction_logs (
  id SERIAL PRIMARY KEY,
  patient_id INT NOT NULL,
  program_id INT NOT NULL,
  week_number INT NOT NULL,
  predicted_rom FLOAT,
  predicted_pain FLOAT,
  predicted_steps INT,
  rom_confidence FLOAT,
  pain_confidence FLOAT,
  steps_confidence FLOAT,
  agent_decision VARCHAR(10),
  agent_reasoning TEXT,
  narrative TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alert records (written when agent says ALERT)
CREATE TABLE ai_alerts (
  id SERIAL PRIMARY KEY,
  patient_id INT NOT NULL,
  week_number INT NOT NULL,
  alert_reason TEXT,
  email_subject VARCHAR(255),
  email_sent BOOLEAN DEFAULT false,
  email_sent_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Node spawn pattern

```javascript
const { spawn } = require('child_process');

function runPython(script, inputJson) {
  return new Promise((resolve, reject) => {
    const proc = spawn('python', [script], { cwd: './python' });
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', d => stdout += d);
    proc.stderr.on('data', d => stderr += d);

    proc.on('close', code => {
      if (code !== 0) return reject(new Error(stderr));
      try {
        resolve(JSON.parse(stdout));
      } catch {
        reject(new Error(`Invalid JSON from ${script}: ${stdout}`));
      }
    });

    proc.stdin.write(JSON.stringify(inputJson));
    proc.stdin.end();
  });
}

// Usage in your route:
const prediction = await runPython('predict.py', patientInput);
const narrative  = await runPython('narrate.py', prediction);
const agent      = await runPython('agent.py', prediction);
```

---

## Windows note
Use `python` not `python3` in spawn on Windows 11.
Set cwd to the folder containing the .pkl files.
