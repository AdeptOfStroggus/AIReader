from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QGridLayout, QLineEdit, QProgressBar, QComboBox
from PySide6.QtCore import Qt, Signal, QSize, QPointF, QThread, Slot, QPropertyAnimation, QEasingCurve, QRunnable, QThreadPool, QTimer, QTime, QWaitCondition, QMutex, QMutexLocker
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QPalette
from PySide6.QtPdf import QPdfDocument, QPdfLink
from PySide6.QtPdfWidgets import QPdfView
from doc_converter import Converter
from multiprocessing import cpu_count



class GpuWorker(QThread):
    pageConverted = Signal(int, str, str, list)  # pageIndex, text, html, images

    def __init__(self, docConverter, filePath):
        super().__init__()
        self.docConverter = docConverter
        self.filePath = filePath
        self.queue = []  # очередь индексов страниц
        self.mutex = QMutex()
        self.condition = QWaitCondition()
        self.running = True
        self._is_closing = False

    def add_page(self, pageIndex):
        with QMutexLocker(self.mutex):
            self.queue.append(pageIndex)
            self.condition.wakeOne()

    def run(self):
        print("GpuWorker запущен")
        while self.running:
            with QMutexLocker(self.mutex):
                if not self.queue:
                    self.condition.wait(self.mutex)
                if not self.running:
                    break
                pageIndex = self.queue.pop(0)
            print(f"GpuWorker: начата обработка страницы {pageIndex}")
            try:
                text, html, images = self.docConverter.convertPdf(self.filePath, 1, pageIndex)
                print(f"GpuWorker: страница {pageIndex} обработана, длина HTML: {len(html)}")
                self.pageConverted.emit(pageIndex, text, html, images)
            except Exception as e:
                print(f"GpuWorker: ошибка на странице {pageIndex}: {e}")
                self.pageConverted.emit(pageIndex, "", f"<p>Ошибка: {e}</p>", [])

