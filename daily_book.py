"""Small daily cash book: chronological income/expense entries, no analytics."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo('Asia/Tashkent')

def amount_text(value, currency):
    number = format(Decimal(str(value)), 'f')
    if '.' in number:
        number = number.rstrip('0').rstrip('.')
    whole, dot, fraction = number.partition('.')
    grouped = '{:,}'.format(int(whole)).replace(',', ' ')
    return grouped + ('.' + fraction if dot else '') + ' ' + currency

def daily_report(entries, now=None, max_lines=45):
    now = now or datetime.now(LOCAL_TZ)
    entries = list(entries)
    title = '📒 Кунлик касса дафтари — ' + now.strftime('%d.%m.%Y')
    if not entries:
        return title + '\n\nБугун ҳали кирим-чиқим қайд этилмаган.'
    totals = defaultdict(lambda: Decimal('0'))
    count = defaultdict(int)
    groups = {'income': [], 'expense': []}
    for entry in entries:
        kind, currency = entry['kind'], entry['currency']
        if kind not in groups or currency not in ('USD', 'UZS'):
            continue
        amount = Decimal(str(entry['amount']))
        if amount <= 0:
            continue
        totals[(kind, currency)] += amount
        count[(kind, currency)] += 1
        timestamp = str(entry['created_at'])
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            if dt.tzinfo is None:  # SQLite production-independent local test stamps
                dt = dt.replace(tzinfo=LOCAL_TZ)
            stamp = dt.astimezone(LOCAL_TZ).strftime('%H:%M')
        except (ValueError, TypeError):
            stamp = '--:--'
        details = str(entry['party'] or entry['note'] or entry['category'] or 'Изоҳсиз').replace('\n', ' ').strip()
        if len(details) > 62:
            details = details[:59] + '…'
        sign = '+' if kind == 'income' else '−'
        groups[kind].append(f"{stamp}  {sign}{amount_text(amount, currency)} — {details}")
    lines = [title]
    for kind, header in (('income', '🟢 КИРИМ'), ('expense', '🔴 ЧИҚИМ')):
        lines.extend(['', header])
        items = groups[kind]
        lines.extend(items[:max_lines] if items else ['Йўқ'])
        if len(items) > max_lines:
            lines.append(f'… яна {len(items) - max_lines} та операция (жами ҳисобга олинган).')
        for currency in ('USD', 'UZS'):
            if count[(kind, currency)]:
                lines.append(f"Жами {kind == 'income' and 'кирим' or 'чиқим'}: {amount_text(totals[(kind, currency)], currency)} ({count[(kind, currency)]} та)")
    return '\n'.join(lines)[:3900]
