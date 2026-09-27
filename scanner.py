"""History scanning with bounded modes and resumable Telegram rate limits."""
import asyncio
from telethon import errors
from telethon.tl.types import InputMessagesFilterUrl

MODES = {
    'Полная история': 'Все доступные сообщения, включая ссылки в кнопках.',
    'Быстро: ссылки Telegram': 'Только сообщения из поиска ссылок Telegram. Возможны пропуски ссылок в кнопках и нераспознанных адресов.',
    'Последние 5000 сообщений': 'Только последние 5000 доступных сообщений. Более старая история не проверяется.',
}


async def scan_messages(client, entity, mode, on_wait, sleep=asyncio.sleep):
    limit = 5000 if mode == 'Последние 5000 сообщений' else None
    options = {'filter': InputMessagesFilterUrl()} if mode == 'Быстро: ссылки Telegram' else {}
    count, offset, wait_time = 0, 0, 0.5
    while limit is None or count < limit:
        try:
            async for message in client.iter_messages(
                entity, limit=None if limit is None else limit - count,
                offset_id=offset, wait_time=wait_time, **options,
            ):
                offset = message.id
                count += 1
                yield message
            return
        except errors.FloodWaitError as error:
            # Honor server limits, resume after the last delivered message,
            # and reduce the request rate for the rest of this scan.
            wait_time = min(5.0, max(1.0, wait_time * 2))
            on_wait(error.seconds)
            await sleep(error.seconds + 1)
