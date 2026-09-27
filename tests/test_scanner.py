import asyncio
import unittest
from types import SimpleNamespace
from telethon import errors
from telethon.tl.types import InputMessagesFilterUrl
from scanner import scan_messages


class FakeClient:
    def __init__(self, total, flood=False):
        self.total, self.flood, self.calls = total, flood, []

    async def iter_messages(self, entity, **options):
        self.calls.append(options)
        start = options['offset_id'] - 1 if options['offset_id'] else self.total
        limit = options['limit'] if options['limit'] is not None else start
        for index, ident in enumerate(range(start, max(0, start-limit), -1)):
            if self.flood and index == 2:
                self.flood = False
                raise errors.FloodWaitError(request=None, capture=3)
            yield SimpleNamespace(id=ident)


class ScannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_after_flood(self):
        client = FakeClient(12, flood=True)
        waits, sleeps = [], []
        async def sleep(seconds):
            sleeps.append(seconds)
        result = [m.id async for m in scan_messages(client, None, 'Полная история', waits.append, sleep)]
        self.assertEqual(result, list(range(12, 0, -1)))
        self.assertEqual(waits, [3])
        self.assertEqual(sleeps, [4])
        self.assertGreater(client.calls[1]['wait_time'], client.calls[0]['wait_time'])

    async def test_recent_limit_survives_retry(self):
        client = FakeClient(6000, flood=True)
        async def sleep(seconds):
            pass
        result = [m.id async for m in scan_messages(client, None, 'Последние 5000 сообщений', lambda _: None, sleep)]
        self.assertEqual(result, list(range(6000, 1000, -1)))
        self.assertEqual(client.calls[1]['limit'], 4998)

    async def test_filter_only_in_fast_mode(self):
        for mode in ('Полная история', 'Быстро: ссылки Telegram'):
            client = FakeClient(4)
            result = [m.id async for m in scan_messages(client, None, mode, lambda _: None)]
            self.assertEqual(len(result), 4)
            if mode.startswith('Быстро'):
                self.assertIsInstance(client.calls[0]['filter'], InputMessagesFilterUrl)
            else:
                self.assertNotIn('filter', client.calls[0])

    async def test_cancel_server_wait(self):
        client = FakeClient(5, flood=True)
        waiting = asyncio.Event()
        async def sleep(seconds):
            waiting.set()
            await asyncio.Future()
        async def collect():
            return [m.id async for m in scan_messages(client, None, 'Полная история', lambda _: None, sleep)]
        task = asyncio.create_task(collect())
        await asyncio.wait_for(waiting.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
