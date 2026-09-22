# stress_module.py
import sys
import os
import re
from silero_stress import load_accentor
"""
Модуль расстановки ударений.
Если silero_stress недоступен — работает как «проходной» (текст без изменений),
чтобы GUI оставался рабочим.
"""

def get_base_path():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))




HAS_ACCENTOR = False
_accentor = None
_import_error = ""

try:
    from silero_stress import load_accentor
    # Если silero_stress требует путь, можно передать его:
    # _accentor = load_accentor(model_path=os.path.join(get_base_path(), 'silero_stress_model'))
    _accentor = load_accentor()
    HAS_ACCENTOR = True
except Exception as e:
    _import_error = str(e)


# ---------- Глоссарий (пока пустой — на будущее) ----------
GLOSSARY = {}

if GLOSSARY:
    _PAT = re.compile(
        r'\b(' + '|'.join(re.escape(k) for k in GLOSSARY) + r')([а-яё]*)',
        flags=re.IGNORECASE,
    )
else:
    _PAT = None


def _apply_case(stressed: str, is_capitalized: bool) -> str:
    for i, ch in enumerate(stressed):
        if ch.isalpha():
            if is_capitalized:
                return stressed[:i] + ch.upper() + stressed[i + 1:]
            return stressed[:i] + ch.lower() + stressed[i + 1:]
    return stressed


def stress_with_glossary(text: str) -> str:
    placeholders = []

    def _protect(m):
        base = m.group(1).lower()
        ending = m.group(2)
        stressed_form = GLOSSARY[base] + ending
        stressed_form = _apply_case(stressed_form, m.group(1)[0].isupper())
        tag = f"ZZGLOS{len(placeholders)}ZZ"
        placeholders.append(stressed_form)
        return tag

    protected = _PAT.sub(_protect, text) if _PAT else text
    stressed = _accentor(protected)

    for i, form in enumerate(placeholders):
        stressed = stressed.replace(f"ZZGLOS{i}ZZ", form)
    return stressed


def stress_text(text: str) -> str:
    """Безопасная обёртка: если accentor не загружен — возвращает текст как есть."""
    if not HAS_ACCENTOR or _accentor is None:
        return text
    try:
        return stress_with_glossary(text)
    except Exception:
        return text