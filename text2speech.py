#!/usr/bin/env python3
"""
text2speech.py - Озвучка книги по абзацам в MP3 файлы
с сетевой устойчивостью и повторными попытками
"""

import argparse
import sys
import os
import asyncio
import edge_tts
from bs4 import BeautifulSoup
import time
from pathlib import Path
import aiohttp
from typing import Optional, Tuple

# ========================= КОНФИГУРАЦИЯ СЕТИ =========================
MAX_RETRIES = 3  # Количество циклов повтора
MAX_ATTEMPTS_PER_PARAGRAPH = 5  # Попыток на один абзац
BASE_TIMEOUT = 60  # Базовая задержка 60 секунд


class NetworkError(Exception):
    """Сетевая ошибка при генерации"""
    pass


# ========================= ПАРСИНГ АРГУМЕНТОВ =========================
def parse_args():
    parser = argparse.ArgumentParser(
        description='Озвучка HTML файла с тегами <p> в MP3 файлы',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s -i book.html                      # озвучка в динамик
  %(prog)s -i book.html -o D:/audio/          # запись в MP3 в папку
  %(prog)s -i book.html -t                    # тестовый прогон
  %(prog)s -i book.html -o ./audio -s +30     # запись с ускорением

При записи в MP3 (-o) воспроизведения нет, только сохранение файлов.
Каждый абзац сохраняется как: папка/000001.mp3, папка/000002.mp3 и т.д.
        """
    )

    parser.add_argument('-i', '--input-file',
                        required=True,
                        help='Входной HTML файл с тегами <p>')

    parser.add_argument('-o', '--output-dir',
                        help='Папка для сохранения MP3 (если указана, воспроизведения нет)')

    parser.add_argument('-t', '--test',
                        action='store_true',
                        help='Тестовый прогон: только статистика, без озвучки')

    parser.add_argument('-s', '--speed',
                        default='+0%',
                        help='Скорость речи: от -70 до +70 (по умолчанию +0)')

    parser.add_argument('-v', '--voice',
                        default='ru-RU-SvetlanaNeural',
                        help='Голос (по умолчанию ru-RU-SvetlanaNeural)')

    return parser.parse_args()


# ========================= ПРОВЕРКА ФАЙЛА =========================
def validate_file(filename):
    """Проверяет существование файла и наличие тегов <p>"""
    if not os.path.exists(filename):
        print(f"Ошибка: файл '{filename}' не найден")
        sys.exit(1)

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
        sys.exit(1)

    # Проверяем наличие тегов <p>
    if '<p>' not in content and '<p ' not in content:
        print(f"Ошибка: в файле '{filename}' нет тегов <p>")
        print("   Файл должен содержать HTML разметку с абзацами")
        sys.exit(1)

    return content


# ========================= ПАРСИНГ АБЗАЦЕВ =========================
def extract_paragraphs(html_content):
    """Извлекает все абзацы из HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')
    paragraphs = soup.find_all('p')

    # Очищаем от пустых
    result = []
    for p in paragraphs:
        text = p.get_text().strip()
        if text:
            result.append({
                'text': text,
                'html': str(p),
                'len': len(text)
            })

    return result


# ========================= СОЗДАНИЕ ПАПКИ =========================
def prepare_output_dir(dir_path):
    """Создает папку для выходных файлов"""
    path = Path(dir_path)
    path.mkdir(parents=True, exist_ok=True)

    # Проверяем доступна ли папка для записи
    if not os.access(path, os.W_OK):
        print(f"Ошибка: нет прав на запись в папку '{dir_path}'")
        sys.exit(1)

    return path


# ========================= ГЕНЕРАЦИЯ С ПОВТОРАМИ =========================
async def generate_with_retry(text: str, voice: str, speed: str,
                              paragraph_num: int, total: int,
                              retry_cycle: int) -> Tuple[bool, Optional[bytes]]:
    """
    Генерирует речь с повторными попытками при сетевых ошибках
    Возвращает (успех, аудио_данные)
    """

    for attempt in range(1, MAX_ATTEMPTS_PER_PARAGRAPH + 1):
        try:
            print(f"  🔄 Попытка {attempt}/{MAX_ATTEMPTS_PER_PARAGRAPH} (цикл {retry_cycle}/{MAX_RETRIES})")

            communicate = edge_tts.Communicate(text, voice, rate=speed)

            # Добавляем таймаут для сетевых операций
            audio_data = b''
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            if not audio_data:
                raise NetworkError("Получен пустой ответ от сервера")

            return True, audio_data

        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, NetworkError) as e:
            # Сетевая ошибка - пробуем снова
            wait_time = BASE_TIMEOUT * attempt  # 60, 120, 180, 240, 300 сек
            print(f"  ⚠️  Сетевая ошибка: {e.__class__.__name__}")
            print(f"  ⏳ Ожидание {wait_time} сек перед повторной попыткой...")

            if attempt < MAX_ATTEMPTS_PER_PARAGRAPH:
                await asyncio.sleep(wait_time)
            else:
                # Последняя попытка не удалась
                print(f"  ❌ Все {MAX_ATTEMPTS_PER_PARAGRAPH} попыток исчерпаны")
                return False, None

        except Exception as e:
            # Другие ошибки (не сетевые) - может быть проблема с текстом
            print(f"  ❌ Критическая ошибка: {e}")
            return False, None

    return False, None


