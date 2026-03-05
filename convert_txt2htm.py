# -*- coding: utf-8 -*-
import os
import re

# Имя входного файла
input_filename = "d:\\Users\\admin\\Downloads\\125\\new1123.txt"
# Имя выходного файла (то же имя, но с расширением .html)
output_filename = "d:\\Users\\admin\\Downloads\\125\\new11233_100.html"


def split_into_paragraphs(text, min_size=100):
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
            # Ищем в радиусе +200 символов (чтобы не резать по слогам)
            search_end = min(end + 200, text_length)

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
    # Читаем текст из файла
    with open(input_filename, 'r', encoding='utf-8') as file:
        text = file.read()

    # Убираем лишние пробелы в начале и конце
    text = text.strip()

    if not text:
        print("Файл пуст")
        exit()

    # Разбиваем на абзацы по ~100 символов
    paragraphs = split_into_paragraphs(text, 100)

    # Оборачиваем каждый абзац в тег <p>
    html_content = ""
    for para in paragraphs:
        if para:
            # Заменяем переносы строк внутри абзаца на пробелы
            para = ' '.join(para.split())
            html_content += f"<p>{para}</p>\n"

    # Записываем результат в HTML-файл
    with open(output_filename, 'w', encoding='utf-8') as file:
        file.write(html_content)

    # Статистика
    print(f"Файл успешно создан: {output_filename}")
    print(f"Всего символов в исходном тексте: {len(text)}")
    print(f"Получилось абзацев: {len(paragraphs)}")

    # Показываем примеры, где были проблемы
    print("\nПроверка спорных мест (должны быть целыми):")

    # Ищем в тексте эти фрагменты и показываем, как они теперь выглядят
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
                print(f"✓ '{phrase[:30]}...' найден в абзаце {i + 1} (целиком)")
                found = True
                break
        if not found:
            print(f"✗ '{phrase[:30]}...' НЕ НАЙДЕН (проблема!)")

except FileNotFoundError:
    print(f"Ошибка: Файл {input_filename} не найден в текущей папке.")
    print(f"Текущая папка: {os.getcwd()}")
except Exception as e:
    print(f"Произошла ошибка: {e}")