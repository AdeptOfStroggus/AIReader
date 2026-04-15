import sys
import os

# Добавляем корневую директорию в пути поиска модулей, 
# чтобы импорты внутри папки ui работали корректно
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from ui.ui import main

if __name__ == "__main__":
    main()
