# txt2html_module.py
import os
import re
import sys


def extract_chapter_title(text):
    """
    Ищет конструкцию 'Глава [номер]. название' в тексте чанка.
    Возвращает строку вида 'Глава_2_Появление_в_деревне' или None.
    Берёт не более 7 слов названия, пробелы заменяет на '_'.
    Если в чанке несколько глав — берётся только первая (re.search
    находит первое совпадение).
    """
    pattern = r'Глава\s+(\d+)\s*\.\s*(.+?)(?:\.|$)'
    match = re.search(pattern, text)
    if not match:
        return None

    number = match.group(1)
    title_text = match.group(2).strip()

    # Не более 7 слов
    words = title_text.split()
    if len(words) > 7:
        words = words[:7]

    # Пробелы → подчёркивания
    title = '_'.join(words)

    # Удаляем символы, недопустимые в именах файлов
    title = re.sub(r'[\\/:*?"<>|]', '', title)

    return f"Глава_{number}_{title}"


def create_html_from_txt(txt_path, min_size=700, search_radius=200):
    """
    Читает TXT, разбивает на абзацы, сохраняет HTML.
    Возвращает (success: bool, html_path: str, message: str, paragraphs_count: int)
    """
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read().strip()

        if not text:
            return False, "", "Файл пуст", 0

        # Разбивка на абзацы
        def split_into_paragraphs(text, min_size, radius):
            if len(text) <= min_size:
                return [text]
            paragraphs = []
            start = 0
            text_length = len(text)
            while start < text_length:
                end = min(start + min_size, text_length)
                if end < text_length:
                    search_end = min(end + radius, text_length)
                    best_pos = -1
                    for pos in range(search_end - 1, end - 1, -1):
                        if pos < text_length and text[pos] in '.!?':
                            if pos + 1 >= text_length or text[pos + 1].isspace() or text[pos + 1] == '\n':
                                best_pos = pos
                                break
                    if best_pos != -1:
                        end = best_pos + 1
                    else:
                        for pos in range(search_end - 1, end - 1, -1):
                            if pos < text_length and text[pos].isspace():
                                end = pos + 1
                                break
                paragraph = text[start:end].strip()
                if paragraph:
                    paragraphs.append(paragraph)
                start = end
            return paragraphs

        paragraphs = split_into_paragraphs(text, min_size, search_radius)

        # Определяем папку запуска (работает и в .py, и в .exe)
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))

        base_name = os.path.splitext(os.path.basename(txt_path))[0]
        html_path = os.path.join(exe_dir, base_name + ".html")

        # Собираем HTML с определением глав
        html_content = ""
        for p in paragraphs:
            clean_p = ' '.join(p.split())
            chapter = extract_chapter_title(clean_p)
            if chapter:
                html_content += f'<p data-chapter="{chapter}">{clean_p}</p>\n'
            else:
                html_content += f"<p>{clean_p}</p>\n"

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return True, html_path, f"Создан HTML: {os.path.basename(html_path)}", len(paragraphs)

    except FileNotFoundError:
        return False, "", f"Файл не найден: {txt_path}", 0
    except Exception as e:
        return False, "", f"Ошибка: {e}", 0
