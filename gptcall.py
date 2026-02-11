from openai import OpenAI
import os

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def call_llm(system_prompt: str, user_prompt: str, *, model: str = "gpt-5-mini") -> str:
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.output_text

if __name__ == "__main__":
    # Just a little test
    print("LLM RESPONSE:", call_llm(system_prompt="you are just a test, return OK", 
                                    user_prompt = "return things are groovy", 
                                    ))
