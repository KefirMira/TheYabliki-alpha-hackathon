
import os
from dotenv import load_dotenv
from openai import OpenAI

print("Скрипт запущен!")

load_dotenv()

client = OpenAI(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ["LLM_BASE_URL"]
)

response = client.chat.completions.create(
    model=os.environ["LLM_MODEL"],
    messages=[
        {
            "role": "system",
            "content": (
                "Ты финансовый аналитик. "
                "Объясняй влияние новостей на бизнес. "
                "Не выдумывай факты."
            )
        },
        {
            "role": "user",
            "content": (
                "Как повышение ключевой ставки "
                "влияет на компанию с кредитами?"
            )
        }
    ],
    max_tokens=400
)

print(response.choices[0].message.content)

print("Скрипт завершён!")