class IndexingTask(QRunnable):
    def __init__(self, aiClient, pageIndex, text, images):
        super().__init__() 
        self.aiClient = aiClient
        self.pageIndex = pageIndex
        self.text = text
        self.images = images

    def run(self):
        self.aiClient.rag_manager.add_page_text(self.text, self.pageIndex)
        for img in self.images:
            self.aiClient.image_indexer.add_image(img, self.pageIndex)

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
        self.convertedTextView.setAcceptRichText(True)
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
            self.maxConcurrentWorkers = 1 #max(1, num_cores // 4)  # Консервативный подход: CPU_count / 
        except:
            self.maxConcurrentWorkers = 1 # # Fallback на 2 потока, если не удалось определить количество ядер
        
    #    self.converterPool = QThreadPool()
     #   self.converterPool.setMaxThreadCount(self.maxConcurrentWorkers)
     #   print(f"Инициализирована многопоточная конвертация: {self.maxConcurrentWorkers} рабочих потоков (CPU cores: {num_cores if 'num_cores' in locals() else 'unknown'})")
        
        # Подключаем сигнал завершения конвертации к слоту (гарантирует выполнение в главном потоке)
     #   self.pageConversionFinished.connect(self._onPageConversionFinished)

      # В ReaderPanel:
        self.cpuPool = QThreadPool.globalInstance()
        try:
            num_cores = cpu_count()
            cpu_threads = max(2, num_cores // 2)
        except:
            cpu_threads = 4
        self.cpuPool.setMaxThreadCount(cpu_threads)
        print(f"CPU пул для индексации: {cpu_threads} потоков")

        # GPU-воркер пока не создаём – создадим при загрузке документа
        self.gpuWorker = None
        self._is_closing = False
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
    # Останавливаем предыдущего воркера, если есть
        if self.gpuWorker is not None:
            self.gpuWorker.running = False
            self.gpuWorker.condition.wakeOne()
            self.gpuWorker.wait()
            self.gpuWorker = None

        # Останавливаем CPU-пул (ждём завершения всех индексаций)
        self.cpuPool.waitForDone()

        self.currentFilePath = filePath
        self.document.load(filePath)
        self.maxPages = self.docConverter.getPagesCount(filePath)

        # Обновляем выпадающий список статуса страниц
        self.statusCombo.blockSignals(True)
        self.statusCombo.clear()
        for i in range(self.maxPages):
            self.statusCombo.addItem(f"Стр. {i+1} - ◌ Ожидание")
            self.statusCombo.setItemData(i, QColor("#888888"), Qt.ItemDataRole.ForegroundRole)
        self.statusCombo.blockSignals(False)

        self.pdfWindow.setDocument(self.document)
        self.convertedPagesCache.clear()
        self.convertedPagesCache = ["" for _ in range(self.maxPages)]

        # Очищаем очереди и статусы
        self.conversionInProgress.clear()
        self.workerQueue.clear()
        self.pendingQueueUpdate = False
        if(self.aiClient is not None):
            self.aiClient.rag_manager.clear()

        # Инициализируем конвертер (ленивая загрузка моделей)
        print("Инициализирую конвертер для первой страницы...")
        try:
            _ = self.docConverter.converter  # обращаемся к свойству
            print("Конвертер инициализирован успешно")
        except Exception as e:
            print(f"Ошибка при инициализации конвертера: {e}")

        # Создаём новый GPU-воркер
        try:
            self.gpuWorker = GpuWorker(self.docConverter, filePath)
            self.gpuWorker.pageConverted.connect(self._onPageConversionFinished)
            self.gpuWorker.start()
            print("gpuWorker запущен")
        except Exception as e:
            print(f"Ошибка создания gpuWorker: {e}")
        print(f"LoadDocument: gpuWorker создан, running={self.gpuWorker.running}")
        # Устанавливаем первую страницу
        self.currentPage = 0
        self.setPagesCount(self.currentPage)
        self.pdfWindow.pageNavigator().jump(self.currentPage, QPointF(0, 0), 1.0)

        # Запускаем загрузку первой страницы
        self.LoadConvertedPage(self.currentPage)
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
        self.workerQueue.clear()
        # 1. Текущая страница
        if self.convertedPagesCache[self.currentPage] == "" and self.currentPage not in self.conversionInProgress:
            self.workerQueue.append(self.currentPage)
            self.UpdatePageStatus(self.currentPage)
        # 2. Страницы слева
        for i in range(self.currentPage - 1, -1, -1):
            if self.convertedPagesCache[i] == "" and i not in self.conversionInProgress and i not in self.workerQueue:
                self.workerQueue.append(i)
                self.UpdatePageStatus(i)
        # 3. Страницы справа
        for i in range(self.currentPage + 1, self.maxPages):
            if self.convertedPagesCache[i] == "" and i not in self.conversionInProgress and i not in self.workerQueue:
                self.workerQueue.append(i)
                self.UpdatePageStatus(i)
        self.ProcessQueue()   # <-- эта строка должна быть
        
    def PreloadNearbyPages(self, radius=5):
        start = max(0, self.currentPage - radius)
        end = min(self.maxPages, self.currentPage + radius + 1)
        added = False
        for i in range(start, end):
            if i != self.currentPage:
                if self.convertedPagesCache[i] == "" and i not in self.conversionInProgress and i not in self.workerQueue:
                    self.workerQueue.append(i)
                    added = True
        if added:
            self.ProcessQueue()

    def ProcessQueue(self):
        if self.gpuWorker is None:
            print("ProcessQueue: gpuWorker is None")
            return
        if not self.gpuWorker.running:
            print(f"ProcessQueue: gpuWorker.running = {self.gpuWorker.running}")
            return
        if not self.gpuWorker or not self.gpuWorker.running:
            print("ProcessQueue: gpuWorker не готов")
            return
        while self.workerQueue:
            pageIndex = self.workerQueue.pop(0)
            if self.convertedPagesCache[pageIndex] != "" or pageIndex in self.conversionInProgress:
                continue
            self.conversionInProgress.add(pageIndex)
            self.UpdatePageStatus(pageIndex)
            print(f"ProcessQueue: отправляю страницу {pageIndex} в gpuWorker")
            self.gpuWorker.add_page(pageIndex)
        def OnPageConverted(self, pageIndex, text):
            """Callback из рабочего потока - просто пересылает сигнал в главный поток."""
            # Испускаем сигнал чтобы обработка произошла в главном потоке
            self.pageConversionFinished.emit(pageIndex, text)
    
    @Slot(int, str, str, list)
    def _onPageConversionFinished(self, pageIndex, text, html, images):
        if self._is_closing:
            return
        print(f"Главный поток: получена страница {pageIndex}")
        """
        Вызывается из GpuWorker после конвертации страницы.
        text – обычный текст (для индексации)
        html – форматированный HTML (для отображения)
        images – список base64 изображений
        """
        # 1. Убираем страницу из множества "в обработке"
        if pageIndex in self.conversionInProgress:
            self.conversionInProgress.discard(pageIndex)

        # 2. Сохраняем HTML в кэш (для быстрого показа при перелистывании)
        self.convertedPagesCache[pageIndex] = html

        # 3. Запускаем индексацию в CPU-пуле (не блокируем GUI и GPU)
        indexing_task = IndexingTask(self.aiClient, pageIndex, text, images)
        self.cpuPool.start(indexing_task)

        # 4. Обновляем статус в выпадающем списке
        self.UpdatePageStatus(pageIndex, force=(pageIndex == self.currentPage))

        # 5. Если это текущая страница – показываем HTML и убираем индикатор загрузки
        if pageIndex == self.currentPage:
            self.convertedTextView.setHtml(html)
            self.loadingBar.hide()

            # Если есть отложенное выделение текста – применяем
            if self._pendingHighlight:
                self._HighlightSnippet(self._pendingHighlight)
                self._pendingHighlight = ""

            # После загрузки текущей страницы предзагружаем соседние
            self.PreloadNearbyPages(radius=5)

        # 6. Если были отложенные обновления очереди – выполняем
        if self.pendingQueueUpdate:
            self.pendingQueueUpdate = False
            self.UpdateQueueOrder()
        else:
            # Иначе берём следующую страницу из очереди (если есть)
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
        self._is_closing = True
        # Отключаем сигналы, чтобы слоты не вызывались после разрушения
        if self.gpuWorker is not None:
            try:
                self.gpuWorker.pageConverted.disconnect(self._onPageConversionFinished)
            except TypeError:
                pass  # если не был подключён
            self.gpuWorker.running = False
            self.gpuWorker.condition.wakeOne()
            if not self.gpuWorker.wait(3000):  # таймаут 3 секунды
                print("GpuWorker не завершился, принудительно завершаем")
                self.gpuWorker.terminate()
                self.gpuWorker.wait()
        # Для cpuPool – ограничиваем время ожидания
        self.cpuPool.waitForDone(2000)
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
        #self.converterPool.waitForDone()  # Ждем завершения всех задач в пуле потоков
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


