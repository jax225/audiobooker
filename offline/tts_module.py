# tts_module.py
import os
import re
import sys
import threading
from pathlib import Path

import numpy as np
import soundfile as sf
import torch


def get_base_path():
    """Возвращает путь к папке с ресурсами (в exe или в проекте)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

# ==================== НАСТРОЙКИ ====================
SPEAKER_MODEL = 'v5_5_ru'          # имя модели Silero
MODEL_FILE    = f"{SPEAKER_MODEL}.pt"
SAMPLE_RATE   = 48000
# ====================================================

_model = None
_model_lock = threading.Lock()

SPEED_MAP = {
    "-20%": "x-slow",
    "-10%": "slow",
    "+0%":  "medium",
    "+10%": "fast",
    "+20%": "x-fast",
    "+30%": "x-fast",
    "+50%": "x-fast",
}


def _get_model():
    """Ленивая загрузка локальной модели Silero из v5_5_ru.pt."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                model_path = os.path.join(get_base_path(), MODEL_FILE)
                print(f"Загрузка модели из {model_path}…")
                _model = torch.package.PackageImporter(model_path).load_pickle(
                    "tts_models", "model"
                )
                _model.to(torch.device("cpu"))
                print("Модель загружена.")
    return _model


def _extract_paragraphs(html_content):
    """
    Извлекает абзацы из HTML без сторонних библиотек.
    Возвращает список dict: {'text': str, 'chapter': str}.
    """
    paragraphs = []
    for m in re.finditer(r'<p([^>]*)>(.*?)</p>', html_content, re.DOTALL | re.IGNORECASE):
        attrs = m.group(1)
        text  = m.group(2).strip()
        if not text:
            continue
        chapter = ''
        ch = re.search(r'data-chapter="([^"]*)"', attrs)
        if ch:
            chapter = ch.group(1)
        paragraphs.append({'text': text, 'chapter': chapter})
    return paragraphs


def _synthesize(text, voice, speed, model):
    """Синтез одного абзаца. Возвращает numpy-массив float32."""
    rate = SPEED_MAP.get(speed, "medium")
    # Silero v5 поддерживает SSML. Оборачиваем текст для управления скоростью.
    ssml_text = f'<speak><prosody rate="{rate}">{text}</prosody></speak>'

    audio = model.apply_tts(
        ssml_text=ssml_text,
        speaker=voice,
        sample_rate=SAMPLE_RATE,
    )

    if hasattr(audio, "numpy"):
        audio = audio.numpy()
    return np.asarray(audio, dtype=np.float32)


def run_generation(html_path, output_dir, voice, speed, start_from,
                   log_callback=None, progress_callback=None, stop_event=None):
    """
    Синхронная генерация MP3 из HTML через Silero TTS.
    Интерфейс совместим с вызовом из main_gui.py.
    """

    if stop_event is None:
        stop_event = threading.Event()

    # --- читаем HTML ---
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        if log_callback:
            log_callback(f"❌ Ошибка чтения HTML: {e}")
        return False

    paragraphs = _extract_paragraphs(content)
    if not paragraphs:
        if log_callback:
            log_callback("❌ Не найдено ни одного абзаца <p>")
        return False

    total_all = len(paragraphs)
    start_idx = max(0, start_from - 1)
    if start_idx >= total_all:
        if log_callback:
            log_callback(f"❌ start-from {start_from} больше общего числа абзацев ({total_all})")
        return False

    paragraphs = paragraphs[start_idx:]
    total = len(paragraphs)
    first_num = start_idx + 1

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if log_callback:
        log_callback(f"📖 Всего абзацев: {total_all}, начинаем с {first_num}, будет обработано: {total}")
        log_callback(f"📁 Сохранение в: {output_path.absolute()}")

    # --- грузим модель (один раз) ---
    try:
        model = _get_model()
    except Exception as e:
        if log_callback:
            log_callback(f"❌ Ошибка загрузки модели: {e}")
        return False

    processed = 0
    failed    = []

    for i, p in enumerate(paragraphs):
        if stop_event.is_set():
            if log_callback:
                log_callback("⏹ Остановлено пользователем")
            return False

        file_num = first_num + i
        chapter  = p['chapter']

        if chapter:
            filename = f"{file_num:06d}_{chapter}.mp3"
        else:
            filename = f"{file_num:06d}.mp3"

        filepath = output_path / filename

        # Пропускаем уже готовые файлы
        if filepath.exists() and filepath.stat().st_size > 0:
            size = filepath.stat().st_size
            if log_callback:
                log_callback(
                    f"⏩ [{file_num:06d}/{total_all:06d}] {filename} "
                    f"уже существует ({size/1024:.1f} KB) - пропускаем"
                )
            processed += 1
            if progress_callback:
                progress_callback(processed, total)
            continue

        if log_callback:
            log_callback(f"🎤 [{file_num:06d}/{total_all:06d}] Генерация...")

        try:
            audio = _synthesize(p['text'], voice, speed, model)
            sf.write(filepath, audio, SAMPLE_RATE)
            size = filepath.stat().st_size
            if log_callback:
                log_callback(
                    f"✅ [{file_num:06d}/{total_all:06d}] {filename} "
                    f"сохранен ({size/1024:.1f} KB)"
                )
            processed += 1
        except Exception as e:
            if log_callback:
                log_callback(f"❌ [{file_num:06d}/{total_all:06d}] Ошибка: {e}")
            failed.append(file_num)

        if progress_callback:
            progress_callback(processed, total)

    if failed:
        if log_callback:
            log_callback(f"⚠️ Не удалось сгенерировать {len(failed)} абзацев: {failed}")
        return False

    if log_callback:
        log_callback("🎉 Генерация завершена успешно!")
    return True