# ========================= ЗАПИСЬ В ФАЙЛ =========================
async def save_paragraph_to_file(text, voice, speed, output_dir, index, total, retry_cycle):
    """Сохраняет абзац в MP3 файл с повторными попытками"""

    # Формируем имя файла: 000001.mp3, 000002.mp3, ...
    filename = f"{index:06d}.mp3"
    filepath = output_dir / filename

    # Проверяем, может файл уже существует (для дозапуска)
    if filepath.exists():
        size = filepath.stat().st_size
        if size > 0:
            print(f"⏩ [{index}/{total}] {filename} уже существует ({size / 1024:.1f} KB) - пропускаем")
            return True, filename, size

    # Генерируем с повторами
    success, audio_data = await generate_with_retry(text, voice, speed, index, total, retry_cycle)

    if not success:
        return False, filename, 0

    # Сохраняем в файл
    filepath.write_bytes(audio_data)
    size = filepath.stat().st_size

    return True, filename, size


# ========================= ОСНОВНАЯ ФУНКЦИЯ =========================
async def main():
    args = parse_args()

    # Проверка: если указан output-dir, отключаем воспроизведение
    save_mode = args.output_dir is not None

    # Валидация
    print(f"Загружаем файл: {args.input_file}")
    content = validate_file(args.input_file)

    # Парсим абзацы
    print("Ищем теги <p>...")
    paragraphs = extract_paragraphs(content)

    if not paragraphs:
        print("Не найдено ни одного непустого абзаца")
        sys.exit(1)

    # Статистика
    total = len(paragraphs)
    total_chars = sum(p['len'] for p in paragraphs)
    avg_len = total_chars / total

    print("\n" + "=" * 70)
    print("СТАТИСТИКА:")
    print(f"  Всего абзацев: {total}")
    print(f"  Всего символов: {total_chars:,}")
    print(f"  Средняя длина: {avg_len:.0f} символов")
    print(f"  Скорость речи: {args.speed}")
    print(f"  Голос: {args.voice}")

    if save_mode:
        # Подготовка папки для сохранения
        output_path = prepare_output_dir(args.output_dir)
        print(f"  Сохранение в: {output_path.absolute()}")
        print(f"  Режим: ЗАПИСЬ В ФАЙЛЫ (без воспроизведения)")
        print(f"  Сетевые настройки:")
        print(f"    • Макс. циклов повтора: {MAX_RETRIES}")
        print(f"    • Попыток на абзац: {MAX_ATTEMPTS_PER_PARAGRAPH}")
        print(f"    • Базовая задержка: {BASE_TIMEOUT} сек")
    else:
        print(f"  Режим: ВОСПРОИЗВЕДЕНИЕ В ДИНАМИК")

    print("=" * 70 + "\n")

    # Тестовый режим - только статистика
    if args.test:
        print("✅ Тестовый прогон завершен. Для работы уберите флаг -t")
        return

    # Основной цикл
    print("🚀 НАЧАЛО РАБОТЫ (Ctrl+C для остановки)\n")

    start_time = time.time()
    failed_paragraphs = []

    try:
        retry_cycle = 1
        while retry_cycle <= MAX_RETRIES:
            print(f"\n{'=' * 50}")
            print(f"ЦИКЛ ПОВТОРА {retry_cycle}/{MAX_RETRIES}")
            print(f"{'=' * 50}")

            for i, p in enumerate(paragraphs, 1):
                # Пропускаем уже успешно обработанные
                if save_mode and hasattr(p, 'processed') and p['processed']:
                    continue

                # Прогресс в консоль
                chars = p['len']
                progress = f"[{i}/{total}] {chars} символов"

                # Сохраняем в файл
                success, filename, size = await save_paragraph_to_file(
                    p['text'], args.voice, args.speed,
                    output_path, i, total, retry_cycle
                )

                if success:
                    p['processed'] = True
                    size_kb = size / 1024
                    print(f"✅ {progress} -> {filename} ({size_kb:.1f} KB)")
                else:
                    print(f"❌ {progress} -> ОШИБКА (абзац {i})")
                    failed_paragraphs.append({
                        'index': i,
                        'text': p['text'][:100] + '...' if len(p['text']) > 100 else p['text'],
                        'retry_cycle': retry_cycle
                    })

            # Проверяем, все ли успешно
            if save_mode:
                processed = sum(1 for p in paragraphs if hasattr(p, 'processed') and p['processed'])
                if processed == total:
                    print(f"\n✅ Все абзацы успешно обработаны на цикле {retry_cycle}")
                    break
                else:
                    if retry_cycle < MAX_RETRIES:
                        print(f"\n⚠️  Обработано {processed}/{total} абзацев")
                        print(f"🔄 Переходим к циклу {retry_cycle + 1}...")
                        await asyncio.sleep(BASE_TIMEOUT)  # Пауза между циклами
                        retry_cycle += 1
                    else:
                        print(f"\n❌ Достигнут лимит циклов повтора ({MAX_RETRIES})")
                        break
            else:
                # Для режима воспроизведения просто идем по порядку
                break

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f"\n\n⏹️  Остановлено пользователем")

        if save_mode:
            processed = sum(1 for p in paragraphs if hasattr(p, 'processed') and p['processed'])
            print(f"\n📊 СТАТИСТИКА ПРЕРЫВАНИЯ:")
            print(f"   Обработано успешно: {processed}/{total}")
            print(f"   Не обработано: {total - processed}")
            print(f"   Время работы: {elapsed:.1f} сек")

            if failed_paragraphs:
                print(f"\n❌ ПРОБЛЕМНЫЕ АБЗАЦЫ:")
                for fail in failed_paragraphs[-10:]:  # последние 10 ошибок
                    print(f"   • Абзац {fail['index']}: {fail['text']}")
        else:
            print(f"Обработано {i - 1} из {total} абзацев за {elapsed:.1f} сек")

        sys.exit(0)

    elapsed = time.time() - start_time

    if save_mode:
        processed = sum(1 for p in paragraphs if hasattr(p, 'processed') and p['processed'])

        print(f"\n{'=' * 70}")
        print("ИТОГОВЫЙ ОТЧЕТ")
        print(f"{'=' * 70}")
        print(f"📊 Статистика:")
        print(f"   Всего абзацев: {total}")
        print(f"   Успешно: {processed}")
        print(f"   С ошибками: {len(failed_paragraphs)}")
        print(f"   Время работы: {elapsed:.1f} сек")

        if processed > 0:
            total_size = sum(f.stat().st_size for f in output_path.glob("*.mp3"))
            total_mb = total_size / (1024 * 1024)
            print(f"\n💾 Файлы:")
            print(f"   Всего файлов: {len(list(output_path.glob('*.mp3')))}")
            print(f"   Общий размер: {total_mb:.1f} MB")
            print(f"   Папка: {output_path.absolute()}")

        if failed_paragraphs:
            print(f"\n❌ СПИСОК ПРОБЛЕМНЫХ АБЗАЦЕВ:")
            for fail in failed_paragraphs:
                print(f"   • [{fail['index']}] (цикл {fail['retry_cycle']}): {fail['text']}")

            # Сохраняем список ошибок в файл
            error_log = output_path / "errors.txt"
            with open(error_log, 'w', encoding='utf-8') as f:
                f.write("ПРОБЛЕМНЫЕ АБЗАЦЫ\n")
                f.write("=" * 50 + "\n")
                for fail in failed_paragraphs:
                    f.write(f"Абзац {fail['index']} (цикл {fail['retry_cycle']}):\n")
                    f.write(f"{fail['text']}\n")
                    f.write("-" * 50 + "\n")
            print(f"\n📝 Подробный лог ошибок: {error_log}")
    else:
        print(f"\n✅ ГОТОВО! Озвучено {total} абзацев за {elapsed:.1f} сек")


# ========================= ЗАПУСК =========================
if __name__ == "__main__":
    asyncio.run(main())