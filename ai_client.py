import asyncio
from openai import AsyncOpenAI
from pydantic import BaseModel
import json


class AIClient():
    def __init__(self):
        try:
            with open(".env", 'r', encoding='utf-8') as openai_env:
                self.rawData = openai_env.read()
                self.openaiapijson = json.loads(self.rawData)
        except Exception as e:
            print(f"Ошибка загрузки .env: {e}")
            self.openaiapijson = {"OPENAI_API_KEY": "", "OPENAI_BASE_PATH": ""}

        self.async_client = AsyncOpenAI(
            api_key=self.openaiapijson.get('OPENAI_API_KEY', ''),
            base_url=self.openaiapijson.get('OPENAI_BASE_PATH', '')
        )


    async def CreateResponceAsync(self, modelID, query, text):
        try:
            response = await self.async_client.chat.completions.create(
                model=modelID,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - надёжный помощник в анализе различной литературы. Твоя задача - максимально подробно и точно изучить текст и выполнить задачу, которую дал пользователь. Ответ выдавай в HTML, и только ответ на задачу (не более). Не надо говорить 'этот HTML код выполняет то-то то-то' и такое прочее."
                    },
                    {
                        "role": "user",
                        "content": f"Текст предоставлен ниже:\n{text}\n\nЗадача: {query}"
                    }
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Ошибка API: {str(e)}"

    async def GetModelsAsync(self):
        try:
            """Выполняет асинхронный запрос к API для получения списка моделей."""
            # Пробуем стандартный метод OpenAI
            try:
                resp_models = await self.async_client.models.list()
                model_ids = [model.id for model in resp_models.data]
            except Exception as e:
                # Если стандартный метод не сработал (например, Together AI возвращает список напрямую)
                # Делаем ручной запрос через httpx
                import httpx
                headers = {"Authorization": f"Bearer {self.openaiapijson.get('OPENAI_API_KEY', '')}"}
                base_url = self.openaiapijson.get('OPENAI_BASE_PATH', '').rstrip('/')
                async with httpx.AsyncClient() as client:
                    resp = await client.get(f"{base_url}/models", headers=headers)
                    data = resp.json()
                    if isinstance(data, list):
                        model_ids = [m['id'] for m in data if 'id' in m]
                    elif isinstance(data, dict) and 'data' in data:
                        model_ids = [m['id'] for m in data['data'] if 'id' in m]
                    else:
                        raise e

            model_ids.sort()
            self.modelListID = model_ids
            return model_ids
        except Exception as e:
            print(f"Ошибка при получении моделей: {e}")
            return [f"Ошибка: {str(e)}"]
    
    def SetCurrentModelID(self, id):
        self.currentModelId = id
    
    async def CreateTOC(self, text):
        """Создает оглавление для текста."""
        try:
            model = self.modelListID[self.currentModelId] if hasattr(self, 'modelListID') else "gpt-3.5-turbo"
            response = await self.async_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - надёжный помощник в анализе различной литературы. Твоя задача - максимально подробно и точно помочь пользователю проанализировать текст."
                    },
                    {
                        "role": "user",
                        "content": f"Текст:\n{text}\n\nСоздай оглавление для данного текста"
                    }
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Ошибка при создании оглавления: {str(e)}"


def test_GetModels():
    client = AIClient()
    asyncio.run(client.GetModelsAsync())
    print(client.modelListID)

def test_CreateResponce():
    client = AIClient()
    asyncio.run(client.GetModelsAsync())
    print(client.modelListID)

    #a = asyncio.run(client.CreateTOC("1.Что-то 2.Что-то ещё 3.Что-то третье 4.Что-то четвёртое"))
    #print(a)


#test_GetModels()
#test_CreateResponce()
    
