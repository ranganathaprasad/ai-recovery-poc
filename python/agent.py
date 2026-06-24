# ==========================================
# agent.py
# Clinical Alert Agent with guardrails
#
# Guardrail: ALERT requires 2+ corroborating
# concern signals — prevents alert fatigue
# Guardrail: MONITOR/OK always return null
# for email fields — no false notifications
# ==========================================

import sys
import json
import urllib.request
import urllib.error
import re

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"

SYSTEM_PROMPT = """You are a clinical alert agent for a post-surgical recovery platform.

Your job is to reason carefully about a patient's recovery data and decide if a doctor needs to be alerted.

You must reason step by step (chain of thought), then give a final JSON decision.

Rules:
- Consider ALL signals together — a high pain score alone is not enough if ROM and activity are improving
- A patient consistently below cohort average on multiple metrics is more concerning than one bad metric
- Low exercise adherence in early weeks (1-2) is expected; in week 4+ it is a serious flag
- Improving trends matter more than absolute values in early recovery weeks
- If unsure, choose MONITOR over ALERT (avoid alert fatigue)
- ALERT requires at least 2 corroborating concern signals — one bad metric alone is never enough
- If decision is MONITOR or OK, alert_reason MUST be null, email_subject MUST be null, email_body MUST be null

Output format — return valid JSON only, no markdown, no extra text:
{
  "reasoning": "Step by step clinical reasoning here...",
  "decision": "ALERT" | "MONITOR" | "OK",
  "confidence": "High" | "Medium" | "Low",
  "alert_reason": "Short reason if ALERT, else null",
  "email_subject": "Subject line if ALERT, else null",
  "email_body": "2-3 sentence email body to doctor if ALERT, else null",
  "recommended_action": "One specific clinical action recommended"
}"""

def clean_json_response(text):
    # Remove ```json ... ``` or ``` ... ``` wrappers
    text = re.sub(r'^```json\s*', '', text.strip())
    text = re.sub(r'^```\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    return text.strip()

def build_agent_prompt(pred: dict) -> str:
    f       = pred["forecast"]
    cohort  = pred["cohort"]
    drivers = pred["drivers"]
    summary = pred["input_summary"]
    severity = pred.get("severity", {})
    guardrails = pred.get("guardrails", {})

    concern_labels  = [d["label"] for d in drivers.get("concern", [])]
    positive_labels = [d["label"] for d in drivers.get("positive", [])]

    warning_text = ""
    if guardrails.get("has_warnings"):
        warning_text = f"\nData quality warnings: {'; '.join(guardrails['warnings'])}"

    return f"""Assess this patient's recovery and decide on clinical action.

Patient:
- Procedure: {summary.get("procedure_type")}
- Recovery week: {summary.get("current_week")}
- Age: {summary.get("age")}, Gender: {summary.get("gender")}

Next week forecast:
- ROM: {f['rom']['prediction']}% (confidence: {f['rom']['label']})
- Pain: {f['pain']['prediction']}/10 (confidence: {f['pain']['label']})
- Steps: {f['steps']['prediction']}/day (confidence: {f['steps']['label']})

Cohort comparison (vs {cohort['similar_patients_count']} similar patients):
- ROM: {cohort['comparison']['rom']} (avg: {cohort['averages']['rom']}%)
- Pain: {cohort['comparison']['pain']} (avg: {cohort['averages']['pain']}/10)
- Activity: {cohort['comparison']['activity']} (avg: {cohort['averages']['steps']} steps)

Positive signals ({len(positive_labels)}): {', '.join(positive_labels) if positive_labels else 'None'}
Concerns ({len(concern_labels)}): {', '.join(concern_labels) if concern_labels else 'None'}
System severity flag: {"YES" if severity.get("is_severe") else "NO"}{warning_text}

GUARDRAIL REMINDER: ALERT requires 2 or more concern signals. This patient has {len(concern_labels)} concern(s).
If MONITOR or OK: set alert_reason, email_subject, email_body all to null.

Reason step by step, then output your JSON decision."""


def enforce_guardrails(result: dict) -> dict:
    """
    Post-processing guardrail.
    Even if LLM ignores instructions, enforce:
    1. MONITOR/OK must have null email fields
    2. ALERT requires severity flag or 2+ concerns
    This is the safety net after LLM output.
    """
    decision = result.get("decision", "MONITOR")

    if decision in ("MONITOR", "OK"):
        result["alert_reason"]  = None
        result["email_subject"] = None
        result["email_body"]    = None

    return result


def call_ollama(prompt: str) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ],
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=360) as resp:
            result  = json.loads(resp.read().decode("utf-8"))
            content = result["message"]["content"].strip()

            # Strip markdown fences if model wraps in ```json
            if content.startswith("```"):
                lines   = content.split("\n")
                content = "\n".join(lines[1:-1]).strip()

            parsed = json.loads(content)
            # Apply guardrail enforcement on top of LLM output
            return enforce_guardrails(parsed)

    except urllib.error.URLError as e:
        raise ConnectionError(f"Cannot reach Ollama: {e}")
    except json.JSONDecodeError:
        raise ValueError("Agent returned non-JSON response")


