import httpx, json
from .config import AI_API_KEY, AI_BASE_URL, AI_MODEL

async def explain(question, context):
    if not AI_API_KEY:
        return {"text":"AI provider is not configured. The application can still perform deterministic analytics without inventing results."}
    system=("You are a careful data analyst. Use only the provided computed context. "
            "Never invent values. Never claim causation from correlation. If evidence is insufficient, "
            "say exactly: The available data is insufficient to determine this.")
    payload={"model":AI_MODEL,"messages":[{"role":"system","content":system},{"role":"user","content":json.dumps({"question":question,"computed_context":context},default=str)}],"temperature":0.1}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r=await client.post(f"{AI_BASE_URL.rstrip('/')}/chat/completions",headers={"Authorization":f"Bearer {AI_API_KEY}","Content-Type":"application/json"},json=payload)
            r.raise_for_status(); data=r.json(); return {"text":data["choices"][0]["message"]["content"]}
    except Exception:
        return {"text":"The AI service is temporarily unavailable. The deterministic result is still shown."}
