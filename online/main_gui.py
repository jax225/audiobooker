# main_gui.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os

from txt2html_module import create_html_from_txt
from tts_module import run_generation

class AudioBookApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AudioBook Maker")
        self.root.geometry("700x550")
        self.root.resizable(True, True)

        # Переменные
        self.txt_path = tk.StringVar()
        self.html_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.voice = tk.StringVar(value="ru-RU-SvetlanaNeural")
        self.speed = tk.StringVar(value="+0%")
        self.start_num = tk.IntVar(value=1)

        self.generation_thread = None
        self.stop_event = threading.Event()

        self.create_widgets()

    def create_widgets(self):
        # Заголовок
        title = tk.Label(self.root, text="AudioBook Maker", font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Notebook (вкладки) или просто фреймы — сделаем два больших фрейма
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ----- ШАГ 1: TXT -> HTML -----
        step1_frame = ttk.LabelFrame(main_frame, text="Шаг 1: TXT → HTML", padding="10")
        step1_frame.pack(fill=tk.X, pady=(0, 10))

        # Выбор TXT
        ttk.Label(step1_frame, text="TXT файл:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(step1_frame, textvariable=self.txt_path, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(step1_frame, text="Обзор", command=self.browse_txt).grid(row=0, column=2)

        # Кнопка создать HTML
        self.btn_create_html = ttk.Button(step1_frame, text="Создать HTML", command=self.create_html)
        self.btn_create_html.grid(row=1, column=1, pady=10)

        self.lbl_html_result = ttk.Label(step1_frame, text="")
        self.lbl_html_result.grid(row=2, column=0, columnspan=3)

        # ----- ШАГ 2: HTML -> MP3 -----
        step2_frame = ttk.LabelFrame(main_frame, text="Шаг 2: HTML → MP3", padding="10")
        step2_frame.pack(fill=tk.BOTH, expand=True)

        # Выбор HTML
        ttk.Label(step2_frame, text="HTML файл:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(step2_frame, textvariable=self.html_path, width=60).grid(row=0, column=1, padx=5)
        ttk.Button(step2_frame, text="Обзор", command=self.browse_html).grid(row=0, column=2)

        # Выбор папки для MP3
        ttk.Label(step2_frame, text="Папка для MP3:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(step2_frame, textvariable=self.output_dir, width=60).grid(row=1, column=1, padx=5)
        ttk.Button(step2_frame, text="Обзор", command=self.browse_output_dir).grid(row=1, column=2)

        # Настройки (голос, скорость, стартовый номер)
        settings_frame = ttk.Frame(step2_frame)
        settings_frame.grid(row=2, column=0, columnspan=3, pady=10, sticky=tk.W)

        ttk.Label(settings_frame, text="Голос:").grid(row=0, column=0, padx=5)
        voice_combo = ttk.Combobox(settings_frame, textvariable=self.voice, width=20,
                                   values=["ru-RU-SvetlanaNeural", "ru-RU-DariyaNeural",
                                           "ru-RU-DmitryNeural", "ru-RU-MikhailNeural"])
        voice_combo.grid(row=0, column=1, padx=5)

        ttk.Label(settings_frame, text="Скорость:").grid(row=0, column=2, padx=5)
        speed_combo = ttk.Combobox(settings_frame, textvariable=self.speed, width=10,
                                   values=["-20%", "-10%", "+0%", "+10%", "+20%", "+30%", "+50%"])
        speed_combo.grid(row=0, column=3, padx=5)

        ttk.Label(settings_frame, text="Начать с номера:").grid(row=0, column=4, padx=5)
        ttk.Entry(settings_frame, textvariable=self.start_num, width=8).grid(row=0, column=5, padx=5)

        # Кнопки запуска и остановки
        btn_frame = ttk.Frame(step2_frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=5)

        self.btn_start = ttk.Button(btn_frame, text="▶ Запустить озвучку", command=self.start_generation)
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ttk.Button(btn_frame, text="🛑 Остановить", command=self.stop_generation, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # Прогресс-бар
        self.progress = ttk.Progressbar(step2_frame, orient=tk.HORIZONTAL, mode='determinate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=5)

        self.lbl_progress = ttk.Label(step2_frame, text="")
        self.lbl_progress.grid(row=5, column=0, columnspan=3)

        # Текстовое поле для лога
        log_frame = ttk.LabelFrame(step2_frame, text="Лог", padding="5")
        log_frame.grid(row=6, column=0, columnspan=3, sticky=tk.NSEW, pady=10)
        step2_frame.rowconfigure(6, weight=1)
        step2_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=12, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def browse_txt(self):
        filename = filedialog.askopenfilename(title="Выберите TXT файл",
                                              filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if filename:
            self.txt_path.set(filename)

    def browse_html(self):
        filename = filedialog.askopenfilename(title="Выберите HTML файл",
                                              filetypes=[("HTML files", "*.html *.htm"), ("All files", "*.*")])
        if filename:
            self.html_path.set(filename)

    def browse_output_dir(self):
        dirname = filedialog.askdirectory(title="Выберите папку для сохранения MP3")
        if dirname:
            self.output_dir.set(dirname)

    def log(self, message):
        """Добавляет сообщение в лог и прокручивает вниз"""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def create_html(self):
        txt = self.txt_path.get().strip()
        if not txt:
            messagebox.showerror("Ошибка", "Выберите TXT файл")
            return

        self.btn_create_html.config(state=tk.DISABLED, text="Обработка...")
        self.lbl_html_result.config(text="")

        def worker():
            success, html_path, msg, count = create_html_from_txt(txt)
            self.root.after(0, self._create_html_done, success, html_path, msg, count)

        threading.Thread(target=worker, daemon=True).start()

    def _create_html_done(self, success, html_path, msg, count):
        self.btn_create_html.config(state=tk.NORMAL, text="Создать HTML")
        if success:
            self.lbl_html_result.config(text=f"✅ {msg} ({count} абзацев)", foreground="green")
            self.html_path.set(html_path)  # автоматически подставляем путь в Шаг 2
            self.log(f"HTML создан: {html_path}")
        else:
            self.lbl_html_result.config(text=f"❌ {msg}", foreground="red")

    def start_generation(self):
        html = self.html_path.get().strip()
        out_dir = self.output_dir.get().strip()

        if not html:
            messagebox.showerror("Ошибка", "Выберите HTML файл")
            return
        if not out_dir:
            messagebox.showerror("Ошибка", "Выберите папку для сохранения MP3")
            return

        # Проверяем, существует ли папка, если нет - создаём
        if not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir)
                self.log(f"📁 Создана папка: {out_dir}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось создать папку:\n{e}")
                return

        # Блокируем кнопки
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.progress['value'] = 0
        self.lbl_progress.config(text="")
        self.log_text.delete(1.0, tk.END)

        self.stop_event.clear()

        # Запускаем генерацию в отдельном потоке
        self.generation_thread = threading.Thread(
            target=self._generation_worker,
            args=(html, out_dir, self.voice.get(), self.speed.get(), self.start_num.get()),
            daemon=True
        )
        self.generation_thread.start()

    def _generation_worker(self, html, out_dir, voice, speed, start_num):
        def log_callback(msg):
            self.root.after(0, self.log, msg)

        def progress_callback(current, total):
            self.root.after(0, self._update_progress, current, total)

        try:
            result = run_generation(
                html_path=html,
                output_dir=out_dir,
                voice=voice,
                speed=speed,
                start_from=start_num,
                log_callback=log_callback,
                progress_callback=progress_callback,
                stop_event=self.stop_event
            )
            self.root.after(0, self._generation_done, result)
        except Exception as e:
            self.root.after(0, self._generation_error, str(e))

    def _update_progress(self, current, total):
        self.progress['maximum'] = total
        self.progress['value'] = current
        self.lbl_progress.config(text=f"{current} / {total}")

    def _generation_done(self, success):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        if success:
            self.log("🎉 Генерация завершена успешно!")
        else:
            self.log("⚠️ Генерация завершена с ошибками или была остановлена.")

    def _generation_error(self, error_msg):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.log(f"❌ Критическая ошибка: {error_msg}")

    def stop_generation(self):
        self.stop_event.set()
        self.btn_stop.config(state=tk.DISABLED)
        self.log("⏹ Отправлен сигнал остановки...")

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioBookApp(root)
    root.mainloop()