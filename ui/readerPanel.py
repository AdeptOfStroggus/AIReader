from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QGridLayout, QLineEdit, QProgressBar, QComboBox
from PySide6.QtCore import Qt, Signal, QSize, QPointF, QThread, Slot, QPropertyAnimation, QEasingCurve, QRunnable, QThreadPool, QTimer, QTime
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPalette
from PySide6.QtPdf import QPdfDocument, QPdfLink
from PySide6.QtPdfWidgets import QPdfView
from doc_converter import Converter
from multiprocessing import cpu_count

class PageConverterRunnable(QRunnable):
    """Рабочий класс для конвертации страницы PDF в текст (QRunnable для QThreadPool)."""
    finished = Signal(int, str)  # pageIndex, resultText

    def __init__(self, docConverter: Converter, filePath: str, pageIndex: int, onFinished, aiClient=None):
        super().__init__()
        self.docConverter = docConverter
        self.filePath = filePath
        self.pageIndex = pageIndex
        self.onFinished = onFinished
        self.aiClient = aiClient  # Для индексирования в фоновом потоке

    def run(self):
        try:
            # Конвертируем одну страницу
            [text, overall, imgs] = self.docConverter.convertPdf(self.filePath, 1, self.pageIndex)
            
            # Индексируем текст в FAISS В РАБОЧЕМ ПОТОКЕ, чтобы не блокировать главный поток!
            if self.aiClient:
                try:
                    self.aiClient.rag_manager.add_page_text(text, self.pageIndex)
                    for image in imgs:
                        self.aiClient.image_indexer.add_image(image, self.pageIndex) # Индексируем изображения в том же порядке
                except Exception as e:
                    print(f"Ошибка при индексировании страницы {self.pageIndex}: {e}")
            
            # Отправляем только текст в главный поток
            self.onFinished(self.pageIndex, overall)
        except Exception as e:
            print(f"Ошибка при конвертации страницы {self.pageIndex}: {e}")
            self.onFinished(self.pageIndex, f"Ошибка загрузки: {str(e)}")

