"""Touch UI. Shared extraction and scanning modules are copied during build."""
import asyncio
import hashlib
import json
from pathlib import Path
import queue
import re
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.utils import platform

from links import extract_links, export_links
from scanner import MODES, scan_messages


class TelegramLinksApp(App):
    def build(self):
        self.title = 'Telegram Links'
        self.folder = Path(self.user_data_dir)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.running = False
        self.result = None
        self.pending_export = None
        try:
            saved = json.loads((self.folder / 'settings.json').read_text())
            if not isinstance(saved, dict):
                saved = {}
        except (OSError, ValueError):
            saved = {}
        scroll = ScrollView()
        body = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(14), size_hint_y=None)
        body.bind(minimum_height=body.setter('height'))
        scroll.add_widget(body)
        body.add_widget(Label(text='Telegram Links • Android', size_hint_y=None, height=dp(40), font_size='22sp'))
        self.fields = {}
        for key, title, value in [('api_id', 'API ID', saved.get('api_id', '')),
                                  ('api_hash', 'API Hash', saved.get('api_hash', '')),
                                  ('phone', 'Телефон: +380…', ''),
                                  ('chat', 'Чат: @имя или ссылка', '@pl_warszawa_rabota')]:
            body.add_widget(Label(text=title, size_hint_y=None, height=dp(24)))
            row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
            field = TextInput(text=str(value), multiline=False, password=key == 'api_hash', font_size='16sp')
            paste = Button(text='Вставить', size_hint_x=.3)
            paste.bind(on_release=lambda button, field=field: field.insert_text(Clipboard.paste() or ''))
            row.add_widget(field)
            row.add_widget(paste)
            body.add_widget(row)
            self.fields[key] = field
        self.remember = self.option(body, 'Запоминать API на этом телефоне', saved.get('remember', True))
        self.exclude = self.option(body, 'Исключать Combot CAS', saved.get('exclude_cas', True))
        self.group = self.option(body, 'Одна ссылка на каждый канал', saved.get('group_telegram', True))
        self.mode = Spinner(text='Полная история', values=list(MODES), size_hint_y=None, height=dp(48))
        body.add_widget(self.mode)
        self.mode_note = Label(text=MODES[self.mode.text], size_hint_y=None, height=dp(78))
        self.mode_note.bind(size=lambda widget, size: setattr(widget, 'text_size', (size[0], None)))
        self.mode.bind(text=lambda widget, text: setattr(self.mode_note, 'text', MODES[text]))
        body.add_widget(self.mode_note)
        self.start_button = Button(text='Собрать ссылки', size_hint_y=None, height=dp(50))
        self.start_button.bind(on_release=self.start_scan)
        body.add_widget(self.start_button)
        stop = Button(text='Остановить и сохранить', size_hint_y=None, height=dp(48))
        stop.bind(on_release=lambda *_: self.stop_event.set())
        body.add_widget(stop)
        self.status = Label(text='Во время сбора оставляйте приложение открытым.', size_hint_y=None, height=dp(110))
        self.status.bind(size=lambda widget, size: setattr(widget, 'text_size', (size[0], None)))
        body.add_widget(self.status)
        for extension in ('txt', 'html'):
            button = Button(text='Сохранить ' + extension.upper() + ' в выбранную папку', size_hint_y=None, height=dp(48))
            button.bind(on_release=lambda button, ext=extension: self.export_file(ext))
            body.add_widget(button)
        if platform == 'android':
            from android import activity
            activity.bind(on_activity_result=self.activity_result)
        Clock.schedule_interval(self.poll, .2)
        return scroll

    def option(self, body, text, active):
        row = BoxLayout(size_hint_y=None, height=dp(44))
        check = CheckBox(active=bool(active), size_hint_x=None, width=dp(44))
        row.add_widget(check)
        row.add_widget(Label(text=text, font_size='14sp'))
        body.add_widget(row)
        return check

    def save_preferences(self):
        data = dict(remember=self.remember.active, exclude_cas=self.exclude.active, group_telegram=self.group.active)
        if self.remember.active:
            data.update(api_id=self.fields['api_id'].text.strip(), api_hash=self.fields['api_hash'].text.strip())
        temp = self.folder / 'settings.tmp'
        temp.write_text(json.dumps(data), encoding='utf-8')
        temp.replace(self.folder / 'settings.json')

    def start_scan(self, *_):
        if self.running:
            return
        values = {key: field.text.strip() for key, field in self.fields.items()}
        if not values['api_id'].isdigit() or int(values['api_id']) <= 0 or not re.fullmatch('[a-fA-F0-9]{32}', values['api_hash']):
            self.status.text = 'Введите числовой API ID и API Hash из 32 символов.'
            return
        if not values['phone'] or not values['chat']:
            self.status.text = 'Введите телефон и чат.'
            return
        try:
            self.save_preferences()
        except OSError:
            self.status.text = 'Не удалось сохранить настройки.'
            return
        values.update(mode=self.mode.text, exclude=self.exclude.active, group=self.group.active)
        self.running = True
        self.start_button.disabled = True
        self.stop_event.clear()
        self.status.text = 'Подключение…'
        threading.Thread(target=self.worker, args=(values,), daemon=True).start()

    def worker(self, values):
        try:
            asyncio.run(self.collect(values))
        except Exception as error:
            self.events.put(('status', f'Ошибка {type(error).__name__}: {error}'))
        finally:
            self.events.put(('done', None))

    async def ask(self, prompt, password=False):
        response = queue.Queue()
        self.events.put(('auth', (prompt, password, response)))
        while not self.stop_event.is_set():
            try:
                value = response.get_nowait()
                if value is None:
                    raise asyncio.CancelledError()
                return value if password else value.strip()
            except queue.Empty:
                await asyncio.sleep(.1)
        raise asyncio.CancelledError()

    async def collect(self, values):
        from telethon import TelegramClient, errors
        session = self.folder / hashlib.sha256(values['phone'].encode()).hexdigest()[:20]
        client = TelegramClient(str(session), int(values['api_id']), values['api_hash'],
                                flood_sleep_threshold=0, receive_updates=False)
        links, count, started, complete = {}, 0, False, False
        async def run():
            nonlocal count, started, complete
            await client.connect()
            if not await client.is_user_authorized():
                await client.send_code_request(values['phone'])
                for attempt in range(3):
                    try:
                        await client.sign_in(values['phone'], code=await self.ask('Код из Telegram'))
                        break
                    except errors.PhoneCodeInvalidError:
                        if attempt == 2:
                            raise
                    except errors.SessionPasswordNeededError:
                        await client.sign_in(password=await self.ask('Пароль двухэтапной защиты', True))
                        break
            chat = values['chat']
            if re.fullmatch(r'-?\d+', chat):
                await client.get_dialogs()
                chat = int(chat)
            entity = await client.get_entity(chat)
            started = True
            def wait(seconds):
                self.events.put(('status', f'Пауза Telegram: {seconds} сек. Найдено: {len(links)}.'))
            async for message in scan_messages(client, entity, values['mode'], wait):
                links.update(dict.fromkeys(extract_links(message, values['exclude'], values['group'])))
                count += 1
                if count == 1 or count % 100 == 0:
                    self.events.put(('status', f'Сообщений: {count}. Ссылок: {len(links)}.'))
            complete = True
        task = asyncio.create_task(run())
        try:
            while not task.done():
                if self.stop_event.is_set():
                    task.cancel()
                    break
                await asyncio.sleep(.2)
            await task
        except asyncio.CancelledError:
            self.events.put(('status', 'Остановлено.'))
        finally:
            try:
                await client.disconnect()
            finally:
                if started:
                    result = export_links(self.folder / 'exports', values['chat'], links, count, complete,
                                          scope=values['mode'] + '. ' + MODES[values['mode']] +
                                          (' Combot CAS исключён.' if values['exclude'] else '') +
                                          (' Посты объединены по каналам.' if values['group'] else ''))
                    self.events.put(('result', (result, len(links), complete)))

    def poll(self, dt):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'status':
                    self.status.text = value
                elif kind == 'done':
                    self.running = False
                    self.start_button.disabled = False
                elif kind == 'result':
                    self.result, count, complete = value
                    self.status.text = f'{"Готово" if complete else "Частичный результат"}: {count} ссылок.\nНажмите «Сохранить TXT» или «Сохранить HTML».'
                elif kind == 'auth':
                    if self.stop_event.is_set():
                        value[2].put(None)
                    else:
                        self.auth_popup(*value)
        except queue.Empty:
            pass

    def auth_popup(self, prompt, password, response):
        body = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(10))
        field = TextInput(multiline=False, password=password, size_hint_y=None, height=dp(52))
        body.add_widget(field)
        paste = Button(text='Вставить')
        paste.bind(on_release=lambda *_: field.insert_text(Clipboard.paste() or ''))
        body.add_widget(paste)
        ok = Button(text='Продолжить')
        body.add_widget(ok)
        popup = Popup(title=prompt, content=body, size_hint=(.95, None), height=dp(270))
        answered = [False]
        def submit(*_):
            answered[0] = True
            response.put(field.text)
            popup.dismiss()
        ok.bind(on_release=submit)
        popup.bind(on_dismiss=lambda *_: None if answered[0] else response.put(None))
        popup.open()

    def export_file(self, extension):
        if self.result is None:
            self.status.text = 'Сначала соберите ссылки.'
            return
        if self.pending_export is not None:
            return
        if platform != 'android':
            self.status.text = str(self.result / ('links.' + extension))
            return
        self.pending_export = self.result / ('links.' + extension)
        from android.runnable import run_on_ui_thread
        from jnius import autoclass
        @run_on_ui_thread
        def choose():
            Intent = autoclass('android.content.Intent')
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType('text/html' if extension == 'html' else 'text/plain')
            intent.putExtra(Intent.EXTRA_TITLE, 'TelegramLinks.' + extension)
            activity.startActivityForResult(intent, 407)
        choose()

    def activity_result(self, request, result, intent):
        if request != 407:
            return
        source, self.pending_export = self.pending_export, None
        if result != -1 or source is None or intent is None:
            return
        try:
            from jnius import autoclass
            activity = autoclass('org.kivy.android.PythonActivity').mActivity
            stream = activity.getContentResolver().openOutputStream(intent.getData())
            if stream is None:
                raise OSError('Не удалось открыть файл')
            try:
                stream.write(source.read_bytes())
            finally:
                stream.close()
            self.events.put(('status', 'Файл сохранён в выбранную папку. HTML можно открыть браузером.'))
        except Exception:
            self.events.put(('status', 'Не удалось сохранить файл. Выберите другую папку.'))

    def on_pause(self):
        self.save_preferences()
        return True

    def on_stop(self):
        self.stop_event.set()
        self.save_preferences()


TelegramLinksApp().run()
