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
    QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from ai_client import AIClient
import asyncio
from PySide6.QtCore import QRunnable, QThreadPool, QTimer, Slot, QThread, Signal, Qt

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

        #Инициализация GUI

        #Окно выбора модели
        self.modelSelector = QComboBox()
        self.modelSelector.setPlaceholderText("Загрузка моделей...")
        self.modelSelector.setStyleSheet("""
            QComboBox {
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                padding: 5px 30px 5px 10px;
                background-color: white;
                min-height: 25px;
                font-size: 13px;
                color: #333;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #dcdcdc;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #666;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #dcdcdc;
                selection-background-color: #f0f2f5;
                outline: 0px;
            }
        """)
        

        #Вывод модели (История чата)
        self.chatWindow = QScrollArea()
        self.chatWindow.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chatWindow.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.chatHistory = QTextEdit()
        self.chatHistory.setPlaceholderText("Здесь будет ваша переписка...")
        self.chatHistory.setReadOnly(True)
        self.chatHistory.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: none;
                padding: 10px;
                font-size: 14px;
                line-height: 1.5;
            }
        """)
        self.chatWindow.setWidget(self.chatHistory)
        self.chatWindow.setWidgetResizable(True)
        self.chatWindow.setStyleSheet("border: 1px solid #e0e0e0; border-radius: 15px; background-color: white;")

        #Нижняя панель ввода
        self.inputContainer = QWidget()
        self.inputLayout = QHBoxLayout(self.inputContainer)
        self.inputLayout.setContentsMargins(0, 5, 0, 5)
        self.inputLayout.setSpacing(10)

        #Окно промпта
        self.promptWindow = QTextEdit()
        self.promptWindow.setPlaceholderText("Спросите что-нибудь...")
        self.promptWindow.setFixedHeight(45)
        self.promptWindow.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 22px;
                padding-left: 15px;
                padding-right: 45px;
                padding-top: 10px;
                background-color: #f8f9fa;
                font-size: 14px;
                color: #333;
            }
        """)

        #Кнопка на отправку промпта
        self.promptEnterButton = QPushButton(self.promptWindow)
        self.promptEnterButton.clicked.connect(self.OnPromptEnderButtonClicked)
        self.promptEnterButton.setText("↑") # Элегантная стрелка вверх
        self.promptEnterButton.setFixedSize(32, 32)
        # Позиционируем кнопку прямо внутри текстового поля справа
        self.promptEnterButton.move(0, 0) # Будет уточнено в resizeEvent или через отступы
        self.promptEnterButton.setStyleSheet("""
            QPushButton {
                background-color: #000000;
                color: white;
                border-radius: 16px;
                font-size: 18px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #222;
            }
            QPushButton:pressed {
                background-color: #444;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)

        # Для позиционирования кнопки внутри текстового поля
        self.promptWindow.installEventFilter(self)

        self.inputLayout.addWidget(self.promptWindow)

        #Кнопка на обновление модели
        self.refreshModelButton = QPushButton()
        self.refreshModelButton.clicked.connect(self.OnRefreshModelButtonClicked)
        self.refreshModelButton.setText("↻") # Иконка обновления
        self.refreshModelButton.setFixedSize(30, 30)
        self.refreshModelButton.setStyleSheet("""
            QPushButton {
                background-color: #f0f2f5;
                color: #555;
                border: 1px solid #dcdcdc;
                border-radius: 15px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e4e6e9;
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
        if sender == "Вы":
            # Сообщение пользователя: справа, синий пузырь
            bubble_style = "background-color: #0078d4; color: white; border-radius: 20px; border-bottom-right-radius: 5px; padding: 12px 16px; margin-left: 40px; margin-bottom: 4px; display: inline-block;"
            header_style = "color: #888; font-size: 11px; margin-bottom: 4px; font-weight: bold;"
            alignment = "right"
        else:
            # Сообщение ИИ: слева, серый пузырь
            bubble_style = "background-color: #f1f3f4; color: #202124; border-radius: 20px; border-top-left-radius: 5px; padding: 12px 16px; margin-right: 40px; margin-bottom: 4px; display: inline-block;"
            header_style = "color: #888; font-size: 11px; margin-bottom: 4px; font-weight: bold;"
            alignment = "left"

        # Формируем HTML для "пузыря"
        safe_message = message.replace('\n', '<br/>')
        formatted_message = f"""
        <div style='margin-bottom: 16px; text-align: {alignment};'>
            <div style='{header_style}'>{sender}</div>
            <div style='{bubble_style}'>
                {safe_message}
            </div>
        </div>
        """
        
        self.chatHistory.append(formatted_message)
        # Прокрутка вниз
        self.chatHistory.verticalScrollBar().setValue(self.chatHistory.verticalScrollBar().maximum())

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
                self.modelSelector.setItemData(index, QColor("green"), Qt.ItemDataRole.ForegroundRole)
                self.modelSelector.setItemText(index, f"{m_id} (Serverless)")

    def GetSelectedModel(self):
        # Возвращаем оригинальный ID из userData
        return self.modelSelector.currentData()
    
    


    