class ReaderPanel(QWidget):
    # Добавляем сигналы для безопасной работы с потоками
    pageIndexed = Signal(int, str)
    pageConversionFinished = Signal(int, str)  # для безопасной передачи данных из рабочего потока

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
        self.statusOverlay.setFixedWidth(220)
        self.statusOverlay.setFixedHeight(60)
        
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
        
        self.statusLayout = QVBoxLayout(self.statusOverlay)
        self.statusLayout.setContentsMargins(5, 5, 5, 5)
        self.statusLayout.setSpacing(3)

        self.statusSummaryLabel = QLabel("0/0/(0)")
        self.statusSummaryLabel.setStyleSheet("background: transparent; color: #aaaaaa; font-size: 11px;")
        self.statusSummaryLabel.setToolTip("x/y/(z): x - обработанных страниц, y - всего страниц, z - сейчас обрабатывается")
        self.statusLayout.addWidget(self.statusSummaryLabel)
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
        self.conversionInProgress = set()  # Множество индексов страниц, которые сейчас конвертируются
        self.workerQueue = []    # Очередь индексов страниц для конвертации
        self.pendingQueueUpdate = False # Флаг отложенного обновления очереди
        self._pendingHighlight = "" # Текст, который нужно выделить после загрузки страницы
        self._lastUIUpdateTime = 0  # Для дебаунсинга обновлений UI
        self._uiUpdateDebounce = 100  # Минимум миллисекунд между обновлениями статуса
        
        # Инициализируем QThreadPool с динамическим количеством потоков на основе CPU
        try:
            num_cores = cpu_count()
            self.maxConcurrentWorkers = max(1, num_cores // 2)  # Консервативный подход: CPU_count / 2
        except:
            self.maxConcurrentWorkers = 2  # Fallback на 2 потока, если не удалось определить количество ядер
        
        self.converterPool = QThreadPool()
        self.converterPool.setMaxThreadCount(self.maxConcurrentWorkers)
        print(f"Инициализирована многопоточная конвертация: {self.maxConcurrentWorkers} рабочих потоков (CPU cores: {num_cores if 'num_cores' in locals() else 'unknown'})")
        
        # Подключаем сигнал завершения конвертации к слоту (гарантирует выполнение в главном потоке)
        self.pageConversionFinished.connect(self._onPageConversionFinished)
        
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
        
        # Очищаем очередь и множество активных конвертаций
        # Ждем завершения всех активных задач в пуле потоков
        self.converterPool.waitForDone()  # Ожидаем завершения всех текущих задач
        self.conversionInProgress.clear()
        self.workerQueue.clear()
        self.pendingQueueUpdate = False
        self.aiClient.rag_manager.clear() # Очищаем FAISS индекс
        
        # Инициализируем конвертер для первой страницы чтобы избежать ленивой загрузки
        print("Инициализирую конвертер для первой страницы...")
        try:
            # Это вызовет инициализацию converter и его компонентов
            self.docConverter.converter  # Просто обращаемся к свойству, чтобы инициализировать
            print("Конвертер инициализирован успешно")
        except Exception as e:
            print(f"Ошибка при инициализации конвертера: {e}")

        # print(self.convertedPagesCache)
        # self.LoadConvertedPage(0)
        self.SetPdfPage(0)

        self.currentPage=0
        self.setPagesCount(self.currentPage)
        self.LoadConvertedPage(self.currentPage) # Загружаем первую страницу
        self.UpdateStatusSummary()
        self.navigationOverlay.raise_()

    def UpdatePageStatus(self, pageIndex, force=False):
        """Обновляет текст и цвет элемента в выпадающем списке статуса.
        Кэширует предыдущие значения чтобы избежать лишних перерисовок GUI."""
        if pageIndex < 0 or pageIndex >= self.statusCombo.count():
            return
        
        # Определяем состояние статуса
        if self.convertedPagesCache[pageIndex] != "":
            status_text = "✓ Готово"
            color = QColor("#4ec9b0") # Зеленый
        elif pageIndex in self.conversionInProgress:
            status_text = "● Обработка..."
            color = QColor("#007acc") # Синий
        elif pageIndex in self.workerQueue:
            status_text = "○ В очереди"
            color = QColor("#cccccc") # Светло-серый
        else:
            status_text = "◌ Ожидание"
            color = QColor("#888888") # Серый
        
        # Кэшируем текст для проверки изменений чтобы избежать лишних обновлений
        current_text = self.statusCombo.itemText(pageIndex)
        new_text = f"Стр. {pageIndex + 1} - {status_text}"
        
        # Обновляем только если текст или цвет изменились
        if force or current_text != new_text:
            self.statusCombo.setItemText(pageIndex, new_text)
            self.statusCombo.setItemData(pageIndex, color, Qt.ItemDataRole.ForegroundRole)

        self.UpdateStatusSummary()

    def OnStatusComboChanged(self, index):
        """Переход на страницу при выборе в выпадающем списке."""
        if index != self.currentPage and index >= 0:
            self.currentPage = index
            self.LoadConvertedPage(self.currentPage)
            self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)
            self.setPagesCount(self.currentPage)

    def UpdateStatusSummary(self):
        """Обновляет сводный индикатор статуса страниц."""
        total_pages = self.maxPages
        processed_pages = sum(1 for page_text in self.convertedPagesCache if page_text != "") if total_pages else 0
        processing_pages = len(self.conversionInProgress)
        self.statusSummaryLabel.setText(f"{processed_pages}/{total_pages}/({processing_pages})")

    def UpdateQueueOrder(self):
        """Переупорядочивает очередь оцифровки: сначала текущая, затем все слева, затем все справа.
        Теперь также агрессивно загружает близлежащие страницы в фоне."""
        self.workerQueue.clear()
        
        # 1. Текущая страница (самый высокий приоритет)
        if self.convertedPagesCache[self.currentPage] == "" and self.currentPage not in self.conversionInProgress:
            self.workerQueue.append(self.currentPage)
            self.UpdatePageStatus(self.currentPage)
            
        # 2. Все страницы слева (от текущей к началу)
        for i in range(self.currentPage - 1, -1, -1):
            if self.convertedPagesCache[i] == "" and i not in self.conversionInProgress:
                if i not in self.workerQueue:
                    self.workerQueue.append(i)
                    self.UpdatePageStatus(i)  # Обновляем только для новых элементов
                
        # 3. Все страницы справа (от текущей к концу)
        for i in range(self.currentPage + 1, self.maxPages):
            if self.convertedPagesCache[i] == "" and i not in self.conversionInProgress:
                if i not in self.workerQueue:
                    self.workerQueue.append(i)
                    self.UpdatePageStatus(i)  # Обновляем только для новых элементов
            
        self.ProcessQueue()
    
    def PreloadNearbyPages(self, radius=5):
        """Предзагружает страницы вблизи текущей страницы в фон.
        Используется для заполнения емкости многопоточности во время простоя."""
        # Диапазон страниц для предзагрузки
        start = max(0, self.currentPage - radius)
        end = min(self.maxPages, self.currentPage + radius + 1)
        
        added_to_queue = False
        for i in range(start, end):
            if i != self.currentPage:  # Пропускаем текущую страницу (она уже приоритизирована)
                if self.convertedPagesCache[i] == "" and i not in self.conversionInProgress and i not in self.workerQueue:
                    self.workerQueue.append(i)
                    added_to_queue = True
        
        # Если добавили страницы в очередь, обработаем их
        if added_to_queue:
            self.ProcessQueue()

    def ProcessQueue(self):
        """Берет задачи из очереди и отправляет их в пул потоков для обработки.
        Заполняет все доступные слоты рабочих потоков из очереди."""
        # Цикл для заполнения всех доступных слотов рабочих потоков
        while self.workerQueue and len(self.conversionInProgress) < self.maxConcurrentWorkers:
            # Берем следующую страницу из очереди
            pageIndex = self.workerQueue.pop(0)
            
            # На всякий случай проверяем еще раз
            if self.convertedPagesCache[pageIndex] != "" or pageIndex in self.conversionInProgress:
                continue  # Пропускаем и переходим к следующей доступной странице
            
            # Добавляем страницу в множество активных конвертаций
            self.conversionInProgress.add(pageIndex)
            # Обновляем статус на "Обработка"
            self.UpdatePageStatus(pageIndex)
            
            # Создаем рабочий объект и отправляем его в пул потоков
            runnable = PageConverterRunnable(
                self.docConverter, 
                self.currentFilePath, 
                pageIndex, 
                self.OnPageConverted,
                self.aiClient  # Передаем aiClient для индексирования в рабочем потоке
            )
            self.converterPool.start(runnable)

    def OnPageConverted(self, pageIndex, text):
        """Callback из рабочего потока - просто пересылает сигнал в главный поток."""
        # Испускаем сигнал чтобы обработка произошла в главном потоке
        self.pageConversionFinished.emit(pageIndex, text)
    
    @Slot(int, str)
    def _onPageConversionFinished(self, pageIndex, text):
        """Обработчик завершения конвертации страницы (выполняется в главном потоке)."""
        # Удаляем страницу из множества активных конвертаций
        if pageIndex in self.conversionInProgress:
            self.conversionInProgress.discard(pageIndex)
            
        self.convertedPagesCache[pageIndex] = text
        # Индексирование уже произошло в рабочем потоке!
        
        # Обновляем статус страницы в списке только если это текущая страница или нужно её показать
        if pageIndex == self.currentPage:
            # Для текущей страницы обновляем немедленно
            self.UpdatePageStatus(pageIndex, force=True)
            self.convertedTextView.setHtml(text)
            self.loadingBar.hide()
            
            # Проверяем, есть ли отложенное выделение
            if self._pendingHighlight:
                self._HighlightSnippet(self._pendingHighlight)
                self._pendingHighlight = ""
            
            # После загрузки текущей страницы, предзагружаем соседние страницы
            self.PreloadNearbyPages(radius=5)
        else:
            # Для остальных страниц - всегда обновляем статус при завершении
            self.UpdatePageStatus(pageIndex)
            
        # Если есть отложенное обновление очереди, выполняем его сейчас
        if self.pendingQueueUpdate:
            self.pendingQueueUpdate = False
            self.UpdateQueueOrder()
        else:
            # Обрабатываем следующие задачи из очереди
            # Так как один поток освободился, может быть место для новых задач
            self.ProcessQueue()

    def LoadConvertedPage(self, pageIndex):
        if pageIndex < 0 or pageIndex >= self.maxPages:
            return
            
        if self.convertedPagesCache[pageIndex] == "":
            # Показываем индикатор загрузки
            self.loadingBar.show()
            
            # Если идет загрузка, показываем это
            if pageIndex in self.conversionInProgress or pageIndex in self.workerQueue:
                self.convertedTextView.setHtml("<h2 style='color: #888; text-align: center; margin-top: 50px;'>Страница в очереди или загружается...</h2>")
            
            # Если есть активные конвертации, откладываем обновление очереди
            if self.conversionInProgress:
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
            if self.conversionInProgress:
                self.pendingQueueUpdate = True
            else:
                self.UpdateQueueOrder()

    def SetPdfPage(self, pageIndex):
        pass
        
    def closeEvent(self, event):
        # Останавливаем все фоновые задачи при закрытии
        self.converterPool.waitForDone()  # Ждем завершения всех задач в пуле потоков
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
        """Останавливает все активные конвертации перед закрытием приложения."""
        self.converterPool.waitForDone()  # Ждем завершения всех задач в пуле потоков
        self.conversionInProgress.clear()
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


