## 🔧 Как собрать EXE-файл

### 1. Установите зависимости
Убедитесь, что установлены `pyinstaller` и остальные библиотеки:
```bash
pip install pyinstaller edge-tts beautifulsoup4 aiohttp
```

### 2. Выполните команду сборки
Откройте терминал в папке с проектом и вставьте:

```bash
pyinstaller --onefile --windowed --name "AudioBookMaker" --hidden-import aiohttp --hidden-import edge_tts --hidden-import bs4 main_gui.py
```

**Что значат флаги:**
- `--onefile` – всё упаковывается в один EXE.
- `--windowed` – не показывать чёрное окно консоли при запуске.
- `--name` – имя выходного EXE-файла.
- `--hidden-import` – подключает модули, которые PyInstaller может пропустить.

### 3. Где найти результат
Готовый EXE-файл появится в папке `dist` внутри вашего проекта.

---

Всё, можете запускать `AudioBookMaker.exe` на любом Windows без Python.