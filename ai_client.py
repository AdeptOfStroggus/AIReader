import asyncio
import json
import os

# LangChain, FAISS и OpenAI импорты вынесены в ленивую загрузку

class RAGManager:
    """Управление векторным индексом FAISS для поиска по книге."""
    def __init__(self):
        # Используем легкую модель для эмбеддингов (инициализируется при первом использовании)
        self._embeddings = None
        self.vector_store = None
        self._text_splitter = None

    @property
    def embeddings(self):
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        return self._embeddings

    @property
    def text_splitter(self):
        if self._text_splitter is None:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            self._text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100,
                length_function=len,
            )
        return self._text_splitter

    def add_page_text(self, text, page_index):
        """Разбивает текст страницы на чанки и добавляет в индекс."""
        if not text or len(text.strip()) < 10:
            return

        from langchain_core.documents import Document
        # Очищаем HTML теги для индексации (простой способ)
        import re
        clean_text = re.sub('<[^<]+?>', '', text)
        
        chunks = self.text_splitter.split_text(clean_text)
        documents = [
            Document(page_content=chunk, metadata={"page": page_index})
            for chunk in chunks
        ]
        
        if self.vector_store is None:
            from langchain_community.vectorstores import FAISS
            self.vector_store = FAISS.from_documents(documents, self.embeddings)
        else:
            self.vector_store.add_documents(documents)

    def search(self, query, k=4, page_numbers=None):
        """Поиск наиболее релевантных фрагментов с опциональной фильтрацией по страницам."""
        if self.vector_store is None:
            return []
        
        filter_dict = None
        if page_numbers:
            # Преобразуем список страниц (1-based) в 0-based для метаданных
            zero_based_pages = [p - 1 for p in page_numbers]
            if len(zero_based_pages) == 1:
                filter_dict = {"page": zero_based_pages[0]}
            else:
                # FAISS filter в langchain поддерживает callable или dict
                # Для нескольких значений используем lambda
                filter_dict = lambda metadata: metadata.get("page") in zero_based_pages

        docs = self.vector_store.similarity_search(query, k=k, filter=filter_dict)
        return docs

    def clear(self):
        """Очистка индекса при загрузке новой книги."""
        self.vector_store = None

class AIClient():
    def __init__(self):
        from openai import AsyncOpenAI
        self.rag_manager = RAGManager()
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
            """Выполняет асинхронный запрос к API для получения списка моделей с определением serverless типа через эндпоинты."""
            import httpx
            headers = {"Authorization": f"Bearer {self.openaiapijson.get('OPENAI_API_KEY', '')}"}
            base_url = self.openaiapijson.get('OPENAI_BASE_PATH', '').rstrip('/')
            
            async with httpx.AsyncClient() as client:
                # 1. Получаем список активных эндпоинтов (здесь точно указан тип serverless/dedicated)
                resp_endpoints = await client.get(f"{base_url}/endpoints", headers=headers)
                serverless_models_set = set()
                if resp_endpoints.status_code == 200:
                    endpoints_data = resp_endpoints.json()
                    endpoints_list = []
                    if isinstance(endpoints_data, list):
                        endpoints_list = endpoints_data
                    elif isinstance(endpoints_data, dict) and 'data' in endpoints_data:
                        endpoints_list = endpoints_data['data']
                    
                    for e in endpoints_list:
                        if e.get('type') == 'serverless':
                            model_name = e.get('model')
                            if model_name:
                                serverless_models_set.add(model_name)

                # 2. Получаем полный список моделей библиотеки
                resp_models = await client.get(f"{base_url}/models", headers=headers)
                models_data = resp_models.json()
                
                models_info = []
                items = []
                if isinstance(models_data, list):
                    items = models_data
                elif isinstance(models_data, dict) and 'data' in models_data:
                    items = models_data['data']
                
                for m in items:
                    if 'id' in m:
                        m_id = m['id']
                        # Модель считается serverless, если она есть в списке активных serverless эндпоинтов
                        # Или если у неё есть цена за токены (подстраховка)
                        is_serverless = m_id in serverless_models_set
                        
                        if not is_serverless:
                            pricing = m.get('pricing', {})
                            if pricing and (pricing.get('input', 0) > 0 or pricing.get('output', 0) > 0):
                                is_serverless = True
                        
                        models_info.append({
                            "id": m_id,
                            "is_serverless": is_serverless
                        })

                # Сортировка по ID
                models_info.sort(key=lambda x: x['id'])
                self.modelListID = [m['id'] for m in models_info]
                return models_info
        except Exception as e:
            print(f"Ошибка при получении моделей: {e}")
            return [{"id": f"Ошибка: {str(e)}", "is_serverless": False}]
    
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
    
