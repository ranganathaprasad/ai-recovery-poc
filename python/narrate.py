# ==========================================
# narrate.py
# Takes prediction JSON from stdin
# Calls Ollama (local LLaMA) to generate
# a clinical narrative for the doctor
# Writes narrative JSON to stdout
#
# Why Ollama over OpenAI:
#   Patient health data must not leave the
#   network. Ollama runs 100% locally.
#   No PHI sent to third-party APIs.
# ==========================================

import sys
import json
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2"   # change to "mistral" if preferred


def build_prompt(pred: dict) -> str:
    f = pred["forecast"]
    cohort = pred["cohort"]
    drivers = pred["drivers"]
    summary = pred["input_summary"]

    positive_labels = [d["label"] for d in drivers.get("positive", [])]
    concern_labels = [d["label"] for d in drivers.get("concern", [])]

    return f"""You are a clinical narrative converter for a post-surgical recovery platform.
Your ONLY job is to convert structured prediction data into plain clinical language for a physiotherapist.
You are a converter, not a clinician — stay strictly within what the data explicitly shows.

Patient context:
- Procedure: {summary.get("procedure_type")}
- Week of recovery: {summary.get("current_week")}
- Age: {summary.get("age")}, Gender: {summary.get("gender")}

Next week prediction:
- ROM (Range of Motion): {f['rom']['prediction']}% (confidence: {f['rom']['label']})
- Pain Score: {f['pain']['prediction']}/10 (confidence: {f['pain']['label']})
- Walking Steps: {f['steps']['prediction']} steps/day (confidence: {f['steps']['label']})

Compared to {cohort['similar_patients_count']} similar patients:
- ROM: {cohort['comparison']['rom']} (cohort avg: {cohort['averages']['rom']}%)
- Pain: {cohort['comparison']['pain']} (cohort avg: {cohort['averages']['pain']}/10)
- Activity: {cohort['comparison']['activity']} (cohort avg: {cohort['averages']['steps']} steps)

Positive signals: {', '.join(positive_labels) if positive_labels else 'None'}
Concerns: {', '.join(concern_labels) if concern_labels else 'None'}

Write a concise clinical summary (3-4 sentences) following these rules strictly:
- Reflect ONLY what the data above explicitly shows — do not add, amplify, or downplay any signal
- Do not introduce clinical opinions or concerns not present in the positive/concern lists above
- Do not repeat or list numerical values — describe what they mean clinically
- Highlight the most important signal (positive or concern) from the data
- End with one concrete recommended action supported by the data only
- Use plain clinical language, no jargon, no hedging phrases like 'it appears that'
- Do NOT say 'AI predicted', 'the model', or reference any system
- Do NOT add warnings or recommendations beyond what the concern list contains"""


def call_ollama(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a concise clinical assistant. Respond in 3-4 sentences only. No bullet points."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["message"]["content"].strip()
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Cannot reach Ollama at {OLLAMA_URL}. "
            f"Is Ollama running? Run: ollama serve\nError: {e}"
        )


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"error": "No input received"}))
        sys.exit(1)

    try:
        prediction = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    if "error" in prediction:
        print(json.dumps({"error": "Upstream prediction failed", "details": prediction["error"]}))
        sys.exit(1)

    prompt = build_prompt(prediction)

    try:
        narrative = call_ollama(prompt)
    except ConnectionError as e:
        # Graceful fallback — return rule-based insight if Ollama is down
        narrative = prediction.get("insight", "Recovery monitoring in progress.")
        output = {
            "narrative": narrative,
            "source": "fallback",
            "warning": str(e)
        }
        print(json.dumps(output))
        return

    output = {
        "narrative": narrative,
        "source": "ollama",
        "model": MODEL
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
