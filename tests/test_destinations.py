import unittest
from types import SimpleNamespace
from links import extract_links, telegram_destination


class DestinationTests(unittest.TestCase):
    def test_user_example(self):
        urls = [f'https://t.me/Pudel_ua/{i}?single' for i in (707, 682, 678, 675, 639, 524, 543)]
        urls.insert(4, 'https://t.me/adm_europe_bot')
        msg = SimpleNamespace(message=' '.join(urls), entities=[])
        self.assertEqual(extract_links(msg, group_telegram=True),
                         ['https://t.me/pudel_ua', 'https://t.me/adm_europe_bot'])
        self.assertEqual(len(extract_links(msg)), 8)

    def test_variants(self):
        for url in ['https://t.me/s/Pudel_ua/707?single', 'https://telegram.me/Pudel_ua/707#x',
                    'https://t.me/Pudel_ua/123/707?thread=1', 'https://t.me/Pudel_ua/',
                    'tg://resolve?domain=Pudel_ua&post=707']:
            self.assertEqual(telegram_destination(url), 'https://t.me/pudel_ua')

    def test_preserves_other_destinations(self):
        for url in ['https://t.me/+abc', 'https://t.me/+def', 'https://t.me/joinchat/ABC',
                    'https://t.me/c/123/456', 'https://t.me/addstickers/MyPack',
                    'https://t.me/adm_europe_bot?start=123', 'https://example.com/123?a=2',
                    'https://t.me/combot/cas?startapp=12']:
            self.assertEqual(telegram_destination(url), url)
