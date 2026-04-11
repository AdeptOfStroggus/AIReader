from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QPushButton,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QGroupBox,
    QLabel,
    QScrollArea
)
from PySide6.QtCore import Qt, Signal
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


        #Инициализация GUI

        #Окно выбора модели
        self.modelSelector = QScrollArea()
        self.modelSelector.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.modelSelector.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.modelListUI = QListWidget()
        self.modelSelector.setWidget(self.modelListUI)
        self.modelSelector.setWidgetResizable(True)
        

        #Окно промпта
        self.promptWindow = QTextEdit()
        self.promptWindow.setPlaceholderText("Введите промпт")

        #Вывод модели
        self.responceWindow = QScrollArea()
        self.responceWindow.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.responceWindow.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.responceEdit = QTextEdit()
        self.responceEdit.setPlaceholderText("Ответ появится здесь")
        self.responceEdit.setReadOnly(True)
        self.responceWindow.setWidget(self.responceEdit)
        self.responceWindow.setWidgetResizable(True)

        #Кнопка на обновление модели
        self.refreshModelButton = QPushButton()
        self.refreshModelButton.clicked.connect(self.OnRefreshModelButtonClicked)
        self.refreshModelButton.setText("Обновить список моделей")
        
        #Кнопка на отправку промпта
        self.promptEnterButton = QPushButton()
        self.promptEnterButton.clicked.connect(self.OnPromptEnderButtonClicked)
        self.promptEnterButton.setText("Отправить сообщение")


        #Инициализация окна с промптами
        self.promptLayoutWidget = QWidget()
        self.promptLayout = QVBoxLayout()
        self.promptLayout.addWidget(self.responceWindow)
        self.promptLayout.addWidget(self.promptWindow)
        self.promptLayout.addWidget(self.promptEnterButton)
        self.promptLayoutWidget.setLayout(self.promptLayout)

        self.promptLayout.setStretch(0,3)
        self.promptLayout.setStretch(1,1)

        #Инициализация окна с выбором модели
        self.modelSelectorLayoutWidget = QWidget()
        self.modelSelectorLayout = QVBoxLayout()
        self.modelSelectorLayout.addWidget(self.modelSelector)
        self.modelSelectorLayout.addWidget(self.refreshModelButton)
        self.modelSelectorLayoutWidget.setLayout(self.modelSelectorLayout)

        #Основной layout панели
        self.box = QVBoxLayout()
        self.box.addWidget(self.modelSelectorLayoutWidget)
        self.box.addWidget(self.promptLayoutWidget)
        self.setLayout(self.box)
        self.box.setStretch(0,1)
        self.box.setStretch(1,5)

        #Инициализация событий

        #Инициализация всего прочего
        self.client = client
        self.threadPool = QThreadPool()

        self.promptWorker:GetResponceWorker
        self.modelUpdateWorker:GetModelsWorker
        self.readText = readmethod
        


    def OnRefreshModelButtonClicked(self):
        self.modelUpdateWorker = GetModelsWorker(self.client)
        self.modelUpdateWorker.completed.connect(self.OnModelReceived)
        self.modelUpdateWorker.start()
        

    def OnPromptEnderButtonClicked(self):
        modelId = self.GetSelectedModel()
        self.promptWorker = GetResponceWorker(client=self.client, model=modelId, query=self.promptWindow.toPlainText(),
                                              text=self.readText())
        self.promptWorker.completed.connect(self.OnResponceReceived)
        self.promptWorker.start()

    def OnResponceReceived(self, resp):
        self.responceEdit.setHtml(resp)

    def OnModelReceived(self, modelList):
        if isinstance(modelList, list):
            self.UpdateModelList(modelList)
        else:
            # Если пришла строка (ошибка), выводим её в список
            self.UpdateModelList([f"Ошибка: {str(modelList)}"])

    def UpdateModelList(self, modelIDs):
        self.modelListUI.clear()
        for i in modelIDs:
            item = QListWidgetItem(str(i))
            self.modelListUI.addItem(item)

    def GetSelectedModel(self):
        return self.modelListUI.currentItem().text()
    
    


    

