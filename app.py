"""Desktop Telegram history link exporter. Python 3.10+."""
import asyncio
import os
import sys
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser
import time

from links import extract_links, export_links
from scanner import MODES, scan_messages
from app_paths import export_directory, session_directory


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Telegram → ссылки — 1.3 (быстрый поиск)')
        self.geometry('880x600')
        self.minsize(820, 570)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.running = False
        self.result = None
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Ссылки из Telegram', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Три режима поиска • Без повторов • TXT + кликабельный HTML').pack(anchor='w', pady=(4, 18))
        self.values = {}
        for key, label, default in [
            ('api_id', 'API ID', os.getenv('TG_API_ID', '')),
            ('api_hash', 'API Hash', os.getenv('TG_API_HASH', '')),
            ('phone', 'Телефон с кодом страны', ''),
            ('chat', 'Чат: @имя, t.me/имя или числовой ID', '@pl_warszawa_rabota'),
            ('folder', 'Папка результатов', str(export_directory())),
        ]:
            row = ttk.Frame(frame)
            row.pack(fill='x', pady=4)
            ttk.Label(row, text=label, width=36).pack(side='left')
            variable = tk.StringVar(value=default)
            self.values[key] = variable
            add_input(row, textvariable=variable, show='*' if key == 'api_hash' else '')
            if key == 'folder':
                ttk.Button(row, text='…', width=3, command=self.pick_folder).pack(side='left')
        ttk.Button(frame, text='Получить API ID / Hash', command=lambda: webbrowser.open('https://my.telegram.org/apps')).pack(anchor='w', pady=8)
        self.mode = tk.StringVar(value='Полная история')
        self.mode_box = ttk.Combobox(frame, textvariable=self.mode, values=list(MODES), state='readonly', width=42)
        self.mode_box.pack(anchor='w')
        self.mode_description = tk.StringVar(value=MODES[self.mode.get()])
        self.mode_box.bind('<<ComboboxSelected>>', lambda event: self.mode_description.set(MODES[self.mode.get()]))
        ttk.Label(frame, textvariable=self.mode_description, wraplength=780).pack(anchor='w', pady=6)
        actions = ttk.Frame(frame)
        actions.pack(fill='x', pady=10)
        self.start_button = ttk.Button(actions, text='Собрать ссылки', command=self.start)
        self.start_button.pack(side='left')
        self.cancel_button = ttk.Button(actions, text='Остановить', command=self.stop.set, state='disabled')
        self.cancel_button.pack(side='left', padx=8)
        self.open_button = ttk.Button(actions, text='Открыть результат', command=self.open_result, state='disabled')
        self.open_button.pack(side='left')
        self.status = tk.StringVar(value='Введите данные и нажмите «Собрать ссылки».')
        ttk.Label(frame, textvariable=self.status, wraplength=640).pack(anchor='w', pady=8)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)

    def pick_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.values['folder'].set(folder)

    def start(self):
        values = {key: value.get().strip() for key, value in self.values.items()}
        values['mode'] = self.mode.get()
        if not values['api_id'].isdigit() or int(values['api_id']) <= 0 or not re.fullmatch(r'[a-fA-F0-9]{32}', values['api_hash']):
            messagebox.showerror('Данные API', 'Введите числовой API ID и API Hash (32 шестнадцатеричных символа).')
            return
        if not all(values[key] for key in ('phone', 'chat', 'folder')):
            messagebox.showerror('Данные', 'Заполните телефон, чат и папку результатов.')
            return
        self.running = True
        self.stop.clear()
        self.start_button.config(state='disabled')
        self.mode_box.config(state='disabled')
        self.cancel_button.config(state='normal')
        self.status.set('Подключение к Telegram…')
        threading.Thread(target=self.worker, args=(values,), daemon=True).start()

    async def ask(self, prompt, secret=False):
        answer = queue.Queue()
        self.events.put(('ask', (prompt, secret, answer)))
        while not self.stop.is_set():
            try:
                value = answer.get_nowait()
                if value is None:
                    raise asyncio.CancelledError()
                return value.strip()
            except queue.Empty:
                await asyncio.sleep(.1)
        raise asyncio.CancelledError()

    def worker(self, values):
        try:
            asyncio.run(self.collect(values))
        except Exception as error:
            self.events.put(('error', f'{type(error).__name__}: {error}'))
        finally:
            self.events.put(('done', None))

    async def collect(self, values):
        from telethon import TelegramClient, errors
        data = session_directory()
        data.mkdir(parents=True, exist_ok=True)
        import hashlib
        account = hashlib.sha256(values['phone'].encode()).hexdigest()[:20]
        client = TelegramClient(str(data / account), int(values['api_id']), values['api_hash'], flood_sleep_threshold=0, receive_updates=False)
        links = {}
        count = 0
        started = False
        complete = False
        async def run():
            nonlocal count, started, complete
            await client.connect()
            if not await client.is_user_authorized():
                await client.send_code_request(values['phone'])
                for attempt in range(3):
                    try:
                        code = await self.ask('Введите код входа, полученный от Telegram:')
                        await client.sign_in(values['phone'], code=code)
                        break
                    except errors.PhoneCodeInvalidError:
                        if attempt == 2:
                            raise
                    except errors.SessionPasswordNeededError:
                        password = await self.ask('Введите пароль двухэтапной аутентификации:', True)
                        await client.sign_in(password=password)
                        break
            chat = values['chat']
            if re.fullmatch(r'-?\d+', chat):
                # Fill the entity cache for private groups the account belongs to.
                await client.get_dialogs()
                chat = int(chat)
            entity = await client.get_entity(chat)
            started = True
            began = time.monotonic()
            mode = values['mode']
            self.events.put(('status', f'{mode}: чтение сообщений…'))
            def on_wait(seconds):
                self.events.put(('status', f'Telegram запросил паузу: {seconds} сек. Уже собрано ссылок: {len(links)}. Продолжение автоматически.'))
            async for message in scan_messages(client, entity, mode, on_wait):
                links.update(dict.fromkeys(extract_links(message)))
                count += 1
                if count == 1 or count % 100 == 0:
                    elapsed = time.monotonic() - began
                    self.events.put(('status', f'{mode}. Прочитано: {count}; ссылок: {len(links)}; прошло: {elapsed:.0f} сек.'))
            complete = True
        task = asyncio.create_task(run())
        try:
            while not task.done():
                if self.stop.is_set():
                    task.cancel()
                    break
                await asyncio.sleep(.2)
            await task
        except asyncio.CancelledError:
            self.events.put(('status', 'Сбор остановлен.'))
        finally:
            try:
                await client.disconnect()
            finally:
                if started:
                    target = export_links(values['folder'], values['chat'], links, count, complete,
                                          scope=values['mode'] + '. ' + MODES[values['mode']])
                    self.events.put(('result', (target, len(links), count, complete)))

    def poll(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == 'ask':
                    prompt, secret, answer = payload
                    if self.stop.is_set():
                        answer.put(None)
                    else:
                        answer.put(LoginDialog(self, prompt, secret).result)
                elif kind == 'status':
                    self.status.set(payload)
                elif kind == 'error':
                    self.status.set('Не удалось завершить сбор. Если история уже читалась, сохранён частичный результат.')
                    messagebox.showerror('Ошибка', payload)
                elif kind == 'result':
                    self.result, size, count, complete = payload
                    self.open_button.config(state='normal')
                    self.status.set(f'{"Готово" if complete else "Частичный результат"}: {size} ссылок из {count} сообщений.\n{self.result}')
                elif kind == 'done':
                    self.running = False
                    self.start_button.config(state='normal')
                    self.mode_box.config(state='readonly')
                    self.cancel_button.config(state='disabled')
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def open_result(self):
        if self.result:
            webbrowser.open((self.result / 'links.html').as_uri())

    def close(self):
        if self.running:
            self.stop.set()
            self.status.set('Останавливаем сбор и сохраняем результат. Закройте окно после завершения.')
        else:
            self.destroy()


def paste_from_clipboard(field):
    """Insert text directly, without relying on Tk's virtual paste bindings."""
    try:
        text = field.clipboard_get()
    except tk.TclError:
        messagebox.showinfo('Вставка', 'В буфере обмена нет доступного текста. Скопируйте текст и попробуйте снова.', parent=field.winfo_toplevel())
        return
    if field.selection_present():
        start = field.index('sel.first')
        field.delete('sel.first', 'sel.last')
        field.icursor(start)
    field.insert('insert', text)
    field.focus_set()
    field.xview_moveto(1)


def add_input(parent, **options):
    field = ttk.Entry(parent, exportselection=False, **options)
    field.pack(side='left', fill='x', expand=True)
    # Widget bindings run BEFORE class bindings, which can consume Ctrl events.
    if sys.platform == 'win32':
        field.bind('<KeyPress>', windows_shortcut)
    elif sys.platform == 'darwin':
        def paste(event):
            paste_from_clipboard(field)
            return 'break'
        field.bind('<Command-v>', paste)
        field.bind('<Command-V>', paste)
    button = ttk.Button(parent, text='Вставить', takefocus=False,
                        command=lambda: paste_from_clipboard(field))
    button.pack(side='left', padx=(6, 0))
    return field, button


class LoginDialog(simpledialog.Dialog):
    def __init__(self, parent, prompt, secret=False):
        self.prompt = prompt
        self.secret = secret
        super().__init__(parent, 'Вход в Telegram')

    def body(self, master):
        ttk.Label(master, text=self.prompt, wraplength=500).pack(anchor='w', padx=10, pady=10)
        row = ttk.Frame(master, padding=10)
        row.pack(fill='x')
        self.field, self.paste_button = add_input(row, width=42, show='*' if self.secret else '')
        return self.field

    def apply(self):
        self.result = self.field.get()


def windows_shortcut(event):
    # Windows virtual-key codes remain the same under Russian/Ukrainian layouts.
    # Ignore AltGr (Ctrl+Alt), which is used to type characters on some layouts.
    if not event.state & 0x4 or event.state & 0x20000 or event.state & 0x8:
        return None
    if event.keycode == 86:
        paste_from_clipboard(event.widget)
        return 'break'
    action = {67: '<<Copy>>', 88: '<<Cut>>'}.get(event.keycode)
    if action:
        event.widget.event_generate(action)
        return 'break'
    if event.keycode == 65:
        event.widget.selection_range(0, 'end')
        event.widget.icursor('end')
        return 'break'
    return None


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        # CI can verify the packaged Tcl/Tk and exporter without an account.
        import json
        import tempfile
        application = App()
        application.withdraw()
        application.update()
        with tempfile.TemporaryDirectory() as folder:
            output = export_links(folder, 'test', ['https://example.org'], 1, True)
            assert (output / 'links.html').is_file()
        application.destroy()
        Path(sys.argv[2]).write_text(json.dumps({'status': 'ok', 'platform': sys.platform,
                                                'frozen': bool(getattr(sys, 'frozen', False))}), encoding='utf-8')
    else:
        App().mainloop()
