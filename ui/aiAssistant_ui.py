from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QTextEdit,
    QComboBox,
    QLabel,
    QScrollArea,
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
    sourceClicked = Signal(int, str)

    def __init__(self, sender, message, is_user, is_dark):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(3)

        bubble_container = QHBoxLayout()
        bubble_container.setContentsMargins(0, 0, 0, 0)

        self.bubble = QLabel(message)
        self.bubble.setWordWrap(True)
        self.bubble.setTextFormat(Qt.TextFormat.RichText)
        self.bubble.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.bubble.setOpenExternalLinks(False)
        self.bubble.linkActivated.connect(self.OnLinkActivated)
        self.bubble.setMaximumWidth(380)

        self.header = QLabel(sender)
        self.header.setStyleSheet("color: #475569; font-size: 10px; font-weight: 600;")

        self.update_style(is_user, is_dark)

        if is_user:
            bubble_container.addStretch(1)
            bubble_container.addWidget(self.bubble)
            main_layout.addWidget(self.header, 0, Qt.AlignmentFlag.AlignRight)
            main_layout.addLayout(bubble_container)
            self.header.setContentsMargins(0, 0, 4, 0)
        else:
            bubble_container.addWidget(self.bubble)
            bubble_container.addStretch(1)
            main_layout.addWidget(self.header, 0, Qt.AlignmentFlag.AlignLeft)
            main_layout.addLayout(bubble_container)
            self.header.setContentsMargins(4, 0, 0, 0)

    def OnLinkActivated(self, link):
        if link.startswith("source://"):
            try:
                params = link[len("source://"):].split("&")
                page = 0
                text = ""
                for p in params:
                    if p.startswith("page="):
                        page = int(p.split("=")[1]) - 1
                    elif p.startswith("text="):
                        text = unquote(p.split("=")[1])
                self.sourceClicked.emit(page, text)
            except Exception as e:
                print(f"Ошибка при обработке ссылки: {e}")

    def update_style(self, is_user, is_dark, fs=13):
        if is_user:
            self.bubble.setStyleSheet(f"""
                QLabel {{
                    background-color: #1A003A;
                    color: #E8C0FF;
                    border-radius: 4px;
                    border-top-right-radius: 1px;
                    border: 1px solid #CC00FF;
                    padding: 10px 14px;
                    font-size: {fs}px;
                    line-height: 1.5;
                }}
            """)
            palette = self.bubble.palette()
            palette.setColor(QPalette.ColorRole.Link, QColor("#FF80FF"))
            palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#CC80FF"))
            self.bubble.setPalette(palette)
            self.header.setStyleSheet(
                f"color: #CC00FF; font-size: {fs - 3}px; font-weight: 600;"
            )
        else:
            if is_dark:
                self.bubble.setStyleSheet(f"""
                    QLabel {{
                        background-color: #001825;
                        color: #B0D8F0;
                        border-radius: 4px;
                        border-top-left-radius: 1px;
                        border: 1px solid rgba(0,200,255,0.28);
                        padding: 10px 14px;
                        font-size: {fs}px;
                        line-height: 1.5;
                    }}
                """)
                palette = self.bubble.palette()
                palette.setColor(QPalette.ColorRole.Link, QColor("#00C8FF"))
                palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#80E0FF"))
                self.bubble.setPalette(palette)
                self.header.setStyleSheet(
                    f"color: #3A6880; font-size: {fs - 3}px; font-weight: 600;"
                )
            else:
                self.bubble.setStyleSheet(f"""
                    QLabel {{
                        background-color: #F0F8FF;
                        color: #0A1828;
                        border-radius: 4px;
                        border-top-left-radius: 1px;
                        border: 1px solid #90C0E0;
                        padding: 10px 14px;
                        font-size: {fs}px;
                        line-height: 1.5;
                    }}
                """)
                palette = self.bubble.palette()
                palette.setColor(QPalette.ColorRole.Link, QColor("#0055CC"))
                palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#7700CC"))
                self.bubble.setPalette(palette)
                self.header.setStyleSheet(
                    f"color: #6080A0; font-size: {fs - 3}px; font-weight: 600;"
                )


