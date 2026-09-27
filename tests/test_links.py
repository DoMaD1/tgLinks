import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from links import extract_links, export_links, normalize


def entity(kind, **kwargs):
    return type(kind, (), kwargs)()


class LinkTests(unittest.TestCase):
    def test_entities_unicode_and_buttons(self):
        text = '😀 example.com/a ссылка'
        msg = NS(message=text, entities=[
            entity('MessageEntityUrl', offset=3, length=13),
            entity('MessageEntityTextUrl', offset=17, length=6, url='https://hidden.test/?a=1&b=2'),
        ], reply_markup=NS(rows=[NS(buttons=[NS(url='https://example.com/a')])]))
        self.assertEqual(extract_links(msg), ['https://example.com/a', 'https://hidden.test/?a=1&b=2'])

    def test_plain_links(self):
        msg = NS(message='(https://example.com/a_(b)). www.example.org, t.me/test https://EXAMPLE.com/a_(b)', entities=[])
        self.assertEqual(extract_links(msg), ['https://example.com/a_(b)', 'https://www.example.org', 'https://t.me/test'])

    def test_schemes(self):
        self.assertIsNone(normalize('javascript:alert(1)'))
        self.assertIsNone(normalize('file:///etc/passwd'))
        self.assertEqual(normalize('tg://resolve?domain=test'), 'tg://resolve?domain=test')
        self.assertNotEqual(normalize('https://a.test/A'), normalize('https://a.test/a'))

    def test_export_escape_dedupe_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            links = ['https://example.com/?a=1&b="x"'] * 2
            result = export_links(folder, '<chat>', links, 20, False)
            second = export_links(folder, '<chat>', [], 0, True)
            self.assertNotEqual(result, second)
            self.assertEqual((result / 'links.txt').read_text(encoding='utf-8-sig').splitlines(), links[:1])
            content = (result / 'links.html').read_text(encoding='utf-8')
            self.assertIn('&lt;chat&gt;', content)
            self.assertIn('&amp;b=&quot;x&quot;', content)
            self.assertIn('Частичный результат', content)
            self.assertEqual(content.count('<li>'), 1)


if __name__ == '__main__':
    unittest.main()
