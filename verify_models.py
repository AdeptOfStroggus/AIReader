import asyncio
import json
from ai_client import AIClient

async def test_models():
    client = AIClient()
    print("Fetching models...")
    models = await client.GetModelsAsync()
    if isinstance(models, list) and len(models) > 0:
        if "Ошибка" in str(models[0]):
            print(f"Failed to fetch models: {models[0]}")
        else:
            print(f"Successfully fetched {len(models)} models.")
            print("First 5 models:", models[:5])
    else:
        print("No models found or error occurred.")

if __name__ == "__main__":
    asyncio.run(test_models())
