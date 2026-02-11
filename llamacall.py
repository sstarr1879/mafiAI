import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.1:8b"

def call_llm(system_prompt: str, user_prompt: str, model: str = MODEL) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 120  # cap tokens (important for cost & speed)
        }
    }

    r = requests.post(OLLAMA_URL, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"]


if __name__ == "__main__":
    # Just a little test
    print("LLM RESPONSE:", call_llm(system_prompt="you are just a test, return OK", 
                                    user_prompt = "return things are groovy", 
                                    ))
