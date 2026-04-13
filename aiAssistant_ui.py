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
from PySide6.QtGui import QColor, QFont
from ai_client import AIClient
import asyncio
from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot, QThread, Signal, Qt

class MessageBubble(QWidget):
    """Виджет отдельного сообщения в стиле мессенджера."""
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
        self.bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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

    def update_style(self, is_user, is_dark):
        if is_user:
            bg_color = "#007acc"
            text_color = "white"
            radius = "12px 12px 2px 12px"
            border = "none"
        else:
            if is_dark:
                bg_color = "#2d2d2d"
                text_color = "#d4d4d4"
                border = "1px solid #3c3c3c"
            else:
                bg_color = "#f1f1f1"
                text_color = "#333333"
                border = "1px solid #e0e0e0"
            radius = "12px 12px 12px 2px"
            
        self.bubble.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 12px;
                border: {border};
                padding: 8px 12px;
                font-size: 13px;
            }}
        """)
        # Хак для имитации специфических углов в Qt QLabel (border-radius применяется ко всем углам)
        # Для реальных специфических углов нужно рисовать через QPainter, 
        # но для начала сделаем просто аккуратные закругления.

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

    def __init__(self, client, query, text, model):
        super().__init__()
        self.client = client
        self.query = query
        self.text = text
        self.model = model

    @Slot()
    def run(self):
        resp = asyncio.run(self.client.CreateResponceAsync(self.model, self.query, self.text))
        self.completed.emit(resp)

class AIAssistantPanel(QWidget):
    def __init__(self, client: AIClient, readmethod, parent=None, ):
        super().__init__(parent)

        #Инициализация всего прочего
        self.client = client
        self.threadPool = QThreadPool()
        self.readText = readmethod
        self.promptWorker = None
        self.modelUpdateWorker = None
        self.isDarkMode = True

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
        if obj == self.promptWindow and event.type() == event.Type.Resize:
            # Позиционируем кнопку в правом углу текстового поля
            rect = self.promptWindow.rect()
            self.promptEnterButton.move(rect.width() - 40, (rect.height() - 32) // 2)
        return super().eventFilter(obj, event)

    def OnRefreshModelButtonClicked(self):
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
        self.promptWindow.clear()
        
        self.promptWorker = GetResponceWorker(client=self.client, model=modelId, query=query,
                                              text=self.readText())
        self.promptWorker.completed.connect(self.OnResponceReceived)
        self.promptWorker.start()

    def OnResponceReceived(self, resp):
        # Добавляем ответ ИИ в чат
        self.AppendToChat("ИИ", resp)

    def AppendToChat(self, sender, message):
        is_user = (sender == "Вы")
        
        # Создаем виджет сообщения (бабл)
        bubble = MessageBubble(sender, message, is_user, self.isDarkMode)
        self.chatHistoryLayout.addWidget(bubble)
        
        # Прокрутка вниз
        QTimer.singleShot(50, lambda: self.chatWindow.verticalScrollBar().setValue(
            self.chatWindow.verticalScrollBar().maximum()
        ))

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
            
            # Сохраняем оригинальный ID в UserRole для корректной работы API
            self.modelSelector.addItem(m_id, userData=m_id)
            index = self.modelSelector.count() - 1
            
            # Если модель serverless, красим её в зеленый цвет и добавляем метку
            if is_serverless:
                self.modelSelector.setItemData(index, QColor("#4ec9b0"), Qt.ItemDataRole.ForegroundRole)
                self.modelSelector.setItemText(index, f"{m_id} (Serverless)")

    def GetSelectedModel(self):
        # Возвращаем оригинальный ID из userData
        return self.modelSelector.currentData()
    
    def SetDarkMode(self, is_dark):
        self.isDarkMode = is_dark
        if is_dark:
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
            self.chatWindow.setStyleSheet("border: 1px solid #3c3c3c; border-radius: 4px; background-color: #1e1e1e;")
            self.chatHistoryWidget.setStyleSheet("background-color: #1e1e1e;")
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
        else:
            self.modelSelector.setStyleSheet("""
                QComboBox {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 4px 10px;
                    background-color: #ffffff;
                    color: #333333;
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
                    border-top: 5px solid #666666;
                }
                QComboBox QAbstractItemView {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    selection-background-color: #0078d4;
                    selection-color: #ffffff;
                    outline: 0px;
                }
            """)
            self.chatWindow.setStyleSheet("border: 1px solid #dddddd; border-radius: 4px; background-color: #ffffff;")
            self.chatHistoryWidget.setStyleSheet("background-color: #ffffff;")
            self.promptWindow.setStyleSheet("""
                QTextEdit {
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    padding: 8px 40px 8px 10px;
                    background-color: #f5f5f5;
                    color: #333333;
                    font-size: 13px;
                }
                QTextEdit:focus {
                    border: 1px solid #0078d4;
                }
            """)
            self.promptEnterButton.setStyleSheet("""
                QPushButton {
                    background-color: #0078d4;
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
                    background-color: #eeeeee;
                    color: #999999;
                }
            """)
            self.refreshModelButton.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #f5f5f5;
                    border: 1px solid #0078d4;
                }
            """)
        
        # Обновляем стиль существующих баблов
        for i in range(self.chatHistoryLayout.count()):
            item = self.chatHistoryLayout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, MessageBubble):
                is_user = widget.header.text() == "Вы"
                widget.update_style(is_user, is_dark)
    
    


    

