# -*- coding: utf-8 -*-

import os
import re

# ============= НАСТРАИВАЕМЫЕ КОНСТАНТЫ =============
INPUT_FILE = "C:\\Python\\audiobooker\\job_txt\\new1123.txt"  # имя входного файла (обязательно)
OUTPUT_FILE = ""  # если пусто, создается рядом с входным

MIN_PARAGRAPH_SIZE = 700  # минимальный размер абзаца в символах
SEARCH_RADIUS = 200  # на сколько символов искать конец предложения


# ===================================================

def split_into_paragraphs(text, min_size=MIN_PARAGRAPH_SIZE, radius=SEARCH_RADIUS):
    """
    Разбивает текст на абзацы примерно по min_size символов,
    строго по концам предложений (. ! ? с последующим пробелом или концом строки)
    """
    if len(text) <= min_size:
        return [text]

    paragraphs = []
    start = 0
    text_length = len(text)

    while start < text_length:
        # Определяем минимальный конец абзаца
        end = min(start + min_size, text_length)

        # Если это не последний абзац, ищем конец предложения
        if end < text_length:
            # Ищем в радиусе +radius символов
            search_end = min(end + radius, text_length)

            # Ищем позицию КОНЦА ПРЕДЛОЖЕНИЯ (.!? после которых пробел или конец строки)
            best_pos = -1

            # Перебираем все возможные позиции от search_end до end
            for pos in range(search_end - 1, end - 1, -1):
                # Проверяем, что текущий символ - знак конца предложения
                if pos < text_length and text[pos] in '.!?':
                    # Проверяем, что после знака либо конец текста, либо пробел, либо перенос строки
                    if pos + 1 >= text_length or text[pos + 1].isspace() or text[pos + 1] == '\n':
                        best_pos = pos
                        break

            # Если нашли конец предложения
            if best_pos != -1:
                end = best_pos + 1  # включаем знак
            else:
                # Если не нашли ни одного конца предложения, ищем ближайший пробел
                for pos in range(search_end - 1, end - 1, -1):
                    if pos < text_length and text[pos].isspace():
                        end = pos + 1
                        break

        # Добавляем абзац
        paragraph = text[start:end].strip()
        if paragraph:
            paragraphs.append(paragraph)
        start = end

    return paragraphs


try:
    # Проверяем, что входной файл указан
    if not INPUT_FILE:
        print("❌ Ошибка: INPUT_FILE не указан!")
        exit()

    # Читаем текст из файла
    with open(INPUT_FILE, 'r', encoding='utf-8') as file:
        text = file.read()

    # Убираем лишние пробелы в начале и конце
    text = text.strip()

    if not text:
        print("❌ Файл пуст")
        exit()

    # Определяем имя выходного файла
    output_file = OUTPUT_FILE
    if not output_file:
        # Берем имя входного файла без расширения и добавляем .html
        base_name = os.path.splitext(INPUT_FILE)[0]
        output_file = base_name + ".html"
        print(f"ℹ️ OUTPUT_FILE не задан, будет создан: {output_file}")

    # Разбиваем на абзацы
    paragraphs = split_into_paragraphs(text, MIN_PARAGRAPH_SIZE, SEARCH_RADIUS)

    # Оборачиваем каждый абзац в тег <p>
    html_content = ""
    for para in paragraphs:
        if para:
            # Заменяем переносы строк внутри абзаца на пробелы
            para = ' '.join(para.split())
            html_content += f"<p>{para}</p>\n"

    # Записываем результат в HTML-файл
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(html_content)

    # Статистика
    print(f"✅ Файл успешно создан: {output_file}")
    print(f"📊 Всего символов в исходном тексте: {len(text)}")
    print(f"📊 Получилось абзацев: {len(paragraphs)}")
    print(f"⚙️ Настройки: минимальный размер = {MIN_PARAGRAPH_SIZE}, радиус поиска = {SEARCH_RADIUS}")

    # Показываем примеры первых 3 абзацев
    print("\n🔍 Первые 3 абзаца:")
    for i, para in enumerate(paragraphs[:3], 1):
        print(f"  {i}. {len(para)} символов: {para[:100]}...")

    # Проверка проблемных мест из примера
    print("\n🔍 Проверка целостности предложений:")
    check_phrases = [
        "Евгения Баранова, Александра Бурдакова, Егора Виноградова",
        "Илону и Сергея Спилберг, Елену Цыганову",
        "дорога назад",
        "возможность вернуться",
        "на кону высоки"
    ]

    for phrase in check_phrases:
        found = False
        for i, para in enumerate(paragraphs):
            if phrase in para:
                print(f"  ✓ '{phrase}' найден в абзаце {i + 1}")
                found = True
                break
        if not found:
            print(f"  ✗ '{phrase}' НЕ НАЙДЕН (проблема!)")

except FileNotFoundError:
    print(f"❌ Ошибка: Файл {INPUT_FILE} не найден в текущей папке.")
    print(f"📁 Текущая папка: {os.getcwd()}")
except Exception as e:
    print(f"❌ Произошла ошибка: {e}")