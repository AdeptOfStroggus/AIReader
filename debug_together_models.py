import httpx
import json
import asyncio

async def debug_endpoints():
    try:
        with open(".env", 'r', encoding='utf-8') as f:
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
                    print("\n--- DEDICATED ENDPOINT ---")
                    print(json.dumps(dedicated, indent=2))
            else:
                print(f"Error fetching endpoints: {resp.status_code}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_endpoints())