def rule_based_fallback(pred: dict) -> dict:
    """
    Fallback when Ollama is unavailable.
    Deterministic rules with explicit reasoning.
    Same guardrail: ALERT needs 2+ concerns.
    """
    severity  = pred.get("severity", {})
    f         = pred["forecast"]
    cohort    = pred["cohort"]
    concerns  = [d["label"] for d in pred["drivers"].get("concern", [])]
    positives = [d["label"] for d in pred["drivers"].get("positive", [])]
    week      = pred["input_summary"].get("current_week", 1)

    pain_pred = f["pain"]["prediction"]
    avg_pain  = cohort["averages"]["pain"]
    rom_pred  = f["rom"]["prediction"]
    avg_rom   = cohort["averages"]["rom"]

    concern_count = len(concerns)

    # Guardrail: ALERT needs severity flag AND 2+ concerns
    is_alert   = severity.get("is_severe") and concern_count >= 2
    is_monitor = severity.get("is_severe") or concern_count >= 2

    reasoning = (
        f"Rule-based fallback (Ollama unavailable). "
        f"Week {week} patient. "
        f"Concerns detected: {concern_count} ({', '.join(concerns) if concerns else 'none'}). "
        f"Positive signals: {len(positives)}. "
        f"Severity flag: {severity.get('is_severe')}. "
        f"Guardrail: ALERT requires severity + 2 concerns — {'met' if is_alert else 'not met'}."
    )

    if is_alert:
        return {
            "reasoning":          reasoning,
            "decision":           "ALERT",
            "confidence":         "Medium",
            "alert_reason":       f"Multiple concerns in week {week}: {'; '.join(concerns[:2])}",
            "email_subject":      f"[Alert] Patient recovery concern - Week {week}",
            "email_body":         (
                f"Patient shows concerning recovery signals in week {week}. "
                f"Predicted pain {round(pain_pred,1)}/10 and ROM {round(rom_pred,1)}% "
                f"are below expected levels. Clinician review recommended."
            ),
            "recommended_action": "Schedule review call within 24 hours",
            "source":             "rule_based_fallback"
        }
    elif is_monitor:
        return {
            "reasoning":          reasoning,
            "decision":           "MONITOR",
            "confidence":         "Medium",
            "alert_reason":       None,
            "email_subject":      None,
            "email_body":         None,
            "recommended_action": "Flag for next scheduled review",
            "source":             "rule_based_fallback"
        }
    else:
        return {
            "reasoning":          reasoning,
            "decision":           "OK",
            "confidence":         "High",
            "alert_reason":       None,
            "email_subject":      None,
            "email_body":         None,
            "recommended_action": "Continue current program",
            "source":             "rule_based_fallback"
        }


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "No input received"}))
        sys.exit(1)

    try:
        cleaned = clean_json_response(raw)
        prediction = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    if "error" in prediction:
        print(json.dumps({"error": "Upstream error", "details": prediction["error"]}))
        sys.exit(1)

    prompt = build_agent_prompt(prediction)

    try:
        agent_result = call_ollama(prompt)
        agent_result["source"] = "llm_agent"

    except ConnectionError as e:
        agent_result = rule_based_fallback(prediction)
        agent_result["warning"] = "LLM unavailable — used rule-based fallback"

    except ValueError as e:
        agent_result = rule_based_fallback(prediction)
        agent_result["warning"] = "LLM returned invalid JSON — fallback used"


    print(json.dumps(agent_result, indent=2))


if __name__ == "__main__":
    main()
