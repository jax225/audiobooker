# tts_module.py
import asyncio
import edge_tts
from bs4 import BeautifulSoup
from pathlib import Path
import aiohttp
import threading

MAX_RETRIES = 3
MAX_ATTEMPTS_PER_PARAGRAPH = 5
BASE_TIMEOUT = 60


class NetworkError(Exception):
    pass


def extract_paragraphs(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    paragraphs = soup.find_all('p')
    result = []
    for p in paragraphs:
        text = p.get_text().strip()
        if text:
            chapter = p.get('data-chapter', '')
            result.append({'text': text, 'len': len(text), 'chapter': chapter})
    return result


async def generate_with_retry(text, voice, speed, paragraph_num, total, retry_cycle):
    for attempt in range(1, MAX_ATTEMPTS_PER_PARAGRAPH + 1):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=speed)
            audio_data = b''
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            if not audio_data:
                raise NetworkError("Пустой ответ")
            return True, audio_data
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError, NetworkError) as e:
            wait_time = BASE_TIMEOUT * attempt
            if attempt < MAX_ATTEMPTS_PER_PARAGRAPH:
                await asyncio.sleep(wait_time)
            else:
                return False, None
        except Exception as e:
            return False, None
    return False, None


async def save_paragraph_to_file(text, voice, speed, output_dir, index, total,
                                 retry_cycle, log_callback, chapter=''):
    # Формируем имя файла: с главой или без
    if chapter:
        filename = f"{index:06d}_{chapter}.mp3"
    else:
        filename = f"{index:06d}.mp3"
    filepath = output_dir / filename

    if filepath.exists() and filepath.stat().st_size > 0:
        size = filepath.stat().st_size
        msg = f"⏩ [{index:06d}/{total:06d}] {filename} уже существует ({size/1024:.1f} KB) - пропускаем"
        if log_callback:
            log_callback(msg)
        return True, filename, size

    msg = f"🎤 [{index:06d}/{total:06d}] Генерация..."
    if log_callback:
        log_callback(msg)

    success, audio_data = await generate_with_retry(text, voice, speed, index, total, retry_cycle)

    if success and audio_data:
        filepath.write_bytes(audio_data)
        size = filepath.stat().st_size
        msg = f"✅ [{index:06d}/{total:06d}] {filename} сохранен ({size/1024:.1f} KB)"
        if log_callback:
            log_callback(msg)
        return True, filename, size
    else:
        msg = f"❌ [{index:06d}/{total:06d}] Ошибка генерации"
        if log_callback:
            log_callback(msg)
        return False, filename, 0


async def _async_generate(html_path, output_dir, voice, speed, start_from,
                          log_callback, progress_callback, stop_event):
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        if log_callback:
            log_callback(f"❌ Ошибка чтения HTML: {e}")
        return False

    all_paragraphs = extract_paragraphs(content)
    if not all_paragraphs:
        if log_callback:
            log_callback("❌ Не найдено ни одного абзаца <p>")
        return False

    total_all = len(all_paragraphs)
    start_idx = max(0, start_from - 1)
    if start_idx >= total_all:
        if log_callback:
            log_callback(f"❌ start-from {start_from} больше общего числа абзацев ({total_all})")
        return False

    paragraphs = all_paragraphs[start_idx:]
    total = len(paragraphs)
    first_num = start_idx + 1

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if log_callback:
        log_callback(f"📖 Всего абзацев: {total_all}, начинаем с {first_num}, будет обработано: {total}")
        log_callback(f"📁 Сохранение в: {output_path.absolute()}")

    processed_count = 0
    failed_paragraphs = []

    try:
        retry_cycle = 1
        while retry_cycle <= MAX_RETRIES:
            if stop_event.is_set():
                if log_callback:
                    log_callback("⏹ Остановлено пользователем")
                return False

            if log_callback:
                log_callback(f"🔄 ЦИКЛ ПОВТОРА {retry_cycle}/{MAX_RETRIES}")

            for idx, p in enumerate(paragraphs):
                if stop_event.is_set():
                    if log_callback:
                        log_callback("⏹ Остановлено пользователем")
                    return False

                file_num = first_num + idx

                # Проверяем, не был ли уже успешно обработан в этом запуске
                if p.get('processed'):
                    continue

                success, filename, size = await save_paragraph_to_file(
                    p['text'], voice, speed, output_path, file_num, total_all,
                    retry_cycle, log_callback, p.get('chapter', '')
                )

                if success:
                    p['processed'] = True
                    processed_count += 1
                    if progress_callback:
                        progress_callback(processed_count, total)
                else:
                    failed_paragraphs.append({
                        'number': file_num,
                        'text': p['text'][:100] + '...'
                    })

            # Проверяем, все ли успешно
            processed = sum(1 for p in paragraphs if p.get('processed', False))
            if processed == total:
                if log_callback:
                    log_callback(f"✅ Все абзацы успешно обработаны")
                break
            else:
                if retry_cycle < MAX_RETRIES:
                    if log_callback:
                        log_callback(f"⚠️ Обработано {processed}/{total}, переходим к следующему циклу...")
                    await asyncio.sleep(BASE_TIMEOUT)
                    retry_cycle += 1
                else:
                    if log_callback:
                        log_callback(f"❌ Достигнут лимит циклов ({MAX_RETRIES})")
                    break

        return True

    except Exception as e:
        if log_callback:
            log_callback(f"❌ Критическая ошибка: {e}")
        return False


def run_generation(html_path, output_dir, voice, speed, start_from,
                   log_callback=None, progress_callback=None, stop_event=None):
    """
    Оборачивает асинхронную функцию для вызова из синхронного кода.
    Запускается в отдельном потоке GUI.
    """
    if stop_event is None:
        stop_event = threading.Event()

    async def _run():
        return await _async_generate(html_path, output_dir, voice, speed, start_from,
                                      log_callback, progress_callback, stop_event)

    # Создаём новый event loop для этого потока
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run())
        return result
    finally:
        loop.close()
