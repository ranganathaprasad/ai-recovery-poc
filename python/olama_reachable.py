import urllib.request
import json

url = "http://localhost:11434/api/chat"
payload = {
    "model": "llama3.2",
    "messages": [{"role": "user", "content": "Reply with just the word OK"}],
    "stream": False
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
        print("SUCCESS:", data["message"]["content"])
except Exception as e:
    print("FAILED:", type(e).__name__, str(e))