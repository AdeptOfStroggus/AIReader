import asyncio
import base64
from io import BytesIO
import json
import os
import threading
from PIL import Image
import clip
import faiss
import torch

# LangChain, FAISS и OpenAI импорты вынесены в ленивую загрузку

import os
import base64
import pickle
from io import BytesIO
from typing import Union, List, Tuple, Optional

import torch
import faiss
import numpy as np
from PIL import Image
import clip

import os
import base64
import pickle
from io import BytesIO
from typing import List, Tuple, Optional, Union
import numpy as np
import torch
import faiss
from PIL import Image
from transformers import CLIPProcessor, CLIPModel, CLIPConfig

from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_classic.retrievers import MultiQueryRetriever


class ImageIndexer:
    """
    Индексатор изображений по их ТЕКСТОВЫМ ОПИСАНИЯМ.
    При добавлении изображения вы обязаны предоставить text_description.
    Поиск осуществляется по текстовому запросу, возвращаются изображения.
    """

    def __init__(
        self,
        client,
        model_name: str = "zer0int/LongCLIP-GmP-ViT-L-14",
        device: Optional[str] = None,
        caption_model: Optional[str] = "Salesforce/blip2-opt-2.7b"
    ):
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.client = client
        # CLIP для превращения текста в эмбеддинги
        self.clip_model = CLIPModel.from_pretrained(model_name)
        self.clip_processor = CLIPProcessor.from_pretrained(model_name, padding="max_length", max_length=248)

        # Определяем размерность эмбеддинга CLIP через реальный тензор
        with torch.no_grad():
            dummy_text = self.clip_processor(text=["test"], return_tensors="pt", padding=True)
            # get_text_features возвращает тензор в новых версиях transformers
            dummy_emb = self.clip_model.get_text_features(**dummy_text)
            # Если вдруг вернулся объект с полем pooler_output или last_hidden_state
            if hasattr(dummy_emb, 'pooler_output'):
                dummy_emb = dummy_emb.pooler_output
            elif hasattr(dummy_emb, 'last_hidden_state'):
                dummy_emb = dummy_emb.last_hidden_state[:, 0, :]  # берём CLS-токен
            # Теперь dummy_emb должен быть тензором
            self.dimension = dummy_emb.shape[-1]  # последняя размерность
        
        self.index: Optional[faiss.Index] = None
        self.metadata: List[dict] = []  # каждый элемент: {"page": int, "image": str, "description": str}
        
        # Опциональная модель для генерации описаний
        self.caption_model = None
        if caption_model:
            from transformers import Blip2Processor, Blip2ForConditionalGeneration
            self.caption_processor = Blip2Processor.from_pretrained(caption_model,load_in_8bit=True, device_map="auto")
            self.caption_model = Blip2ForConditionalGeneration.from_pretrained(caption_model)
    
    # -------------------------------------------------------------------------
    # Преобразование входных данных в PIL Image
    # -------------------------------------------------------------------------
    def _to_pil_image(self, image_data: Union[str, bytes, Image.Image]) -> Image.Image:
        if isinstance(image_data, Image.Image):
            return image_data.convert("RGB")
        if isinstance(image_data, str):
            if os.path.isfile(image_data):
                return Image.open(image_data).convert("RGB")
            return Image.open(BytesIO(base64.b64decode(image_data))).convert("RGB")
        if isinstance(image_data, bytes):
            return Image.open(BytesIO(image_data)).convert("RGB")
        raise TypeError("image_data должен быть base64 строкой, bytes, PIL.Image или путём к файлу")
    
    # -------------------------------------------------------------------------
    # Генерация текстового описания (опционально)
    # -------------------------------------------------------------------------
    def generate_caption(self, image_data: Union[str, bytes, Image.Image]) -> str:
        if self.caption_model is None:
            raise RuntimeError("Caption model не загружена. Укажите caption_model при инициализации.")
        img = self._to_pil_image(image_data)
        inputs = self.caption_processor(img, return_tensors="pt")
        out = self.caption_model.generate(**inputs, max_length=50)
        caption = self.caption_processor.decode(out[0], skip_special_tokens=True)
        return caption
    
    # -------------------------------------------------------------------------
    # Получение эмбеддинга из ТЕКСТА (описания)
    # -------------------------------------------------------------------------
    def get_text_embedding(self, text: str) -> np.ndarray:
        inputs = self.clip_processor(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            emb = self.clip_model.get_text_features(**inputs)
        # Если emb является объектом (например, BaseModelOutput), извлекаем тензор
        if hasattr(emb, 'pooler_output'):
            emb = emb.pooler_output
        elif hasattr(emb, 'last_hidden_state'):
            emb = emb.last_hidden_state[:, 0, :]
        # Нормализация
        emb = emb / emb.norm(dim=-1, keepdim=True)
        return emb.cpu().numpy().astype('float32').flatten()
    
    # -------------------------------------------------------------------------
    # Добавление изображения с ОПИСАНИЕМ
    # -------------------------------------------------------------------------
    def add_image(
        self,
        image_data: Union[str, bytes, Image.Image],
        page_index: int,
        index_on_page: int,
        text_description: Optional[str] = None
    ) -> int:
        if text_description is None:
            if self.caption_model is not None:
                text_description = self.generate_caption(image_data)
                print(f"Сгенерировано описание: {text_description}")
            else:
                raise ValueError("Необходимо указать text_description или включить caption_model")
        
        emb = self.get_text_embedding(text_description)
        
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dimension)
        
        self.index.add(emb.reshape(1, -1))
        self.metadata.append({
            "page": page_index,
            "index": index_on_page,
            "image": image_data,
            "description": text_description
        })
        return self.index.ntotal - 1
    
    # -------------------------------------------------------------------------
    # Поиск по текстовому запросу
    # -------------------------------------------------------------------------
    def search(self, query: str, k: int = 5) -> List[Tuple[dict, float]]:
        if self.index is None:
            raise RuntimeError("Индекс пуст. Добавьте изображения с описаниями.")
        
        query_emb = self.get_text_embedding(query).reshape(1, -1)
        scores, indices = self.index.search(query_emb, k)
        
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx != -1:
                results.append((self.metadata[idx], float(score)))
        return results
    
    # -------------------------------------------------------------------------
    # Сохранение / загрузка
    # -------------------------------------------------------------------------
    def save(self, index_path: str, metadata_path: str):
        if self.index is None:
            raise RuntimeError("Нечего сохранять.")
        faiss.write_index(self.index, index_path)
        with open(metadata_path, 'wb') as f:
            pickle.dump({
                'metadata': self.metadata,
                'dimension': self.dimension,
            }, f)
    
    @classmethod
    def load(cls, index_path: str, metadata_path: str, model_name: str = "openai/clip-vit-base-patch32", device=None):
        instance = cls(model_name=model_name, device=device)
        with open(metadata_path, 'rb') as f:
            data = pickle.load(f)
        instance.metadata = data['metadata']
        instance.dimension = data['dimension']
        instance.index = faiss.read_index(index_path)
        return instance
    
    def __len__(self):
        return self.index.ntotal if self.index else 0
    
    def _generate_queries_sync(self, original_query: str, num_queries: int = 3) -> List[str]:
        """
        Синхронная генерация альтернативных запросов с помощью OpenAI.
        Использует те же API-ключи, что и AIClient (из файла .env).
        """
        try:
            # Пытаемся загрузить конфигурацию из .env
            with open(".env", 'r', encoding='utf-8') as f:
                env_data = json.load(f)
            api_key = env_data.get('OPENAI_API_KEY')
            base_url = env_data.get('OPENAI_BASE_PATH')
        except Exception:
            api_key = os.environ.get('OPENAI_API_KEY')
            base_url = os.environ.get('OPENAI_BASE_PATH')
        
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY не найден ни в .env, ни в переменных окружения")
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        prompt = f"""
        Ты — помощник, который улучшает поиск изображений по текстовым описаниям.
        Пользователь задал запрос: "{original_query}"
        
        Сгенерируй {num_queries} различных вариантов перефразирования этого запроса.
        Варианты должны использовать разные синонимы, грамматические конструкции и стили,
        чтобы охватить максимальное количество релевантных описаний изображений.
        
        Напиши каждый вариант на новой строке, без нумерации и лишних пояснений.
        """
        
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",  # можно заменить на более мощную модель
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )
        
        content = response.choices[0].message.content
        queries = [q.strip() for q in content.strip().split('\n') if q.strip()]
        # Ограничиваем количество
        return queries[:num_queries]

    def multi_query_search(
        self,
        query: str,
        k: int = 5,
        num_queries: int = 3,
        k_per_query: Optional[int] = None
    ) -> List[Tuple[dict, float]]:
        """
        Поиск изображений с генерацией нескольких вариантов запроса (multi-query).
        
        Аргументы:
            query: исходный текстовый запрос.
            k: итоговое количество возвращаемых изображений.
            num_queries: количество альтернативных запросов для генерации (без учёта оригинала).
            k_per_query: сколько результатов брать на каждый запрос. Если None, то равно k.
        
        Возвращает:
            Список кортежей (metadata, score), где metadata содержит информацию об изображении.
            Результаты отсортированы по убыванию релевантности (score).
        """
        if self.index is None:
            raise RuntimeError("Индекс пуст. Добавьте изображения с описаниями.")
        
        if k_per_query is None:
            k_per_query = k  # обычно берём столько же, сколько хотим в итоге
        
        # 1. Генерируем альтернативные запросы
        try:
            alt_queries = self._generate_queries_sync(query, num_queries)
        except Exception as e:
            print(f"Ошибка генерации альтернативных запросов: {e}. Использую только оригинал.")
            alt_queries = []
        
        # Все запросы для поиска: оригинал + альтернативные
        all_queries = [query] + alt_queries
        
        # 2. Выполняем поиск по каждому запросу
        all_results = []  # (metadata, score)
        seen_images = set()  # для дедупликации по содержимому изображения
        
        for q in all_queries:
            results = self.search(q, k=k_per_query)
            for meta, score in results:
                # Используем содержимое изображения (base64 или путь) как ключ для уникальности
                img_key = meta.get('image')
                # Если изображение представлено в виде bytes или PIL, приведите к строке
                if isinstance(img_key, bytes):
                    img_key = img_key[:100]  # срез для уникальности
                elif not isinstance(img_key, str):
                    img_key = str(img_key)
                
                if img_key not in seen_images:
                    seen_images.add(img_key)
                    all_results.append((meta, score))
        
        # 3. Сортируем по убыванию score и обрезаем до k
        all_results.sort(key=lambda x: x[1], reverse=True)
        return all_results[:k]

