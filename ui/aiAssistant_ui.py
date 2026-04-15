from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QTextEdit,
    QComboBox,
    QSplitter,
    QGroupBox,
    QLabel,
    QScrollArea,
    QSpacerItem,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette
from ai_client import AIClient
import asyncio
import re
from urllib.parse import unquote
from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot, QThread, Signal, Qt

class MessageBubble(QWidget):
    """Виджет отдельного сообщения в стиле мессенджера."""
    sourceClicked = Signal(int, str)

    def __init__(self, sender, message, is_user, is_dark):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 5, 0, 5)
        main_layout.setSpacing(2)
        
        # Контейнер для выравнивания по горизонтали
        bubble_container = QHBoxLayout()
        bubble_container.setContentsMargins(0, 0, 0, 0)
        
        # Тело сообщения (бабл)
        self.bubble = QLabel(message)
        self.bubble.setWordWrap(True)
        self.bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.bubble.linkActivated.connect(self.OnLinkActivated)
        # Ограничиваем ширину бабла (примерно 80% от ширины панели)
        self.bubble.setMaximumWidth(350) 
        
        # Заголовок (имя отправителя)
        self.header = QLabel(sender)
        self.header.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold;")
        
        self.update_style(is_user, is_dark)
        
        if is_user:
            bubble_container.addStretch(1)
            bubble_container.addWidget(self.bubble)
            main_layout.addWidget(self.header, 0, Qt.AlignmentFlag.AlignRight)
            main_layout.addLayout(bubble_container)
            self.header.setContentsMargins(0, 0, 10, 0)
        else:
            bubble_container.addWidget(self.bubble)
            bubble_container.addStretch(1)
            main_layout.addWidget(self.header, 0, Qt.AlignmentFlag.AlignLeft)
            main_layout.addLayout(bubble_container)
            self.header.setContentsMargins(10, 0, 0, 0)

    def OnLinkActivated(self, link):
        """Обработка нажатия на ссылку вида source://page=5&text=фрагмент"""
        if link.startswith("source://"):
            try:
                # Извлекаем параметры из ссылки
                params = link[len("source://"):].split("&")
                page = 0
                text = ""
                for p in params:
                    if p.startswith("page="):
                        page = int(p.split("=")[1]) - 1 # Переводим в 0-based
                    elif p.startswith("text="):
                        text = unquote(p.split("=")[1])
                
                self.sourceClicked.emit(page, text)
            except Exception as e:
                print(f"Ошибка при обработке ссылки: {e}")

    def update_style(self, is_user, is_dark, fs=13):
        if is_user:
            bg_color = "#007acc"
            text_color = "white"
            link_color = "#e0e0e0" # Светло-серый для ссылок на синем фоне
            radius = "12px 12px 2px 12px"
            border = "none"
        else:
            if is_dark:
                bg_color = "#2d2d2d"
                text_color = "#d4d4d4"
                link_color = "#E548DD" # Светло-фиолетовый для темной темы
                border = "1px solid #3c3c3c"
            else:
                bg_color = "#f1f1f1"
                text_color = "#333333"
                link_color = "#005a92" # Темно-синий для светлой темы
                border = "1px solid #e0e0e0"
            radius = "12px 12px 12px 2px"
            
        self.bubble.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 12px;
                border: {border};
                padding: 8px 12px;
                font-size: {fs}px;
                font-weight: bold;
            }}
        """)
        
        # Установка цвета ссылок через палитру (т.к. QLabel не поддерживает CSS селектор 'a')
        palette = self.bubble.palette()
        palette.setColor(QPalette.ColorRole.Link, QColor(link_color))
        palette.setColor(QPalette.ColorRole.LinkVisited, QColor(link_color))
        self.bubble.setPalette(palette)
        self.header.setStyleSheet(f"color: #888888; font-size: {fs - 3}px; font-weight: bold;")

class LoadingBubble(QWidget):
    """Виджет индикатора загрузки (анимация трех точек)."""
    def __init__(self, is_dark):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 5, 0, 5)
        main_layout.setSpacing(2)
        
        # Контейнер для выравнивания по горизонтали (всегда слева для ИИ)
        bubble_container = QHBoxLayout()
        bubble_container.setContentsMargins(0, 0, 0, 0)
        
        # Тело сообщения (бабл)
        self.bubble = QLabel("печатает .")
        self.bubble.setFixedSize(100, 35)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Заголовок
        self.header = QLabel("ИИ")
        self.header.setStyleSheet("color: #888888; font-size: 10px; font-weight: bold;")
        self.header.setContentsMargins(10, 0, 0, 0)
        
        self.update_style(is_dark)
        
        bubble_container.addWidget(self.bubble)
        bubble_container.addStretch(1)
        
        main_layout.addWidget(self.header, 0, Qt.AlignmentFlag.AlignLeft)
        main_layout.addLayout(bubble_container)

        # Анимация точек
        self.dot_count = 1
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(500)

    def animate(self):
        self.dot_count = (self.dot_count % 3) + 1
        self.bubble.setText("печатает " + "." * self.dot_count)

    def update_style(self, is_dark, fs=13):
        if is_dark:
            bg_color = "#2d2d2d"
            text_color = "#d4d4d4"
            border = "1px solid #3c3c3c"
        else:
            bg_color = "#f1f1f1"
            text_color = "#333333"
            border = "1px solid #e0e0e0"
            
        self.bubble.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 12px;
                border: {border};
                padding: 5px 10px;
                font-size: {fs}px;
                font-weight: bold;
            }}
        """)
        self.header.setStyleSheet(f"color: #888888; font-size: {fs - 3}px; font-weight: bold;")

