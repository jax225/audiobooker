# txt2html_module.py
import os
import re
import sys

try:
    from stress_module import stress_text, HAS_ACCENTOR
except Exception:
    def stress_text(t):
        return t
    HAS_ACCENTOR = False


# ==================== НАСТРОЙКИ ====================
# Правь здесь. Размеры — в символах ИСХОДНОГО текста (до ударений).
MIN_CHUNK_SIZE = 600    # целевой размер чанка
MAX_CHUNK_SIZE = 999    # жёсткий потолок: чанк НИКОГДА не превысит это
SEARCH_RADIUS  = 200    # окно поиска точки/пробела ПОСЛЕ целевого размера
#
# ⚠️ После расстановки ударений текст удлиняется примерно на 10–15%,
#    поэтому реальный размер <p> в HTML будет больше MIN_CHUNK_SIZE.
#    Если в HTML видишь чанки > 1000 — уменьшай MAX_CHUNK_SIZE.
# ====================================================


def extract_chapter_title(text):
    """Ищет 'Глава [номер]. название' — берёт не более 7 слов, '_' вместо пробелов."""
    pattern = r'Глава\s+(\d+)\s*\.\s*(.+?)(?:\.|$)'
    match = re.search(pattern, text)
    if not match:
        return None

    number = match.group(1)
    title_text = match.group(2).strip()
    words = title_text.split()
    if len(words) > 7:
        words = words[:7]
    title = '_'.join(words)
    title = re.sub(r'[\\/:*?"<>|]', '', title)
    return f"Глава_{number}_{title}"


def split_into_paragraphs(text,
                          min_size=MIN_CHUNK_SIZE,
                          max_size=MAX_CHUNK_SIZE,
                          radius=SEARCH_RADIUS):
    """
    Режет текст на чанки.
    Гарантии:
      • длина каждого чанка НЕ превышает max_size (жёсткое ограничение);
      • стараемся завершать чанк на . ! ? — или хотя бы на пробеле;
      • последний чанк может быть короче min_size — это конец файла.
    """
    text_length = len(text)

    # Короткий файл — отдаём целиком
    if text_length <= min_size:
        return [text]

    paragraphs = []
    start = 0

    while start < text_length:
        remaining = text_length - start

        # Хвост влезает целиком — забираем и выходим
        if remaining <= max_size:
            chunk = text[start:].strip()
            if chunk:
                paragraphs.append(chunk)
            break

        target     = start + min_size
        hard_limit = start + max_size

        # Окно поиска: [target, target+radius], но не дальше hard_limit
        search_end = min(target + radius, hard_limit, text_length)

        end = -1

        # 1) Ищем конец предложения (. ! ?), за которым идёт пробел/конец текста
        for pos in range(search_end - 1, target - 1, -1):
            if text[pos] in '.!?':
                if pos + 1 >= text_length or text[pos + 1].isspace():
                    end = pos + 1
                    break

        # 2) Точки нет — ищем просто пробел
        if end == -1:
            for pos in range(search_end - 1, target - 1, -1):
                if text[pos].isspace():
                    end = pos + 1
                    break

        # 3) Совсем не повезло — жёсткая обрезка по целевому размеру
        if end == -1:
            end = target

        # Финальная страховка (на всякий случай)
        if end > hard_limit:
            end = hard_limit

        chunk = text[start:end].strip()
        if chunk:
            paragraphs.append(chunk)
        start = end

    return paragraphs


def create_html_from_txt(txt_path,
                         min_size=MIN_CHUNK_SIZE,
                         max_size=MAX_CHUNK_SIZE,
                         search_radius=SEARCH_RADIUS,
                         log_callback=None):
    """
    Читает TXT, режет на чанки, расставляет ударения, собирает HTML (<p>...</p>)
    и сохраняет рядом с программой.
    Возвращает (success, html_path, message, paragraphs_count).
    """
    def _log(msg):
        if log_callback:
            log_callback(msg)

    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read().strip()

        if not text:
            return False, "", "Файл пуст", 0

        # 1) Нарезаем на чанки
        paragraphs = split_into_paragraphs(text, min_size, max_size, search_radius)
        total = len(paragraphs)

        if HAS_ACCENTOR:
            _log(f"🔤 Расстановка ударений включена. Чанков: {total}")
        else:
            _log(f"⚠️ silero_stress не загружен — ударения не расставляются. Чанков: {total}")
        _log(f"📐 min={min_size}, max={max_size}, radius={search_radius}")

        # 2) Ударения + определение главы → сразу копим HTML
        html_content = ""
        for i, p in enumerate(paragraphs):
            clean_p = ' '.join(p.split())            # нормализуем пробелы

            # Главу ищем ДО расстановки ударений — на исходном тексте
            chapter = extract_chapter_title(clean_p)

            if HAS_ACCENTOR:
                try:
                    clean_p = stress_text(clean_p)
                except Exception as e:
                    _log(f"⚠️ Чанк {i+1}: ошибка ударений: {e}")

            if chapter:
                html_content += f'<p data-chapter="{chapter}">{clean_p}</p>\n'
            else:
                html_content += f"<p>{clean_p}</p>\n"

            _log(f"✍️ [{i+1}/{total}] чанк обработан (raw={len(p)} → final={len(clean_p)})")

        # 3) Сохраняем рядом с программой (.py или .exe)
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))

        base_name = os.path.splitext(os.path.basename(txt_path))[0]
        html_path = os.path.join(exe_dir, base_name + ".html")

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        _log(f"💾 HTML сохранён: {html_path}")
        return True, html_path, f"Создан HTML: {os.path.basename(html_path)}", total

    except FileNotFoundError:
        return False, "", f"Файл не найден: {txt_path}", 0
    except Exception as e:
        return False, "", f"Ошибка: {e}", 0