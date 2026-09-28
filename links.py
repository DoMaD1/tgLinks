"""Extract Telegram links and create safe, clickable documents."""
import html
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qs, unquote

URL_RE = re.compile(r"(?:https?://|tg://|www\.|t\.me/|telegram\.me/)[^\s<>\"']+", re.I)


def normalize(value):
    value = value.strip()
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        return None
    if '://' not in value:
        value = 'https://' + value
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in ('http', 'https', 'tg') or not parts.hostname:
            return None
        # Preserve paths, queries and fragments: they may identify different pages.
        host = parts.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        if parts.port is not None:
            host += ':' + str(parts.port)
        if parts.username is not None:
            host = parts.netloc.rsplit('@', 1)[0] + '@' + host
        return urlunsplit((parts.scheme.lower(), host, parts.path, parts.query, parts.fragment))
    except ValueError:
        return None


def is_combot_cas(link):
    parts = urlsplit(link)
    if parts.scheme == 'tg' and parts.hostname == 'resolve':
        query = parse_qs(parts.query)
        return (query.get('domain', [''])[0].lower() == 'combot'
                and query.get('appname', [''])[0].lower() == 'cas')
    return (parts.hostname in ('t.me', 'www.t.me', 'telegram.me', 'www.telegram.me')
            and unquote(parts.path).rstrip('/').lower() == '/combot/cas')


def extract_links(message, exclude_cas=False):
    text = message.message or ''
    encoded = text.encode('utf-16-le')
    candidates = []
    covered = []
    for entity in message.entities or []:
        kind = type(entity).__name__
        if kind in ('MessageEntityUrl', 'MessageEntityTextUrl'):
            start, end = entity.offset * 2, (entity.offset + entity.length) * 2
            candidates.append(entity.url if kind == 'MessageEntityTextUrl' else encoded[start:end].decode('utf-16-le'))
            covered.append((entity.offset, entity.offset + entity.length))
    for match in URL_RE.finditer(text):
        offset = len(text[:match.start()].encode('utf-16-le')) // 2
        if any(start <= offset < end for start, end in covered):
            continue
        value = match.group().rstrip('.,;:!?…')
        for left, right in [('(', ')'), ('[', ']'), ('{', '}')]:
            while value.endswith(right) and value.count(right) > value.count(left):
                value = value[:-1]
        candidates.append(value)
    markup = getattr(message, 'reply_markup', None)
    for row in getattr(markup, 'rows', []):
        for button in row.buttons:
            if getattr(button, 'url', None):
                candidates.append(button.url)
    return list(dict.fromkeys(link for value in candidates if (link := normalize(value))
                              and not (exclude_cas and is_combot_cas(link))))


def export_links(folder, chat, links, count, complete, scope='Полная история'):
    """Use an exclusive per-run directory so prior exports cannot be overwritten."""
    from datetime import datetime
    import tempfile
    folder = Path(folder).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[^\w-]+', '_', chat).strip('_')[:60] or 'chat'
    target = Path(tempfile.mkdtemp(prefix=f'{safe_name}_{datetime.now():%Y%m%d_%H%M%S}_', dir=folder))
    unique = list(dict.fromkeys(links))
    (target / 'links.txt').write_text(''.join(link + '\n' for link in unique), encoding='utf-8-sig')
    status = 'Завершено' if complete else 'Частичный результат — сбор прерван'
    (target / 'info.txt').write_text(f'{chat}\n{scope}\n{status}\nСообщений: {count}. Ссылок: {len(unique)}.\n', encoding='utf-8-sig')
    rows = '\n'.join(f'<li><a href="{html.escape(link, quote=True)}" rel="noreferrer">{html.escape(link)}</a></li>' for link in unique)
    document = f'''<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ссылки — {html.escape(chat)}</title>
<style>body{{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 24px;background:#f6f8fc;color:#15233b}}li{{margin:12px 0;overflow-wrap:anywhere}}a{{color:#1264bd}}</style>
<h1>Ссылки из {html.escape(chat)}</h1><p>{status}. Сообщений: {count}. Уникальных ссылок: {len(unique)}.</p>
<p>Режим: {html.escape(scope)}</p>
<ol>{rows}</ol></html>'''
    (target / 'links.html').write_text(document, encoding='utf-8')
    return target
