import os
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/projects/shepdog-demo/booking/.env"))
from openai import OpenAI

client = OpenAI()

r1 = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": "What is the capital of France?"}]
)
print("Turn 1:", r1.choices[0].message.content)

r2 = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": r1.choices[0].message.content},
        {"role": "user", "content": "And what is its population?"}
    ]
)
print("Turn 2:", r2.choices[0].message.content)