class GetModelsWorker(QThread):
    """Worker thread."""

    completed = Signal(list)

    def __init__(self, client) -> None:
        super().__init__()
        self.client = client
       
        

    @Slot()
    def run(self):
        modelList = asyncio.run(self.client.GetModelsAsync())
        self.completed.emit(modelList)
        

class GetResponceWorker(QThread):
    """Worker thread."""

    completed = Signal(str)

    def __init__(self, client, query, text, model, use_rag=True):
        super().__init__()
        self.client = client
        self.query = query
        self.text = text
        self.model = model
        self.use_rag = use_rag

    @Slot()
    def run(self):
        is_loading = (self.text == "Текст загружается, подождите...")
        current_text = "[Текст текущей страницы еще загружается и пока недоступен]" if is_loading else self.text
        
        # 1. Парсим запрос на наличие указаний конкретных страниц
        # Поддерживаемые форматы: "стр 5", "страница 10", "стр. 12-15", "страницы 1, 3, 5"
        page_numbers = []
        
        # Поиск диапазонов: "12-15"
        range_matches = re.findall(r'(?:стр|страниц[аеы])\.?\s*(\d+)\s*-\s*(\d+)', self.query, re.IGNORECASE)
        for start, end in range_matches:
            page_numbers.extend(range(int(start), int(end) + 1))
            
        # Поиск отдельных страниц: "стр 5", "стр. 10"
        single_matches = re.findall(r'(?:стр|страниц[аеы])\.?\s*(\d+)(?!\s*-)', self.query, re.IGNORECASE)
        for p in single_matches:
            if int(p) not in page_numbers:
                page_numbers.append(int(p))

        context = ""
        rag_available = self.client.rag_manager.vector_store is not None
        
        if self.use_rag and rag_available:
            # Если пользователь указал конкретные страницы, ищем только по ним
            if page_numbers:
                relevant_docs = self.client.rag_manager.search(self.query, k=10, page_numbers=page_numbers)
                context_header = f"\n--- ИНФОРМАЦИЯ ИЗ ВЫБРАННЫХ СТРАНИЦ ({', '.join(map(str, sorted(page_numbers)))}) ---\n"
            else:
                # Если не указал, ищем по всей книге в равной степени
                relevant_docs = self.client.rag_manager.search(self.query, k=10)
                context_header = "\n--- НАЙДЕННАЯ ИНФОРМАЦИЯ ИЗ ВСЕЙ КНИГИ (RAG) ---\n"
            
            if relevant_docs:
                rag_context = context_header
                for doc in relevant_docs:
                    page_num = doc.metadata.get("page", 0) + 1
                    rag_context += f"\n[Страница {page_num}]: {doc.page_content}\n"
                
                # Добавляем также текст текущей страницы для контекста "здесь и сейчас"
                context = f"ТЕКУЩАЯ СТРАНИЦА:\n{current_text}\n{rag_context}"
            else:
                context = f"ТЕКУЩАЯ СТРАНИЦА:\n{current_text}\n(По вашему запросу ничего не найдено в других частях книги)"
        else:
            context = f"ТЕКУЩАЯ СТРАНИЦА:\n{current_text}"

        resp = asyncio.run(self.client.CreateResponceAsync(self.model, self.query, context))
        self.completed.emit(resp)

