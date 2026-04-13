from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QGridLayout, QLineEdit, QProgressBar
from PySide6.QtCore import Qt, Signal, QSize, QPointF, QThread, Slot, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtPdf import QPdfDocument, QPdfLink
from PySide6.QtPdfWidgets import QPdfView
from doc_converter import Converter

class PageConverterWorker(QThread):
    """Рабочий поток для конвертации страницы PDF в текст."""
    finished = Signal(int, str)  # pageIndex, resultText

    def __init__(self, docConverter: Converter, filePath: str, pageIndex: int):
        super().__init__()
        self.docConverter = docConverter
        self.filePath = filePath
        self.pageIndex = pageIndex

    def run(self):
        try:
            # Конвертируем одну страницу
            text = self.docConverter.convertPdf(self.filePath, 1, self.pageIndex)
            self.finished.emit(self.pageIndex, text)
        except Exception as e:
            print(f"Ошибка при конвертации страницы {self.pageIndex}: {e}")
            self.finished.emit(self.pageIndex, f"Ошибка загрузки: {str(e)}")

class ReaderPanel(QWidget):
    # Добавляем сигнал о том, что страница проиндексирована
    pageIndexed = Signal(int, str)

    def __init__(self, docConverter: Converter, aiClient, parent=None):
        super().__init__(parent)
        self.aiClient = aiClient # Сохраняем ссылку на AIClient
        
        #Окно с рендером PDF
        self.pdfWindow = QPdfView(self)
        self.pdfWindow.setPageMode(QPdfView.PageMode.SinglePage)
        self.pdfWindow.setStyleSheet("background-color: #1e1e1e;")

        #Окно с рендером конвертированного текста
        self.convertedTextView = QTextEdit(self)
        self.convertedTextView.setReadOnly(True)
        self.convertedTextView.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
                padding: 20px;
                font-size: 14px;
                line-height: 1.6;
            }
        """)

        #Layout навигации
        self.navigationOverlay = QWidget()
        self.navigationOverlay.setStyleSheet("""
            QWidget {
                background-color: rgba(37, 37, 38, 220);
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)
        self.navigationOverlay.setFixedWidth(250)
        self.navigationOverlay.setFixedHeight(45)

        self.prevPage = QPushButton()
        self.prevPage.clicked.connect(self.OnPrevPageButtonClicked)
        self.prevPage.setText("←")
        self.prevPage.setShortcut(Qt.Key.Key_Left)
        self.prevPage.setFixedSize(28, 28)
        self.prevPage.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #cccccc;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #007acc;
            }
        """)

        self.nextPage = QPushButton()
        self.nextPage.clicked.connect(self.OnNextPageButtonClicked)
        self.nextPage.setText("→")
        self.nextPage.setShortcut(Qt.Key.Key_Right)
        self.nextPage.setFixedSize(28, 28)
        self.nextPage.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #cccccc;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #007acc;
            }
        """)

        self.jumpPage = QLineEdit()
        self.jumpPage.returnPressed.connect(self.JumpTOPage)
        self.jumpPage.setFixedSize(40, 24)
        self.jumpPage.setAlignment(Qt.AlignCenter)
        self.jumpPage.setPlaceholderText("...")
        self.jumpPage.setStyleSheet("""
            QLineEdit {
                background-color: #3c3c3c; 
                border-radius: 2px; 
                border: 1px solid #3c3c3c;
                color: #cccccc;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 1px solid #007acc;
            }
        """)


        self.pagesLabel = QLabel()
        self.pagesLabel.setText("0 из 0")
        self.pagesLabel.setStyleSheet("background: transparent; color: #808080; font-size: 12px;")

        self.navigationLayout = QHBoxLayout(self.navigationOverlay)
        self.navigationLayout.setContentsMargins(5, 5, 5, 5)
        self.navigationLayout.setSpacing(10)

        self.navigationLayout.addWidget(self.prevPage)
        self.navigationLayout.addWidget(self.jumpPage)
        self.navigationLayout.addWidget(self.pagesLabel)
        self.navigationLayout.addWidget(self.nextPage)

        # Индикатор загрузки страницы
        self.loadingBar = QProgressBar()
        self.loadingBar.setRange(0, 0) # Неопределенное состояние (анимация)
        self.loadingBar.setTextVisible(False)
        self.loadingBar.setFixedHeight(2)
        self.loadingBar.setStyleSheet("""
            QProgressBar {
                background-color: transparent;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #007acc;
            }
        """)
        self.loadingBar.hide()
        self.navigationLayout.addWidget(self.loadingBar)

        # Основной layout
        self.box = QVBoxLayout()
        
        # Контейнер для области чтения, чтобы кнопки были поверх
        self.readingContainer = QWidget()
        self.readingLayout = QGridLayout(self.readingContainer)
        self.readingLayout.setContentsMargins(0, 0, 0, 0)
        self.readingLayout.setSpacing(0)
        
        self.readingLayout.addWidget(self.pdfWindow, 0, 0)
        self.readingLayout.addWidget(self.convertedTextView, 0, 0)
        
        # Добавляем оверлей навигации в верхний левый угол
        self.readingLayout.addWidget(self.navigationOverlay, 0, 0, Qt.AlignLeft | Qt.AlignTop)
        
        self.navigationOverlay.raise_()

        self.box.addWidget(self.readingContainer)
        self.box.setStretch(0,1)

        self.originalMode = True
        self.convertedTextView.hide()
        self.pdfWindow.show()
        
        self.navigationOverlay.raise_()

        self.setLayout(self.box)

        #Прочее
        self.docConverter = docConverter
        self.currentFilePath = ""
        self.document = QPdfDocument()
        self.maxPages = 0
        self.currentPage = 0
        
        self.convertedPagesCache = []
        self.activeWorkers = {}  # pageIndex: PageConverterWorker
        self.workerQueue = []    # Очередь индексов страниц для конвертации
        self.maxConcurrentWorkers = 1 # Ограничиваем одним потоком, так как Docling очень тяжелый
        self.isDarkMode = True

        
    def GetConvertedText(self):
        if not self.convertedPagesCache or self.currentPage >= len(self.convertedPagesCache):
            return "Текст не загружен"
        
        text = self.convertedPagesCache[self.currentPage]
        if(text == ""):
            # Если текста нет, начинаем загрузку и возвращаем временное сообщение
            self.LoadConvertedPage(self.currentPage)
            return "Текст загружается, подождите..."
        
        return self.convertedTextView.toPlainText()

    def SwitchModes(self):
        if(self.originalMode == True):
            self.originalMode = False
            self.convertedTextView.show()
            self.pdfWindow.hide()
            # При переключении в текстовый режим убеждаемся, что текущая страница загружена
            self.LoadConvertedPage(self.currentPage)
        else:
            self.originalMode = True
            self.convertedTextView.hide()
            self.pdfWindow.show()
        
        self.navigationOverlay.raise_()

    def SetConvertedText(self, text):
        self.convertedTextView.setHtml(text)

    def LoadDocument(self, filePath):
        self.currentFilePath = filePath
        self.document.load(filePath)
        self.maxPages = self.docConverter.getPagesCount(filePath)
        self.pdfWindow.setDocument(self.document)
        self.convertedPagesCache.clear()
        self.convertedPagesCache = [str() for x in range(self.maxPages)]
        
        # Очищаем старые воркеры, очередь и векторную базу
        for worker in self.activeWorkers.values():
            worker.terminate()
            worker.wait()
        self.activeWorkers.clear()
        self.workerQueue.clear()
        self.aiClient.rag_manager.clear() # Очищаем FAISS индекс

        print(self.convertedPagesCache)
        #self.LoadConvertedPage(0)
        self.SetPdfPage(0)

        self.currentPage=0
        self.setPagesCount(self.currentPage)
        self.LoadConvertedPage(self.currentPage) # Загружаем первую страницу
        self.navigationOverlay.raise_()

    def ConvertPage(self, pageIndex, priority=False):
        # Если страница уже в кэше или уже обрабатывается
        if self.convertedPagesCache[pageIndex] != "" or pageIndex in self.activeWorkers:
            return
            
        # Если страница уже в очереди, перемещаем ее в начало, если это приоритет
        if pageIndex in self.workerQueue:
            if priority:
                self.workerQueue.remove(pageIndex)
                self.workerQueue.insert(0, pageIndex)
        else:
            if priority:
                self.workerQueue.insert(0, pageIndex)
            else:
                self.workerQueue.append(pageIndex)
                
        self.ProcessQueue()

    def ProcessQueue(self):
        # Если лимит воркеров исчерпан или очередь пуста
        if len(self.activeWorkers) >= self.maxConcurrentWorkers or not self.workerQueue:
            return
            
        # Берем следующую страницу из очереди
        pageIndex = self.workerQueue.pop(0)
        
        # На всякий случай проверяем еще раз
        if self.convertedPagesCache[pageIndex] != "" or pageIndex in self.activeWorkers:
            self.ProcessQueue()
            return
            
        worker = PageConverterWorker(self.docConverter, self.currentFilePath, pageIndex)
        worker.finished.connect(self.OnPageConverted)
        self.activeWorkers[pageIndex] = worker
        worker.start()

    @Slot(int, str)
    def OnPageConverted(self, pageIndex, text):
        # Удаляем воркера из активных и очищаем память воркера
        if pageIndex in self.activeWorkers:
            worker = self.activeWorkers.pop(pageIndex)
            worker.wait()
            worker.deleteLater()
            
        self.convertedPagesCache[pageIndex] = text
        
        # Индексируем текст в FAISS
        self.aiClient.rag_manager.add_page_text(text, pageIndex)
        
        # Если это текущая страница, обновляем UI
        if pageIndex == self.currentPage:
            self.convertedTextView.setHtml(text)
            self.loadingBar.hide()
            
        # Запускаем предзагрузку соседних страниц
        self.PreloadAdjacentPages()
        
        # Обрабатываем следующую страницу из очереди
        self.ProcessQueue()

    def PreloadAdjacentPages(self):
        # Предзагружаем следующую и предыдущую страницы (без приоритета)
        for offset in [1, -1, 2]: # Загружаем вперед на 2 и назад на 1
            idx = self.currentPage + offset
            if 0 <= idx < self.maxPages and self.convertedPagesCache[idx] == "":
                self.ConvertPage(idx, priority=False)

    def LoadConvertedPage(self, pageIndex):
        if pageIndex < 0 or pageIndex >= self.maxPages:
            return
            
        if self.convertedPagesCache[pageIndex] == "":
            # Показываем индикатор загрузки
            self.loadingBar.show()
            
            # Если идет загрузка, показываем это
            if pageIndex in self.activeWorkers or pageIndex in self.workerQueue:
                self.convertedTextView.setHtml("<h2 style='color: #888; text-align: center; margin-top: 50px;'>Страница в очереди или загружается...</h2>")
            
            # Добавляем в очередь с высоким приоритетом
            self.ConvertPage(pageIndex, priority=True)
        else:
            self.loadingBar.hide()
            self.convertedTextView.setHtml(self.convertedPagesCache[pageIndex])
            # Даже если страница в кэше, пробуем предзагрузить соседей
            self.PreloadAdjacentPages()

    def SetPdfPage(self, pageIndex):
        pass
        
    def closeEvent(self, event):
        # Останавливаем все фоновые задачи при закрытии
        for worker in self.activeWorkers.values():
            worker.terminate()
            worker.wait()
        super().closeEvent(event)

    def OnPrevPageButtonClicked(self):
        if(self.currentPage - 1 >= 0):
            self.currentPage -= 1
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage,QPointF(0,0),1.0)
            self.setPagesCount(self.currentPage)

    def OnNextPageButtonClicked(self):
        if(self.currentPage + 1 < self.maxPages):
            self.currentPage += 1
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage,QPointF(0,0),1.0)
            self.setPagesCount(self.currentPage)

    def SetDarkMode(self, is_dark):
        self.isDarkMode = is_dark
        if is_dark:
            self.pdfWindow.setStyleSheet("background-color: #1e1e1e;")
            self.convertedTextView.setStyleSheet("""
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    padding: 20px;
                    font-size: 14px;
                    line-height: 1.6;
                }
            """)
            self.navigationOverlay.setStyleSheet("""
                QWidget {
                    background-color: rgba(37, 37, 38, 220);
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                }
            """)
            button_style = """
                QPushButton {
                    background-color: transparent;
                    color: #cccccc;
                    border-radius: 4px;
                    font-size: 16px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #3c3c3c;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #007acc;
                }
            """
            self.prevPage.setStyleSheet(button_style)
            self.nextPage.setStyleSheet(button_style)
            self.jumpPage.setStyleSheet("""
                QLineEdit {
                    background-color: #3c3c3c; 
                    border-radius: 2px; 
                    border: 1px solid #3c3c3c;
                    color: #cccccc;
                    font-size: 12px;
                }
                QLineEdit:focus {
                    border: 1px solid #007acc;
                }
            """)
            self.pagesLabel.setStyleSheet("background: transparent; color: #808080; font-size: 12px;")
            self.loadingBar.setStyleSheet("""
                QProgressBar {
                    background-color: transparent;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: #007acc;
                }
            """)
        else:
            self.pdfWindow.setStyleSheet("background-color: #ffffff;")
            self.convertedTextView.setStyleSheet("""
                QTextEdit {
                    background-color: #ffffff;
                    color: #333333;
                    border: none;
                    padding: 20px;
                    font-size: 14px;
                    line-height: 1.6;
                }
            """)
            self.navigationOverlay.setStyleSheet("""
                QWidget {
                    background-color: rgba(255, 255, 255, 220);
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                }
            """)
            button_style = """
                QPushButton {
                    background-color: transparent;
                    color: #333333;
                    border-radius: 4px;
                    font-size: 16px;
                    font-weight: bold;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #f0f0f0;
                    color: #0078d4;
                }
                QPushButton:pressed {
                    background-color: #e5e5e5;
                }
            """
            self.prevPage.setStyleSheet(button_style)
            self.nextPage.setStyleSheet(button_style)
            self.jumpPage.setStyleSheet("""
                QLineEdit {
                    background-color: #ffffff; 
                    border-radius: 2px; 
                    border: 1px solid #cccccc;
                    color: #333333;
                    font-size: 12px;
                }
                QLineEdit:focus {
                    border: 1px solid #0078d4;
                }
            """)
            self.pagesLabel.setStyleSheet("background: transparent; color: #666666; font-size: 12px;")
            self.loadingBar.setStyleSheet("""
                QProgressBar {
                    background-color: transparent;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: #0078d4;
                }
            """)

    def setPagesCount(self, current_page: int = 1):
        self.pagesLabel.setText(f"{current_page+1} из {self.maxPages}")

    def JumpTOPage(self):
        try:
            text = self.jumpPage.text().strip()
            if not text:
                return
            number = int(text) - 1
            if 0 <= number < self.maxPages:
                self.currentPage = number
                self.LoadConvertedPage(self.currentPage)
                self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)
                self.setPagesCount(self.currentPage)
                self.jumpPage.clear()
                self.jumpPage.clearFocus()
        except ValueError:
            self.jumpPage.clear()