class LoadingBubble(QWidget):
    def __init__(self, is_dark):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 4)
        main_layout.setSpacing(3)

        bubble_container = QHBoxLayout()
        bubble_container.setContentsMargins(0, 0, 0, 0)

        self.bubble = QLabel("печатает .")
        self.bubble.setFixedSize(110, 36)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.header = QLabel("ИИ")
        self.header.setContentsMargins(4, 0, 0, 0)

        self.update_style(is_dark)

        bubble_container.addWidget(self.bubble)
        bubble_container.addStretch(1)

        main_layout.addWidget(self.header, 0, Qt.AlignmentFlag.AlignLeft)
        main_layout.addLayout(bubble_container)

        self.dot_count = 1
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(500)

    def animate(self):
        self.dot_count = (self.dot_count % 3) + 1
        self.bubble.setText("печатает " + "." * self.dot_count)

    def update_style(self, is_dark, fs=13):
        if is_dark:
            self.bubble.setStyleSheet(f"""
                QLabel {{
                    background-color: #001825;
                    color: #00C8FF;
                    border-radius: 4px;
                    border-top-left-radius: 1px;
                    border: 1px solid rgba(0,200,255,0.22);
                    padding: 6px 12px;
                    font-size: {fs}px;
                }}
            """)
            self.header.setStyleSheet(
                f"color: #3A6880; font-size: {fs - 3}px; font-weight: 600;"
            )
        else:
            self.bubble.setStyleSheet(f"""
                QLabel {{
                    background-color: #F0F8FF;
                    color: #4080A0;
                    border-radius: 4px;
                    border-top-left-radius: 1px;
                    border: 1px solid #90C0E0;
                    padding: 6px 12px;
                    font-size: {fs}px;
                }}
            """)
            self.header.setStyleSheet(
                f"color: #6080A0; font-size: {fs - 3}px; font-weight: 600;"
            )


class GetModelsWorker(QThread):
    completed = Signal(list)

    def __init__(self, client) -> None:
        super().__init__()
        self.client = client

    @Slot()
    def run(self):
        modelList = asyncio.run(self.client.GetModelsAsync())
        self.completed.emit(modelList)


class GetResponceWorker(QThread):
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
        current_text = (
            "[Текст текущей страницы еще загружается и пока недоступен]"
            if is_loading else self.text
        )

        page_numbers = []

        range_matches = re.findall(
            r'(?:стр|страниц[аеы])\.?\s*(\d+)\s*-\s*(\d+)', self.query, re.IGNORECASE
        )
        for start, end in range_matches:
            page_numbers.extend(range(int(start), int(end) + 1))

        single_matches = re.findall(
            r'(?:стр|страниц[аеы])\.?\s*(\d+)(?!\s*-)', self.query, re.IGNORECASE
        )
        for p in single_matches:
            if int(p) not in page_numbers:
                page_numbers.append(int(p))

        context = ""
        rag_available = self.client.rag_manager.vector_store is not None

        imgs = []
        results = []

        if self.use_rag and rag_available:
            if page_numbers:
                relevant_docs = self.client.rag_manager.multi_query_search(
                    self.query, k=4, page_numbers=page_numbers, use_multi_query=True
                )
                results = self.client.image_indexer.multi_query_search(self.query, k=3)
                context_header = (
                    f"\n--- ИНФОРМАЦИЯ ИЗ ВЫБРАННЫХ СТРАНИЦ "
                    f"({', '.join(map(str, sorted(page_numbers)))}) ---\n"
                )
            else:
                relevant_docs = self.client.rag_manager.multi_query_search(
                    self.query, k=4, use_multi_query=True
                )
                results = self.client.image_indexer.multi_query_search(self.query, k=3)
                context_header = "\n--- НАЙДЕННАЯ ИНФОРМАЦИЯ ИЗ ВСЕЙ КНИГИ (RAG) ---\n"

            if relevant_docs:
                rag_context = context_header
                for doc in relevant_docs:
                    page_num = doc.metadata.get("page", 0) + 1
                    rag_context += f"\n[Страница {page_num}]: {doc.page_content}\n"
                context = f"ТЕКУЩАЯ СТРАНИЦА:\n{current_text}\n{rag_context}"
            else:
                context = (
                    f"ТЕКУЩАЯ СТРАНИЦА:\n{current_text}\n"
                    "(По вашему запросу ничего не найдено в других частях книги)"
                )
        else:
            context = f"ТЕКУЩАЯ СТРАНИЦА:\n{current_text}"

        c = 1
        for meta, score in results:
            image_data = meta['image']
            imgs.append(image_data)
            context += f"Информация о изображении {c} -> Местоположение:{meta['page']}; Уверенность: {score}"
            c += 1

        resp = asyncio.run(
            self.client.CreateResponceAsync(
                modelID=self.model, query=self.query, text=context, images=imgs
            )
        )
        print(resp)
        self.completed.emit(resp)


