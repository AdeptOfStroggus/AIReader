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
    # Рекомендованные модели для задач AIReader
    RECOMMENDED_MODELS = [
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "Qwen/Qwen2.5-72B-Instruct-Turbo",
        "deepseek-ai/DeepSeek-V3",
        "deepseek-ai/DeepSeek-R1",
    ]

    def __init__(self):
        from openai import AsyncOpenAI
        self.rag_manager = RAGManager()
        self.chat_history = []  # История чата
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

    def add_to_history(self, role, content):
        """Добавляет сообщение в историю чата."""
        self.chat_history.append({"role": role, "content": content})

    def clear_history(self):
        """Очищает историю чата."""
        self.chat_history = []


    async def CreateResponceAsync(self, modelID, query, text):
        try:
            # Система сообщение
            system_message = {
                "role": "system",
                "content": (
                    "Ты - надёжный помощник в анализе различной литературы. Твоя задача - максимально подробно и точно изучить текст и выполнить задачу, которую дал пользователь.\n\n"
                    "ОБЯЗАТЕЛЬНОЕ УСЛОВИЕ: Для каждого утверждения, которое ты берешь из предоставленного текста, ты ДОЛЖЕН указать источник. "
                    "Формулы приведены в формате LaTeX, переводи их в читаемый вид в HTML и указывай источник для формул так же, как и для текста."
                    "Используй для этого специальный HTML-тег: <a href=\"source://page=N&text=цитата\">[Стр. N]</a>, где N - номер страницы, а 'цитата' - короткий (3-5 слов) уникальный фрагмент текста из этой страницы, на который ты ссылаешься.\n\n"
                    "Пример: 'Согласно исследованиям, климат меняется <a href=\"source://page=5&text=глобальное потепление наступает\">[Стр. 5]</a>.'\n\n"
                    "Ответ выдавай в HTML, и только ответ на задачу (не более). Не надо говорить 'этот HTML код выполняет то-то то-то' и такое прочее."
                )
            }
            
            # Пользовательское сообщение с текстом
            user_message = {
                "role": "user",
                "content": f"Текст предоставлен ниже:\n{text}\n\nЗадача: {query}"
            }
            
            # Собираем messages: система + история + текущее сообщение
            messages = [system_message] + self.chat_history + [user_message]
            
            response = await self.async_client.chat.completions.create(
                model=modelID,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Ошибка API: {str(e)}"

    async def GetModelsAsync(self):
        try:
            """Выполняет асинхронный запрос к API для получения списка моделей."""
            import httpx
            import re
            headers = {"Authorization": f"Bearer {self.openaiapijson.get('OPENAI_API_KEY', '')}"}
            base_url = self.openaiapijson.get('OPENAI_BASE_PATH', '').rstrip('/')
            
            # 1. Загружаем статический список Chat Serverless моделей из файла
            serverless_chat_ids = set()
            try:
                import os
                file_path = os.path.join(os.path.dirname(__file__), "serverless-models.md")
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                    # Извлекаем только секцию "Chat models"
                    chat_section_match = re.search(r'## Chat models(.*?)(?:##|$)', content, re.DOTALL)
                    if chat_section_match:
                        chat_content = chat_section_match.group(1)
                        # Ищем строки в таблицах: | Organization | Model Name | API Model String | ...
                        # Паттерн ищет третью колонку в строках, начинающихся с '|'
                        matches = re.findall(r'^\|\s*[^|]+\s*\|\s*[^|]+\s*\|\s*([^|\s]+)\s*\|', chat_content, re.MULTILINE)
                        for m_id in matches:
                            if m_id and m_id not in ("API", "Model", "---") and '/' in m_id:
                                serverless_chat_ids.add(m_id)
            except Exception as e:
                print(f"Ошибка при чтении serverless-models.md: {e}")

            async with httpx.AsyncClient() as client:
                models_info = []
                seen_ids = set()

                # 2. Получаем список моделей из API и фильтруем только те, что есть в списке Chat
                try:
                    resp_models = await client.get(f"{base_url}/models", headers=headers)
                    if resp_models.status_code == 200:
                        models_data = resp_models.json()
                        items = models_data if isinstance(models_data, list) else models_data.get('data', [])
                        
                        for m in items:
                            m_id = m.get('id')
                            if not m_id: continue
                            
                            # Фильтруем: оставляем только те, что есть в списке Chat моделей из MD файла
                            # Проверяем как полное совпадение, так и по короткому имени
                            is_in_chat_list = m_id in serverless_chat_ids
                            if not is_in_chat_list:
                                short_id = m_id.split('/')[-1] if '/' in m_id else m_id
                                is_in_chat_list = any(short_id == (s.split('/')[-1] if '/' in s else s) for s in serverless_chat_ids)
                            
                            if is_in_chat_list:
                                seen_ids.add(m_id)
                                models_info.append({
                                    "id": m_id,
                                    "is_serverless": True, # Все модели из этого списка - serverless
                                    "is_recommended": m_id in self.RECOMMENDED_MODELS
                                })
                except Exception as e:
                    print(f"Ошибка при получении списка моделей из API: {e}")

                # 3. Добавляем активные эндпоинты (только Serverless), если они есть в списке чатовых моделей
                try:
                    resp_endpoints = await client.get(f"{base_url}/endpoints", headers=headers)
                    if resp_endpoints.status_code == 200:
                        endpoints_data = resp_endpoints.json()
                        items = endpoints_data if isinstance(endpoints_data, list) else endpoints_data.get('data', [])
                        
                        for e in items:
                            m_id = e.get('model')
                            e_type = e.get('type')
                            if m_id and m_id not in seen_ids and e_type == 'serverless':
                                # Проверяем, является ли эта модель чатовой (из нашего списка)
                                is_chat = m_id in serverless_chat_ids or \
                                         any((m_id.split('/')[-1] if '/' in m_id else m_id) == \
                                             (s.split('/')[-1] if '/' in s else s) for s in serverless_chat_ids)
                                
                                if is_chat:
                                    models_info.append({
                                        "id": m_id,
                                        "is_serverless": True,
                                        "is_recommended": m_id in self.RECOMMENDED_MODELS
                                    })
                                    seen_ids.add(m_id)
                except Exception as e:
                    print(f"Предупреждение: Не удалось получить список эндпоинтов: {e}")

                # Сортировка: сначала рекомендованные, затем по ID
                models_info.sort(key=lambda x: (not x['is_recommended'], x['id']))
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
    
