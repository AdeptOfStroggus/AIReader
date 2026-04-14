from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QGridLayout, QLineEdit, QProgressBar, QComboBox
from PySide6.QtCore import Qt, Signal, QSize, QPointF, QThread, Slot, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPalette
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

        # Выпадающий список статуса страниц (верхний правый угол)
        self.statusOverlay = QWidget()
        self.statusOverlay.setStyleSheet("""
            QWidget {
                background-color: rgba(37, 37, 38, 220);
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
        """)
        self.statusOverlay.setFixedWidth(180)
        self.statusOverlay.setFixedHeight(40)
        
        self.statusCombo = QComboBox()
        self.statusCombo.currentIndexChanged.connect(self.OnStatusComboChanged)
        self.statusCombo.setStyleSheet("""
            QComboBox {
                border: none;
                background-color: transparent;
                color: #cccccc;
                padding: 4px 10px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #cccccc;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #454545;
                selection-background-color: #094771;
                outline: 0px;
            }
        """)
        
        self.statusLayout = QHBoxLayout(self.statusOverlay)
        self.statusLayout.setContentsMargins(5, 5, 5, 5)
        self.statusLayout.addWidget(self.statusCombo)

        # Основной layout
        self.box = QVBoxLayout()
        
        # Контейнер для области чтения, чтобы кнопки были поверх
        self.readingContainer = QWidget()
        self.readingLayout = QGridLayout(self.readingContainer)
        self.readingLayout.setContentsMargins(0, 0, 0, 0)
        self.readingLayout.setSpacing(0)
        
        self.readingLayout.addWidget(self.pdfWindow, 0, 0)
        self.readingLayout.addWidget(self.convertedTextView, 0, 0)
        
        # Добавляем оверлеи
        self.readingLayout.addWidget(self.navigationOverlay, 0, 0, Qt.AlignLeft | Qt.AlignTop)
        self.readingLayout.addWidget(self.statusOverlay, 0, 0, Qt.AlignRight | Qt.AlignTop)
        
        self.navigationOverlay.raise_()
        self.statusOverlay.raise_()

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
        self.pendingQueueUpdate = False # Флаг отложенного обновления очереди
        self._pendingHighlight = "" # Текст, который нужно выделить после загрузки страницы
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
        
        # Обновляем выпадающий список страниц
        self.statusCombo.blockSignals(True)
        self.statusCombo.clear()
        for i in range(self.maxPages):
            self.statusCombo.addItem(f"Стр. {i+1} - ◌ Ожидание")
            self.statusCombo.setItemData(i, QColor("#888888"), Qt.ItemDataRole.ForegroundRole)
        self.statusCombo.blockSignals(False)

        self.pdfWindow.setDocument(self.document)
        self.convertedPagesCache.clear()
        self.convertedPagesCache = [str() for x in range(self.maxPages)]
        
        # Очищаем старые воркеры, очередь и векторную базу
        for worker in self.activeWorkers.values():
            worker.terminate()
            worker.wait()
        self.activeWorkers.clear()
        self.workerQueue.clear()
        self.pendingQueueUpdate = False
        self.aiClient.rag_manager.clear() # Очищаем FAISS индекс

        # print(self.convertedPagesCache)
        # self.LoadConvertedPage(0)
        self.SetPdfPage(0)

        self.currentPage=0
        self.setPagesCount(self.currentPage)
        self.LoadConvertedPage(self.currentPage) # Загружаем первую страницу
        self.navigationOverlay.raise_()

    def UpdatePageStatus(self, pageIndex):
        """Обновляет текст и цвет элемента в выпадающем списке статуса."""
        if pageIndex < 0 or pageIndex >= self.statusCombo.count():
            return
            
        status_text = ""
        color = "#888888" # По умолчанию серый
        
        if self.convertedPagesCache[pageIndex] != "":
            status_text = "✓ Готово"
            color = "#4ec9b0" # Зеленый
        elif pageIndex in self.activeWorkers:
            status_text = "● Обработка..."
            color = "#007acc" # Синий
        elif pageIndex in self.workerQueue:
            status_text = "○ В очереди"
            color = "#cccccc" # Светло-серый
        else:
            status_text = "◌ Ожидание"
            color = "#888888" # Серый
            
        self.statusCombo.setItemText(pageIndex, f"Стр. {pageIndex + 1} - {status_text}")
        self.statusCombo.setItemData(pageIndex, QColor(color), Qt.ItemDataRole.ForegroundRole)

    def OnStatusComboChanged(self, index):
        """Переход на страницу при выборе в выпадающем списке."""
        if index != self.currentPage and index >= 0:
            self.currentPage = index
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)
            self.setPagesCount(self.currentPage)

    def UpdateQueueOrder(self):
        """Переупорядочивает очередь оцифровки: сначала текущая, затем все слева, затем все справа."""
        self.workerQueue.clear()
        
        # 1. Текущая страница (самый высокий приоритет)
        if self.convertedPagesCache[self.currentPage] == "" and self.currentPage not in self.activeWorkers:
            self.workerQueue.append(self.currentPage)
            
        # 2. Все страницы слева (от текущей к началу)
        for i in range(self.currentPage - 1, -1, -1):
            if self.convertedPagesCache[i] == "" and i not in self.activeWorkers:
                if i not in self.workerQueue:
                    self.workerQueue.append(i)
                
        # 3. Все страницы справа (от текущей к концу)
        for i in range(self.currentPage + 1, self.maxPages):
            if self.convertedPagesCache[i] == "" and i not in self.activeWorkers:
                if i not in self.workerQueue:
                    self.workerQueue.append(i)
        
        # Обновляем все статусы в комбобоксе
        for i in range(self.maxPages):
            self.UpdatePageStatus(i)
            
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
        # Обновляем статус на "Обработка"
        self.UpdatePageStatus(pageIndex)
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
        
        # Обновляем статус страницы в списке
        self.UpdatePageStatus(pageIndex)
        
        # Если это текущая страница, обновляем UI
        if pageIndex == self.currentPage:
            self.convertedTextView.setHtml(text)
            self.loadingBar.hide()
            
            # Проверяем, есть ли отложенное выделение
            if self._pendingHighlight:
                self._HighlightSnippet(self._pendingHighlight)
                self._pendingHighlight = ""
            
        # Если есть отложенное обновление очереди, выполняем его сейчас
        if self.pendingQueueUpdate:
            self.pendingQueueUpdate = False
            self.UpdateQueueOrder()
        else:
            # Иначе просто берем следующую задачу
            self.ProcessQueue()

    def LoadConvertedPage(self, pageIndex):
        if pageIndex < 0 or pageIndex >= self.maxPages:
            return
            
        if self.convertedPagesCache[pageIndex] == "":
            # Показываем индикатор загрузки
            self.loadingBar.show()
            
            # Если идет загрузка, показываем это
            if pageIndex in self.activeWorkers or pageIndex in self.workerQueue:
                self.convertedTextView.setHtml("<h2 style='color: #888; text-align: center; margin-top: 50px;'>Страница в очереди или загружается...</h2>")
            
            # Если есть активные воркера, откладываем обновление очереди
            if self.activeWorkers:
                self.pendingQueueUpdate = True
            else:
                self.UpdateQueueOrder()
        else:
            self.loadingBar.hide()
            self.convertedTextView.setHtml(self.convertedPagesCache[pageIndex])
            
            # Проверяем, есть ли отложенное выделение
            if self._pendingHighlight:
                self._HighlightSnippet(self._pendingHighlight)
                self._pendingHighlight = ""
                
            # Даже если страница в кэше, обновляем очередь (или откладываем обновление)
            if self.activeWorkers:
                self.pendingQueueUpdate = True
            else:
                self.UpdateQueueOrder()

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

    def JumpToSource(self, pageIndex, snippet):
        """Переходит на страницу и выделяет текст."""
        if pageIndex < 0 or pageIndex >= self.maxPages:
            return
            
        # Запоминаем, что нужно выделить
        self._pendingHighlight = snippet

        # Если мы уже на этой странице
        if self.currentPage == pageIndex:
            # На текущей странице LoadConvertedPage не сработает полностью как нужно для перерисовки, 
            # поэтому вызываем напрямую
            self._HighlightSnippet(snippet)
            self._pendingHighlight = ""
        else:
            # Переходим на страницу
            self.currentPage = pageIndex
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)
            self.setPagesCount(self.currentPage)
        
        # Переключаемся в текстовый режим, если нужно
        if self.originalMode:
            self.SwitchModes()

    def _HighlightSnippet(self, snippet):
        """Внутренний метод для поиска и выделения текста."""
        if not snippet:
            return
            
        # Очищаем старые выделения
        self.convertedTextView.setExtraSelections([])
        
        # Ищем текст
        cursor = self.convertedTextView.document().find(snippet)
        if not cursor.isNull():
            # Нашли! Выделяем
            from PySide6.QtWidgets import QTextEdit
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor("#cc9900")) # Темно-желтый для выделения
            selection.format.setForeground(QColor("white"))
            selection.cursor = cursor
            self.convertedTextView.setExtraSelections([selection])
            
            # Прокручиваем к выделению
            self.convertedTextView.setTextCursor(cursor)
            self.convertedTextView.ensureCursorVisible()

    def SetDarkMode(self, is_dark, fs=14):
        self.isDarkMode = is_dark
        common_style = f"font-size: {fs}px;"
        
        if is_dark:
            self.pdfWindow.setStyleSheet("background-color: #1e1e1e;")
            self.convertedTextView.setStyleSheet(f"""
                QTextEdit {{
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    padding: 20px;
                    line-height: 1.6;
                    {common_style}
                }}
            """)
            
            # Установка цвета ссылок через палитру
            palette = self.convertedTextView.palette()
            palette.setColor(QPalette.ColorRole.Link, QColor("#bb86fc"))
            palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#bb86fc"))
            self.convertedTextView.setPalette(palette)
            self.navigationOverlay.setStyleSheet(f"""
                QWidget {{
                    background-color: rgba(37, 37, 38, 220);
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                }}
            """)
            button_style = f"""
                QPushButton {{
                    background-color: transparent;
                    color: #cccccc;
                    border-radius: 4px;
                    font-weight: bold;
                    border: none;
                    {common_style}
                    font-size: {fs + 2}px;
                }}
                QPushButton:hover {{
                    background-color: #3c3c3c;
                    color: #ffffff;
                }}
                QPushButton:pressed {{
                    background-color: #007acc;
                }}
            """
            self.prevPage.setStyleSheet(button_style)
            self.nextPage.setStyleSheet(button_style)
            self.jumpPage.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #3c3c3c; 
                    border-radius: 2px; 
                    border: 1px solid #3c3c3c;
                    color: #cccccc;
                    {common_style}
                    font-size: {fs - 2}px;
                }}
                QLineEdit:focus {{
                    border: 1px solid #007acc;
                }}
            """)
            self.pagesLabel.setStyleSheet(f"background: transparent; color: #808080; {common_style} font-size: {fs - 2}px;")
            self.loadingBar.setStyleSheet("""
                QProgressBar {
                    background-color: transparent;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: #007acc;
                }
            """)
            self.statusOverlay.setStyleSheet(f"""
                QWidget {{
                    background-color: rgba(37, 37, 38, 220);
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                }}
            """)
            self.statusCombo.setStyleSheet(f"""
                QComboBox {{
                    border: none;
                    background-color: transparent;
                    color: #cccccc;
                    padding: 4px 10px;
                    {common_style}
                    font-size: {fs - 2}px;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #cccccc;
                    margin-right: 8px;
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
        else:
            self.pdfWindow.setStyleSheet("background-color: #ffffff;")
            self.convertedTextView.setStyleSheet(f"""
                QTextEdit {{
                    background-color: #ffffff;
                    color: #333333;
                    border: none;
                    padding: 20px;
                    line-height: 1.6;
                    {common_style}
                }}
            """)
            
            # Установка цвета ссылок через палитру
            palette = self.convertedTextView.palette()
            palette.setColor(QPalette.ColorRole.Link, QColor("#005a92"))
            palette.setColor(QPalette.ColorRole.LinkVisited, QColor("#005a92"))
            self.convertedTextView.setPalette(palette)
            self.navigationOverlay.setStyleSheet(f"""
                QWidget {{
                    background-color: rgba(255, 255, 255, 220);
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                }}
            """)
            button_style = f"""
                QPushButton {{
                    background-color: transparent;
                    color: #333333;
                    border-radius: 4px;
                    font-weight: bold;
                    border: none;
                    {common_style}
                    font-size: {fs + 2}px;
                }}
                QPushButton:hover {{
                    background-color: #eeeeee;
                }}
                QPushButton:pressed {{
                    background-color: #0078d4;
                    color: #ffffff;
                }}
            """
            self.prevPage.setStyleSheet(button_style)
            self.nextPage.setStyleSheet(button_style)
            self.jumpPage.setStyleSheet(f"""
                QLineEdit {{
                    background-color: #f3f3f3; 
                    border-radius: 2px; 
                    border: 1px solid #cccccc;
                    color: #333333;
                    {common_style}
                    font-size: {fs - 2}px;
                }}
                QLineEdit:focus {{
                    border: 1px solid #0078d4;
                }}
            """)
            self.pagesLabel.setStyleSheet(f"background: transparent; color: #666666; {common_style} font-size: {fs - 2}px;")
            self.loadingBar.setStyleSheet("""
                QProgressBar {
                    background-color: transparent;
                    border: none;
                }
                QProgressBar::chunk {
                    background-color: #0078d4;
                }
            """)
            self.statusOverlay.setStyleSheet(f"""
                QWidget {{
                    background-color: rgba(255, 255, 255, 220);
                    border: 1px solid #dddddd;
                    border-radius: 4px;
                }}
            """)
            self.statusCombo.setStyleSheet(f"""
                QComboBox {{
                    border: none;
                    background-color: transparent;
                    color: #333333;
                    padding: 4px 10px;
                    {common_style}
                    font-size: {fs - 2}px;
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 5px solid #333333;
                    margin-right: 8px;
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

    def setPagesCount(self, current_page: int = 1):
        self.pagesLabel.setText(f"{current_page+1} из {self.maxPages}")

    def StopAllWorkers(self):
        """Останавливает все активные воркеры перед закрытием приложения."""
        for pageIndex, worker in list(self.activeWorkers.items()):
            if worker.isRunning():
                worker.quit()
                worker.wait()
        self.activeWorkers.clear()
        self.workerQueue.clear()

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