class AIAssistantPanel(QWidget):
    sourceClicked = Signal(int, str)

    def __init__(self, client: AIClient, readmethod, parent=None):
        super().__init__(parent)

        self.client = client
        self.threadPool = QThreadPool()
        self.readText = readmethod
        self.promptWorker = None
        self.modelUpdateWorker = None
        self.isDarkMode = True
        self.loadingBubble = None

        # Model selector
        self.modelSelector = QComboBox()
        self.modelSelector.setPlaceholderText("Загрузка моделей...")
        self.modelSelector.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.modelSelector.setStyleSheet(self._model_selector_style(dark=True))

        # Chat scroll area
        self.chatWindow = QScrollArea()
        self.chatWindow.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chatWindow.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chatWindow.setWidgetResizable(True)
        self.chatWindow.setFrameShape(QScrollArea.Shape.NoFrame)

        self.chatHistoryWidget = QWidget()
        self.chatHistoryWidget.setObjectName("chatHistoryWidget")
        self.chatHistoryLayout = QVBoxLayout(self.chatHistoryWidget)
        self.chatHistoryLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chatHistoryLayout.setContentsMargins(8, 12, 8, 12)
        self.chatHistoryLayout.setSpacing(8)

        self.chatWindow.setWidget(self.chatHistoryWidget)
        self.chatWindow.setStyleSheet(
            "QScrollArea { background-color: transparent; border: none; }"
        )

        # Input area
        self.inputContainer = QWidget()
        self.inputContainer.setObjectName("inputContainer")
        self.inputLayout = QHBoxLayout(self.inputContainer)
        self.inputLayout.setContentsMargins(0, 6, 0, 0)
        self.inputLayout.setSpacing(8)

        # Prompt text edit
        self.promptWindow = QTextEdit()
        self.promptWindow.setPlaceholderText("Спросите что-нибудь...")
        self.promptWindow.setFixedHeight(44)
        self.promptWindow.setStyleSheet(self._prompt_style(dark=True))

        # Send button — positioned inside prompt field
        self.promptEnterButton = QPushButton(self.promptWindow)
        self.promptEnterButton.clicked.connect(self.OnPromptEnderButtonClicked)
        self.promptEnterButton.setText("↑")
        self.promptEnterButton.setFixedSize(30, 30)
        self.promptEnterButton.setStyleSheet(self._send_button_style(dark=True))

        self.promptWindow.installEventFilter(self)
        self.inputLayout.addWidget(self.promptWindow)

        # Refresh button
        self.refreshModelButton = QPushButton()
        self.refreshModelButton.clicked.connect(self.OnRefreshModelButtonClicked)
        self.refreshModelButton.setText("↺")
        self.refreshModelButton.setFixedSize(32, 32)
        self.refreshModelButton.setStyleSheet(self._icon_button_style(dark=True))

        # Clear chat button
        self.clearChatButton = QPushButton()
        self.clearChatButton.clicked.connect(self.OnClearChatButtonClicked)
        self.clearChatButton.setText("✕")
        self.clearChatButton.setFixedSize(32, 32)
        self.clearChatButton.setStyleSheet(self._icon_button_style(dark=True))

        # Chat layout wrapper
        self.chatLayoutWidget = QWidget()
        self.chatLayout = QVBoxLayout()
        self.chatLayout.setContentsMargins(0, 0, 0, 0)
        self.chatLayout.setSpacing(8)
        self.chatLayout.addWidget(self.chatWindow)
        self.chatLayout.addWidget(self.inputContainer)
        self.chatLayout.setStretch(0, 1)
        self.chatLayout.setStretch(1, 0)
        self.chatLayoutWidget.setLayout(self.chatLayout)

        # Header with model selector and action buttons
        self.modelHeader = QWidget()
        self.modelHeader.setObjectName("modelHeader")
        self.modelHeaderLayout = QHBoxLayout(self.modelHeader)
        self.modelHeaderLayout.setContentsMargins(0, 0, 0, 8)
        self.modelHeaderLayout.setSpacing(6)
        self.modelHeaderLayout.addWidget(self.modelSelector, 1)
        self.modelHeaderLayout.addWidget(self.refreshModelButton)
        self.modelHeaderLayout.addWidget(self.clearChatButton)

        self.modelSelector.currentIndexChanged.connect(self.OnModelIndexChanged)

        # Main layout
        self.box = QVBoxLayout()
        self.box.setContentsMargins(14, 14, 14, 14)
        self.box.setSpacing(0)
        self.box.addWidget(self.modelHeader, 0)
        self.box.addWidget(self.chatLayoutWidget, 1)
        self.setLayout(self.box)

        self._applyPanelBackground(dark=True)
        self.OnRefreshModelButtonClicked()

    # ── Style helpers ──────────────────────────────────────────────────────

    def _model_selector_style(self, dark: bool, fs: int = 12) -> str:
        if dark:
            return f"""
                QComboBox {{
                    border: 1px solid rgba(0,200,255,0.20);
                    border-radius: 2px;
                    padding: 5px 10px;
                    background-color: rgba(0,200,255,0.05);
                    color: #6888A8;
                    min-height: 28px;
                    font-size: {fs}px;
                }}
                QComboBox:hover {{
                    border: 1px solid rgba(0,200,255,0.40);
                    background-color: rgba(0,200,255,0.10);
                    color: #A0D8F0;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 22px;
                    border-left: none;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #3A6880;
                    margin-right: 8px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: #0E0E24;
                    color: #6888A8;
                    border: 1px solid rgba(0,200,255,0.22);
                    border-radius: 2px;
                    selection-background-color: rgba(0,200,255,0.18);
                    selection-color: #C0F0FF;
                    outline: 0px;
                    padding: 4px;
                    font-size: {fs}px;
                }}
            """
        else:
            return f"""
                QComboBox {{
                    border: 1px solid #90A8C0;
                    border-radius: 2px;
                    padding: 5px 10px;
                    background-color: #F8F8F0;
                    color: #304050;
                    min-height: 28px;
                    font-size: {fs}px;
                }}
                QComboBox:hover {{
                    border: 1px solid #5080B0;
                    background-color: #F0F8FF;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 22px;
                    border-left: none;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #6080A0;
                    margin-right: 8px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: #F0F0E8;
                    color: #1A2A3A;
                    border: 1px solid #90A8C0;
                    border-radius: 2px;
                    selection-background-color: rgba(0,80,180,0.12);
                    selection-color: #0040AA;
                    outline: 0px;
                    padding: 4px;
                    font-size: {fs}px;
                }}
            """

    def _prompt_style(self, dark: bool, fs: int = 13) -> str:
        if dark:
            return f"""
                QTextEdit {{
                    border: 1px solid rgba(0,200,255,0.20);
                    border-radius: 2px;
                    padding: 10px 46px 10px 14px;
                    background-color: rgba(0,200,255,0.04);
                    color: #B0D8F0;
                    font-size: {fs}px;
                }}
                QTextEdit:focus {{
                    border: 1px solid rgba(0,200,255,0.60);
                    background-color: rgba(0,200,255,0.07);
                }}
            """
        else:
            return f"""
                QTextEdit {{
                    border: 1px solid #90A8C0;
                    border-radius: 2px;
                    padding: 10px 46px 10px 14px;
                    background-color: #F8F8F0;
                    color: #0A1828;
                    font-size: {fs}px;
                }}
                QTextEdit:focus {{
                    border: 1px solid #0055CC;
                    background-color: rgba(0,80,180,0.04);
                }}
            """

    def _send_button_style(self, dark: bool) -> str:
        if dark:
            return """
                QPushButton {
                    background-color: #CC00FF;
                    color: #FFE0FF;
                    border-radius: 2px;
                    font-size: 16px;
                    font-weight: bold;
                    border: 1px solid #FF40FF;
                }
                QPushButton:hover {
                    background-color: #EE00FF;
                    border: 1px solid #FF80FF;
                }
                QPushButton:pressed {
                    background-color: #AA00CC;
                }
                QPushButton:disabled {
                    background-color: rgba(0,200,255,0.05);
                    color: rgba(0,200,255,0.20);
                    border: 1px solid rgba(0,200,255,0.10);
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #0055CC;
                    color: #FFFFFF;
                    border-radius: 2px;
                    font-size: 16px;
                    font-weight: bold;
                    border: 1px solid #0070FF;
                }
                QPushButton:hover {
                    background-color: #0070FF;
                }
                QPushButton:pressed {
                    background-color: #0040AA;
                }
                QPushButton:disabled {
                    background-color: rgba(0,80,180,0.08);
                    color: rgba(0,80,180,0.30);
                }
            """

    def _icon_button_style(self, dark: bool) -> str:
        if dark:
            return """
                QPushButton {
                    background-color: rgba(0,200,255,0.05);
                    color: #3A6880;
                    border: 1px solid rgba(0,200,255,0.12);
                    border-radius: 2px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(0,200,255,0.14);
                    border: 1px solid rgba(0,200,255,0.35);
                    color: #00C8FF;
                }
                QPushButton:pressed {
                    background-color: rgba(0,200,255,0.25);
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #F8F8F0;
                    color: #6080A0;
                    border: 1px solid #90A8C0;
                    border-radius: 2px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: rgba(0,80,180,0.08);
                    border: 1px solid #0055CC;
                    color: #0055CC;
                }
                QPushButton:pressed {
                    background-color: rgba(0,80,180,0.16);
                }
            """

    def _applyPanelBackground(self, dark: bool):
        if dark:
            self.chatHistoryWidget.setStyleSheet(
                "QWidget#chatHistoryWidget { background-color: transparent; }"
            )
            self.modelHeader.setStyleSheet(
                "QWidget#modelHeader { border-bottom: 1px solid rgba(0,200,255,0.12); }"
            )
        else:
            self.chatHistoryWidget.setStyleSheet(
                "QWidget#chatHistoryWidget { background-color: transparent; }"
            )
            self.modelHeader.setStyleSheet(
                "QWidget#modelHeader { border-bottom: 1px solid #B0C8E0; }"
            )

    # ── Event filter ───────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj == self.promptWindow:
            if event.type() == event.Type.Resize:
                rect = self.promptWindow.rect()
                self.promptEnterButton.move(
                    rect.width() - 42, (rect.height() - 30) // 2
                )
            elif event.type() == event.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                        self.OnPromptEnderButtonClicked()
                        return True
        return super().eventFilter(obj, event)

    # ── Workers ────────────────────────────────────────────────────────────

    def StopAllWorkers(self):
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

        self.AppendToChat("Вы", query)
        self.client.add_to_history("user", query)
        self.promptWindow.clear()

        self.ShowLoadingAnimation()

        text = self.readText()
        is_loading = (text == "Текст загружается, подождите...")
        rag_available = self.client.rag_manager.vector_store is not None

        if is_loading and not rag_available:
            self.HideLoadingAnimation()
            self.AppendToChat(
                "Система",
                "Текст страницы еще не готов и поиск по книге недоступен. "
                "Пожалуйста, подождите немного."
            )
            return

        self.promptWorker = GetResponceWorker(
            client=self.client, model=modelId, query=query, text=text
        )
        self.promptWorker.completed.connect(self.OnResponceReceived)
        self.promptWorker.start()

    def OnResponceReceived(self, resp):
        self.HideLoadingAnimation()
        self.AppendToChat("ИИ", resp)
        self.client.add_to_history("assistant", resp)

    def ShowLoadingAnimation(self):
        if self.loadingBubble:
            return
        self.loadingBubble = LoadingBubble(self.isDarkMode)
        if hasattr(self, 'currentFontSize'):
            self.loadingBubble.update_style(self.isDarkMode, self.currentFontSize - 1)
        self.chatHistoryLayout.addWidget(self.loadingBubble)
        self.ScrollToBottom()

    def HideLoadingAnimation(self):
        if self.loadingBubble:
            self.chatHistoryLayout.removeWidget(self.loadingBubble)
            self.loadingBubble.deleteLater()
            self.loadingBubble = None

    def ScrollToBottom(self):
        QTimer.singleShot(50, lambda: self.chatWindow.verticalScrollBar().setValue(
            self.chatWindow.verticalScrollBar().maximum()
        ))

    def AppendToChat(self, sender, message):
        is_user = (sender == "Вы")
        bubble = MessageBubble(sender, message, is_user, self.isDarkMode)
        bubble.sourceClicked.connect(self.sourceClicked.emit)
        if hasattr(self, 'currentFontSize'):
            bubble.update_style(is_user, self.isDarkMode, self.currentFontSize - 1)
        self.chatHistoryLayout.addWidget(bubble)
        self.ScrollToBottom()

    def OnModelReceived(self, models_info):
        if isinstance(models_info, list):
            self.UpdateModelList(models_info)
        else:
            self.UpdateModelList([{"id": f"Ошибка: {str(models_info)}", "is_serverless": False}])

    def UpdateModelList(self, models_info):
        self.modelSelector.clear()

        for model in models_info:
            m_id = model.get('id', 'Unknown')
            is_serverless = model.get('is_serverless', False)
            is_recommended = model.get('is_recommended', False)

            self.modelSelector.addItem(m_id, userData=m_id)
            index = self.modelSelector.count() - 1

            display_text = m_id

            if is_recommended:
                display_text = f"★ {display_text}"
                self.modelSelector.setItemData(
                    index, QColor("#FBBF24"), Qt.ItemDataRole.ForegroundRole
                )
            elif is_serverless:
                self.modelSelector.setItemData(
                    index, QColor("#34D399"), Qt.ItemDataRole.ForegroundRole
                )

            if is_serverless:
                display_text = f"{display_text} (Serverless)"

            self.modelSelector.setItemText(index, display_text)

        if self.modelSelector.count() > 0:
            self.modelSelector.setCurrentIndex(0)
            self.client.SetCurrentModelID(0)

    def OnModelIndexChanged(self, index):
        if self.client and index >= 0:
            self.client.SetCurrentModelID(index)

    def GetSelectedModel(self):
        return self.modelSelector.currentData()

    def OnClearChatButtonClicked(self):
        self.client.clear_history()
        while self.chatHistoryLayout.count():
            item = self.chatHistoryLayout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.HideLoadingAnimation()

    def SetDarkMode(self, is_dark, fs=14):
        self.isDarkMode = is_dark
        self.currentFontSize = fs

        for i in range(self.chatHistoryLayout.count()):
            widget = self.chatHistoryLayout.itemAt(i).widget()
            if isinstance(widget, MessageBubble):
                is_user = (widget.header.text() == "Вы")
                widget.update_style(is_user, is_dark, fs - 1)
            elif isinstance(widget, LoadingBubble):
                widget.update_style(is_dark, fs - 1)

        self.modelSelector.setStyleSheet(self._model_selector_style(dark=is_dark, fs=fs - 2))
        self.promptWindow.setStyleSheet(self._prompt_style(dark=is_dark, fs=fs - 1))
        self.promptEnterButton.setStyleSheet(self._send_button_style(dark=is_dark))
        self.refreshModelButton.setStyleSheet(self._icon_button_style(dark=is_dark))
        self.clearChatButton.setStyleSheet(self._icon_button_style(dark=is_dark))
        self._applyPanelBackground(dark=is_dark)