class RAGManager:
    """Управление векторным индексом FAISS для поиска по книге."""
    def __init__(self, client):
        # Используем легкую модель для эмбеддингов (инициализируется при первом использовании)
        self._embeddings = None
        self.vector_store = None
        self._text_splitter = None
        self._lock = threading.Lock()
        self.indexed_pages = set()
        self._llm = None
        self.client = client

    @property
    def llm(self):
        if self._llm is None:
            

            # Используем те же параметры, что и в AIClient
            import json, os
            try:
                with open(".env", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                api_key = data.get('OPENAI_API_KEY')
                base_url = data.get('OPENAI_BASE_PATH')
            except:
                api_key = os.environ.get('OPENAI_API_KEY')
                base_url = os.environ.get('OPENAI_BASE_PATH')
            
            self._llm = ChatOpenAI(
                model="openai/gpt-oss-20b",  # или возьмите из self.currentModelId, если нужно
                openai_api_key=api_key,
                openai_api_base=base_url,
                temperature=0
            )
        return self._llm
    
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
        
        with self._lock:
            if self.vector_store is None:
                from langchain_community.vectorstores import FAISS
                self.vector_store = FAISS.from_documents(documents, self.embeddings)
            else:
                self.vector_store.add_documents(documents)
            self.indexed_pages.add(page_index)

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

    def multi_query_search(self, query: str, k=4, page_numbers=None, use_multi_query=True):
        """
        Поиск с мульти-запросами.
        Если use_multi_query=True, генерируются альтернативные формулировки запроса.
        """
        if self.vector_store is None:
            return []
        
        filter_dict = None
        if page_numbers:
            zero_based_pages = [p - 1 for p in page_numbers]
            if len(zero_based_pages) == 1:
                filter_dict = {"page": zero_based_pages[0]}
            else:
                filter_dict = lambda metadata: metadata.get("page") in zero_based_pages
        
        if not use_multi_query:
            return self.vector_store.similarity_search(query, k=k, filter=filter_dict)
        
        # Оборачиваем базовый ретривер в MultiQueryRetriever
        base_retriever = self.vector_store.as_retriever(
            search_kwargs={"k": k, "filter": filter_dict}
        )
        multi_retriever = MultiQueryRetriever.from_llm(
            retriever=base_retriever,
            llm=self.llm,
            # можно задать свой промпт, но дефолтный работает хорошо
        )
        # MultiQueryRetriever возвращает документы, возможно, с дубликатами (он сам убирает)
        return multi_retriever.invoke(query)

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
        self.rag_manager = RAGManager(self)
        self.image_indexer = ImageIndexer(self)
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
            base_url=self.openaiapijson.get('OPENAI_BASE_PATH', ''),
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
                    "Удели особое внимание формулам, и как они будут представлены пользователю. (необходимо, чтобы они хорошо рендерились в приложении, так что используй html для форматирования)"
                    "Формулы приведены в формате LaTeX, переводи их в читаемый вид в HTML и указывай источник для формул так же, как и для текста."
                    "Используй для этого специальный HTML-тег: <a href=\"source://page=N&text=цитата\">[Стр. N]</a>, где N - номер страницы, а 'цитата' - короткий (3-5 слов) уникальный фрагмент текста из этой страницы, на который ты ссылаешься.\n\n"
                    "Если информации недостаточно в предоставленном тексте, честно признай это и не выдавай домыслов. "
                    "Используй только материал из текста, который включен в контексте, и не приводи внешние знания.\n\n"
                    "Пример: 'Согласно исследованиям, климат меняется <a href=\"source://page=5&text=глобальное потепление наступает\">[Стр. 5]</a>.'\n\n"
                    "Ответ выдавай в HTML, и только ответ на задачу (не более). Не надо говорить 'этот HTML код выполняет то-то то-то' и такое прочее. Убедись в правильном формате кода, чтобы сообщение было корректно показано пользователю."
                )
            }
            
            # Пользовательское сообщение с текстом
            user_message = {
                "role": "user",
                "content": f"Текст предоставлен ниже:\n{text}\n\nЗадача: {query}"
            }
            
            # Собираем messages: система + история + текущее сообщение
            messages = [system_message] + self.chat_history + [user_message_image]
            
            response = await self.async_client.chat.completions.create(
                model=modelID,
                messages=messages,

            )
            self.add_to_history("user", user_message["content"])
            self.add_to_history("assistant", response.choices[0].message.content)
            return response.choices[0].message.content
        except Exception as e:
            return f"Ошибка API: {str(e)}"


    async def CreateResponceAsync(self, modelID, query, text, images):
        try:
            # Система сообщение
            system_message = {
                "role": "system",
                "content": (
                    "Ты - надёжный помощник в анализе различной литературы. Твоя задача - максимально подробно и точно изучить текст и выполнить задачу, которую дал пользователь.\n\n"
                    "ОБЯЗАТЕЛЬНОЕ УСЛОВИЕ: Для каждого утверждения, которое ты берешь из предоставленного текста, ты ДОЛЖЕН указать источник. "
                    "Удели особое внимание формулам, и как они будут представлены пользователю. (необходимо, чтобы они хорошо рендерились в приложении, так что используй html для форматирования). Когда тебе нужно изобразить формулу, изображай лишь формулу, без текста по типу 'формула в читаемом виде предоставлена' и тому прочего "
                    "Формулы в тексте приведены в формате LaTeX, в ответе переводи их в читаемый вид в HTML (MathML) и указывай источник для формул так же, как и для текста."
                    "Используй для этого специальный HTML-тег: <a href=\"source://page=N&text=цитата\">[Стр. N]</a>, где N - номер страницы, а 'цитата' - короткий (3-5 слов) уникальный фрагмент текста из этой страницы, на который ты ссылаешься.\n\n"
                    "Так же по возможности анализируй изображения, если они предоставлены, и детально описывай каждое из них с ссылками"
                    "Если информации недостаточно в предоставленном тексте, честно признай это и не выдавай домыслов. "
                    "Используй только материал из текста, который включен в контексте, и не приводи внешние знания.\n\n"
                    "Пример: 'Согласно исследованиям, климат меняется <a href=\"source://page=5&text=глобальное потепление наступает\">[Стр. 5]</a>.'\n\n"
                    "Пример с изображениями: Согласно исследованиям, график вольт-амперной характеристики диода находится на странице [3], изображении под номером [1], и описывает зависимость выходрного тока от входного напряжения, поданного на диод"
                    """Пример с формулами: Согласно документу, зависимость описывается следующей формулой: <math display="block">
                                    <mi>E</mi>
                                    <mo>=</mo>
                                    <mi>m</mi>
                                    <msup>
                                        <mi>c</mi>
                                        <mn>2</mn>
                                    </msup>
                                    </math>
                                    , которая отображает поведение системы в этой ситуации"""
                    "Ответ выдавай в HTML, и только ответ на задачу (не более). Не надо говорить 'этот HTML код выполняет то-то то-то' и такое прочее. Убедись в правильном формате кода, чтобы сообщение было корректно показано пользователю."

                )
            }
            
            # Пользовательское сообщение с текстом
            user_message_image = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Текст предоставлен ниже:\n{text}\n\nЗадача: {query}"
                    },
                    *[
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{i}"}
                        }
                        for i in images
                    ]
                ]
            }

            print(f"Итоговое сообщение: {user_message_image}")
            # Собираем messages: система + история + текущее сообщение
            messages = [system_message] + self.chat_history + [user_message_image]
            
            response = await self.async_client.chat.completions.create(
                model=modelID,
                messages=messages,
                max_completion_tokens=32768,
            )
            self.add_to_history("user", user_message_image["content"])
            self.add_to_history("assistant", response.choices[0].message.content)
            print(response)
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
    
