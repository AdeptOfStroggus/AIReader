import asyncio
from openai import AsyncOpenAI
from pydantic import BaseModel
import json

class AIClient():
    def __init__(self):

        with open(".env", 'r') as openai_env:
            self.rawData = openai_env.read()
            self.openaiapijson = json.loads(self.rawData)

        self.async_client = AsyncOpenAI(
            # This is the default and can be omitted
            api_key=self.openaiapijson['OPENAI_API_KEY'],
            base_url=self.openaiapijson['OPENAI_BASE_PATH']
        )


    async def CreateResponceAsync(self, modelID, query, text):
        response = await self.async_client.responses.create(
            model=modelID,
            instructions=("""
            Ты - надёжный помощник в анализе различной литературы. Твоя задача - максимально подробно и точно изучить текст и выполнить задачу, которую дал пользователь. Ответ выдавай в HTML, и только ответ на задачу (не более). 

            Текст:
            """ + text),
            input=query,
        )
        return response.output_text

    async def GetModelsAsync(self):
        """Выполняет асинхронный запрос к API для получения списка моделей."""
        resp_models = await self.async_client.models.list()
        model_ids = [model.id for model in resp_models.data]
        self.modelListID = model_ids
        return model_ids
    
    def SetCurrentModelID(self, id):
        self.currentModelId = id
    
    async def CreateTOC(self, text):
        """Создает оглавление для текста."""
        response = await self.async_client.responses.create(
            model=self.modelListID[self.currentModelId],
            instructions=("""
            Ты - надёжный помощник в анализе различной литературы. Твоя задача - максимально подробно и точно помочь пользователю проанализировать текст.
 
            Текст:
            """ + text),
            input="Создай оглавление для данного текста",
        )
        return response.output_text


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
    