class AIAssistantPanel(QWidget):
    sourceClicked = Signal(int, str)

    def __init__(self, client: AIClient, readmethod, parent=None, ):
        super().__init__(parent)

        #Инициализация всего прочего
        self.client = client
        self.threadPool = QThreadPool()
        self.readText = readmethod
        self.promptWorker = None
        self.modelUpdateWorker = None
        self.isDarkMode = True
        self.loadingBubble = None

        #Инициализация GUI

        #Окно выбора модели
        self.modelSelector = QComboBox()
        self.modelSelector.setPlaceholderText("Загрузка моделей...")
        self.modelSelector.setStyleSheet("""
            QComboBox {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px 10px;
                background-color: #3c3c3c;
                color: #cccccc;
                min-height: 24px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #cccccc;
            }
            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #454545;
                selection-background-color: #094771;
                outline: 0px;
            }
        """)
        

        #Вывод модели (История чата)
        self.chatWindow = QScrollArea()
        self.chatWindow.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chatWindow.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chatWindow.setWidgetResizable(True)
        
        # Контейнер для сообщений
        self.chatHistoryWidget = QWidget()
        self.chatHistoryLayout = QVBoxLayout(self.chatHistoryWidget)
        self.chatHistoryLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chatHistoryLayout.setContentsMargins(10, 10, 10, 10)
        self.chatHistoryLayout.setSpacing(10)
        
        self.chatWindow.setWidget(self.chatHistoryWidget)
        self.chatWindow.setStyleSheet("border: 1px solid #3c3c3c; border-radius: 4px; background-color: #1e1e1e;")

        #Нижняя панель ввода
        self.inputContainer = QWidget()
        self.inputLayout = QHBoxLayout(self.inputContainer)
        self.inputLayout.setContentsMargins(0, 5, 0, 5)
        self.inputLayout.setSpacing(10)

        #Окно промпта
        self.promptWindow = QTextEdit()
        self.promptWindow.setPlaceholderText("Спросите что-нибудь...")
        self.promptWindow.setFixedHeight(40)
        self.promptWindow.setStyleSheet("""
            QTextEdit {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 8px 40px 8px 10px;
                background-color: #3c3c3c;
                color: #cccccc;
                font-size: 13px;
            }
            QTextEdit:focus {
                border: 1px solid #007acc;
            }
        """)

        #Кнопка на отправку промпта
        self.promptEnterButton = QPushButton(self.promptWindow)
        self.promptEnterButton.clicked.connect(self.OnPromptEnderButtonClicked)
        self.promptEnterButton.setText("↑")
        self.promptEnterButton.setFixedSize(28, 28)
        self.promptEnterButton.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #0062a3;
            }
            QPushButton:pressed {
                background-color: #005a92;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """)

        # Для позиционирования кнопки внутри текстового поля
        self.promptWindow.installEventFilter(self)

        self.inputLayout.addWidget(self.promptWindow)

        #Кнопка на обновление модели
        self.refreshModelButton = QPushButton()
        self.refreshModelButton.clicked.connect(self.OnRefreshModelButtonClicked)
        self.refreshModelButton.setText("↻")
        self.refreshModelButton.setFixedSize(30, 30)
        self.refreshModelButton.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                border: 1px solid #007acc;
            }
        """)

        #Кнопка сброса чата
        self.clearChatButton = QPushButton()
        self.clearChatButton.clicked.connect(self.OnClearChatButtonClicked)
        self.clearChatButton.setText("🗑")
        self.clearChatButton.setFixedSize(30, 30)
        self.clearChatButton.setStyleSheet("""
            QPushButton {
                background-color: #3c3c3c;
                color: #cccccc;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                border: 1px solid #007acc;
            }
        """)


        #Инициализация окна с промптами
        self.chatLayoutWidget = QWidget()
        self.chatLayout = QVBoxLayout()
        self.chatLayout.setContentsMargins(0, 0, 0, 0)
        self.chatLayout.setSpacing(10)
        self.chatLayout.addWidget(self.chatWindow)
        self.chatLayout.addWidget(self.inputContainer)
        self.chatLayout.setStretch(0, 1) # Чат занимает все место
        self.chatLayout.setStretch(1, 0) # Панель ввода внизу
        self.chatLayoutWidget.setLayout(self.chatLayout)


        #Верхняя панель выбора модели
        self.modelHeader = QWidget()
        self.modelHeaderLayout = QHBoxLayout(self.modelHeader)
        self.modelHeaderLayout.setContentsMargins(0, 0, 0, 5)
        self.modelHeaderLayout.setSpacing(8)
        self.modelHeaderLayout.addWidget(self.modelSelector, 1)
        self.modelHeaderLayout.addWidget(self.refreshModelButton)
        self.modelHeaderLayout.addWidget(self.clearChatButton)

        # Подключаем сигнал изменения модели
        self.modelSelector.currentIndexChanged.connect(self.OnModelIndexChanged)

        #Основной layout панели
        self.box = QVBoxLayout()
        self.box.setContentsMargins(15, 15, 15, 15)
        self.box.setSpacing(15)
        self.box.addWidget(self.modelHeader)
        self.box.addWidget(self.chatLayoutWidget)
        self.setLayout(self.box)
        self.box.setStretch(0, 0)
        self.box.setStretch(1, 1)

        # Автоматическая загрузка моделей
        self.OnRefreshModelButtonClicked()
        
    def eventFilter(self, obj, event):
        if obj == self.promptWindow:
            if event.type() == event.Type.Resize:
                # Позиционируем кнопку в правом углу текстового поля
                rect = self.promptWindow.rect()
                self.promptEnterButton.move(rect.width() - 40, (rect.height() - 32) // 2)
            elif event.type() == event.Type.KeyPress:
                # Отправка по Enter, перенос строки по Shift+Enter
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                        self.OnPromptEnderButtonClicked()
                        return True
        return super().eventFilter(obj, event)

    def StopAllWorkers(self):
        """Останавливает все активные воркеры перед закрытием приложения."""
        self.HideLoadingAnimation()
        if self.promptWorker and self.promptWorker.isRunning():
            self.promptWorker.quit()
            self.promptWorker.wait()
        
        if self.modelUpdateWorker and self.modelUpdateWorker.isRunning():
            self.modelUpdateWorker.quit()
            self.modelUpdateWorker.wait()

    def OnRefreshModelButtonClicked(self):
        if not self.client:
            return
        if self.modelUpdateWorker and self.modelUpdateWorker.isRunning():
            return
        self.modelUpdateWorker = GetModelsWorker(self.client)
        self.modelUpdateWorker.completed.connect(self.OnModelReceived)
        self.modelUpdateWorker.start()
        

    def OnPromptEnderButtonClicked(self):
        query = self.promptWindow.toPlainText().strip()
        if not query:
            return
            
        if self.promptWorker and self.promptWorker.isRunning():
            return

        modelId = self.GetSelectedModel()
        if not modelId:
            self.AppendToChat("Система", "Пожалуйста, выберите модель.")
            return
        
        # Добавляем сообщение пользователя в чат
        self.AppendToChat("Вы", query)
        # Добавляем в историю
        self.client.add_to_history("user", query)
        self.promptWindow.clear()
        
        # Показываем анимацию загрузки
        self.ShowLoadingAnimation()
        
        text = self.readText()
        is_loading = (text == "Текст загружается, подождите...")
        rag_available = self.client.rag_manager.vector_store is not None

        if is_loading and not rag_available:
            self.HideLoadingAnimation()
            self.AppendToChat("Система", "Текст страницы еще не готов и поиск по книге недоступен. Пожалуйста, подождите немного.")
            return
            
        self.promptWorker = GetResponceWorker(client=self.client, model=modelId, query=query,
                                              text=text)
        self.promptWorker.completed.connect(self.OnResponceReceived)
        self.promptWorker.start()

    def OnResponceReceived(self, resp):
        # Скрываем анимацию загрузки
        self.HideLoadingAnimation()
        # Добавляем ответ ИИ в чат
        self.AppendToChat("ИИ", resp)
        # Добавляем в историю
        self.client.add_to_history("assistant", resp)

    def ShowLoadingAnimation(self):
        """Показывает анимацию 'ИИ думает'."""
        if self.loadingBubble:
            return
        self.loadingBubble = LoadingBubble(self.isDarkMode)
        if hasattr(self, 'currentFontSize'):
            self.loadingBubble.update_style(self.isDarkMode, self.currentFontSize - 1)
        self.chatHistoryLayout.addWidget(self.loadingBubble)
        self.ScrollToBottom()

    def HideLoadingAnimation(self):
        """Удаляет анимацию загрузки."""
        if self.loadingBubble:
            self.chatHistoryLayout.removeWidget(self.loadingBubble)
            self.loadingBubble.deleteLater()
            self.loadingBubble = None

    def ScrollToBottom(self):
        """Прокручивает чат в самый низ."""
        QTimer.singleShot(50, lambda: self.chatWindow.verticalScrollBar().setValue(
            self.chatWindow.verticalScrollBar().maximum()
        ))

    def AppendToChat(self, sender, message):
        is_user = (sender == "Вы")
        
        # Создаем виджет сообщения (бабл)
        bubble = MessageBubble(sender, message, is_user, self.isDarkMode)
        # Подключаем сигнал нажатия на источник
        bubble.sourceClicked.connect(self.sourceClicked.emit)
        
        # Применяем текущий размер шрифта
        if hasattr(self, 'currentFontSize'):
            bubble.update_style(is_user, self.isDarkMode, self.currentFontSize - 1)
        self.chatHistoryLayout.addWidget(bubble)
        
        # Прокрутка вниз
        self.ScrollToBottom()

    def OnModelReceived(self, models_info):
        if isinstance(models_info, list):
            self.UpdateModelList(models_info)
        else:
            # Если пришла ошибка
            self.UpdateModelList([{"id": f"Ошибка: {str(models_info)}", "is_serverless": False}])

    def UpdateModelList(self, models_info):
        self.modelSelector.clear()
        
        for model in models_info:
            m_id = model.get('id', 'Unknown')
            is_serverless = model.get('is_serverless', False)
            is_recommended = model.get('is_recommended', False)
            
            # Сохраняем оригинальный ID в UserRole для корректной работы API
            self.modelSelector.addItem(m_id, userData=m_id)
            index = self.modelSelector.count() - 1
            
            display_text = m_id
            
            # Если модель рекомендованная, добавляем звезду и красим в золотой
            if is_recommended:
                display_text = f"★ {display_text}"
                self.modelSelector.setItemData(index, QColor("#ffd700"), Qt.ItemDataRole.ForegroundRole) # Gold
            # Если модель serverless, красим её в бирюзовый (если не рекомендованная)
            elif is_serverless:
                self.modelSelector.setItemData(index, QColor("#4ec9b0"), Qt.ItemDataRole.ForegroundRole)
            
            if is_serverless:
                display_text = f"{display_text} (Serverless)"
                
            self.modelSelector.setItemText(index, display_text)
            
        # Устанавливаем первую модель (она будет самой подходящей из рекомендованных)
        if self.modelSelector.count() > 0:
            self.modelSelector.setCurrentIndex(0)
            self.client.SetCurrentModelID(0)

    def OnModelIndexChanged(self, index):
        if self.client and index >= 0:
            self.client.SetCurrentModelID(index)

    def GetSelectedModel(self):
        # Возвращаем оригинальный ID из userData
        return self.modelSelector.currentData()
    
    def OnClearChatButtonClicked(self):
        """Очищает историю чата и удаляет все сообщения из UI."""
        # Очищаем историю в клиенте
        self.client.clear_history()
        
        # Очищаем все виджеты из chatHistoryLayout
        while self.chatHistoryLayout.count():
            item = self.chatHistoryLayout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # Скрываем анимацию загрузки, если она активна
        self.HideLoadingAnimation()
    
    def SetDarkMode(self, is_dark, fs=14):
        self.isDarkMode = is_dark
        self.currentFontSize = fs
        common_style = f"font-size: {fs}px;"
        
        # Обновляем все существующие сообщения в чате
        for i in range(self.chatHistoryLayout.count()):
            widget = self.chatHistoryLayout.itemAt(i).widget()
            if isinstance(widget, MessageBubble):
                is_user = (widget.header.text() == "Вы")
                widget.update_style(is_user, is_dark, fs - 1)
            elif isinstance(widget, LoadingBubble):
                widget.update_style(is_dark, fs - 1)

        if is_dark:
            self.modelSelector.setStyleSheet(f"""
                QComboBox {{
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    padding: 4px 10px;
                    background-color: #3c3c3c;
                    color: #cccccc;
                    min-height: 24px;
                    {common_style}
                    font-size: {fs - 2}px;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: none;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #cccccc;
                }}
                QComboBox QAbstractItemView {{
                    background-color: #252526;
                    color: #cccccc;
                    border: 1px solid #454545;
                    selection-background-color: #094771;
                    outline: 0px;
                    {common_style}
                    font-size: {fs - 2}px;
                }}
            """)
            self.chatWindow.setStyleSheet(f"border: 1px solid #3c3c3c; border-radius: 4px; background-color: #1e1e1e;")
            self.chatHistoryWidget.setStyleSheet("background-color: #1e1e1e;")
            self.promptWindow.setStyleSheet(f"""
                QTextEdit {{
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    padding: 8px 40px 8px 10px;
                    background-color: #3c3c3c;
                    color: #cccccc;
                    {common_style}
                    font-size: {fs - 1}px;
                }}
                QTextEdit:focus {{
                    border: 1px solid #007acc;
                }}
            """)
            self.promptEnterButton.setStyleSheet(f"""
                QPushButton {{
                    background-color: #007acc;
                    color: white;
                    border-radius: 4px;
                    font-weight: bold;
                    border: none;
                    {common_style}
                    font-size: {fs + 2}px;
                }}
                QPushButton:hover {{
                    background-color: #0062a3;
                }}
                QPushButton:pressed {{
                    background-color: #005a92;
                }}
                QPushButton:disabled {{
                    background-color: #333333;
                    color: #666666;
                }}
            """)
            self.refreshModelButton.setStyleSheet(f"""
                QPushButton {{
                    background-color: #3c3c3c;
                    color: #cccccc;
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    {common_style}
                }}
                QPushButton:hover {{
                    background-color: #4d4d4d;
                    border: 1px solid #007acc;
                }}
            """)
        else:
            self.modelSelector.setStyleSheet(f"""
                QComboBox {{
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px 10px;
                    background-color: #ffffff;
                    color: #333333;
                    min-height: 24px;
                    {common_style}
                    font-size: {fs - 2}px;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: none;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #666666;
                }}
                QComboBox QAbstractItemView {{
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    selection-background-color: #0078d4;
                    selection-color: #ffffff;
                    outline: 0px;
                    {common_style}
                    font-size: {fs - 2}px;
                }}
            """)
            self.chatWindow.setStyleSheet(f"border: 1px solid #dddddd; border-radius: 4px; background-color: #ffffff;")
            self.chatHistoryWidget.setStyleSheet("background-color: #ffffff;")
            self.promptWindow.setStyleSheet(f"""
                QTextEdit {{
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 8px 40px 8px 10px;
                    background-color: #f5f5f5;
                    color: #333333;
                    {common_style}
                    font-size: {fs - 1}px;
                }}
                QTextEdit:focus {{
                    border: 1px solid #0078d4;
                }}
            """)
            self.promptEnterButton.setStyleSheet(f"""
                QPushButton {{
                    background-color: #0078d4;
                    color: white;
                    border-radius: 4px;
                    font-weight: bold;
                    border: none;
                    {common_style}
                    font-size: {fs + 2}px;
                }}
                QPushButton:hover {{
                    background-color: #0062a3;
                }}
                QPushButton:pressed {{
                    background-color: #005a92;
                }}
                QPushButton:disabled {{
                    background-color: #eeeeee;
                    color: #999999;
                }}
            """)
            self.refreshModelButton.setStyleSheet(f"""
                QPushButton {{
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    {common_style}
                }}
                QPushButton:hover {{
                    background-color: #f5f5f5;
                    border: 1px solid #0078d4;
                }}
            """)
    
    


    

