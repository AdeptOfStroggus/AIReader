import asyncio
import json
import httpx
import os
import sys

# Добавляем корневую директорию в пути поиска модулей
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from ai_client import AIClient

async def debug_endpoints():
    """Отладка эндпоинтов (из debug_together_models.py)"""
    print("\n--- DEBUGGING ENDPOINTS ---")
    try:
        # Пытаемся прочитать .env как JSON (как в оригинале)
        env_path = ".env"
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                env_data = json.load(f)
            
            api_key = env_data.get('OPENAI_API_KEY', '')
            base_url = env_data.get('OPENAI_BASE_PATH', '').rstrip('/')
            
            headers = {"Authorization": f"Bearer {api_key}"}
            
            async with httpx.AsyncClient() as client:
                # Try /endpoints
                resp = await client.get(f"{base_url}/endpoints", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    endpoints = data.get('data', [])
                    
                    print(f"Total endpoints: {len(endpoints)}")
                    
                    types = {}
                    for e in endpoints:
                        e_type = e.get('type')
                        types[e_type] = types.get(e_type, 0) + 1
                    
                    print(f"Types: {types}")
                    
                    # If there are dedicated, print one
                    if types.get('dedicated'):
                        dedicated = next(e for e in endpoints if e.get('type') == 'dedicated')
                        print("\n--- DEDICATED ENDPOINT SAMPLE ---")
                        print(json.dumps(dedicated, indent=2))
                else:
                    print(f"Error fetching endpoints: {resp.status_code}")
        else:
            print(".env file not found.")
                
    except Exception as e:
        print(f"Error in debug_endpoints: {e}")

async def test_models():
    """Тестирование получения моделей (из verify_models.py)"""
    print("\n--- TESTING MODELS ---")
    try:
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
    except Exception as e:
        print(f"Error in test_models: {e}")

async def main():
    print("AIReader Debug Tools")
    print("====================")
    
    await debug_endpoints()
    await test_models()

if __name__ == "__main__":
    asyncio.run(main())
