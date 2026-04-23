# txt2html_module.py
import os
import sys

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

        # Разбивка на абзацы (твоя логика)
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
            # exe режим
            exe_dir = os.path.dirname(sys.executable)
        else:
            # обычный Python
            exe_dir = os.path.dirname(os.path.abspath(__file__))

        base_name = os.path.splitext(os.path.basename(txt_path))[0]
        html_path = os.path.join(exe_dir, base_name + ".html")

        # Собираем HTML
        html_content = ""
        for p in paragraphs:
            clean_p = ' '.join(p.split())
            html_content += f"<p>{clean_p}</p>\n"

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return True, html_path, f"Создан HTML: {os.path.basename(html_path)}", len(paragraphs)

    except FileNotFoundError:
        return False, "", f"Файл не найден: {txt_path}", 0
    except Exception as e:
        return False, "", f"Ошибка: {e}", 0