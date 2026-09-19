import os, sqlite3, json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

PATH=os.getenv('SQLITE_PATH','/tmp/ai_kassir_test.sqlite3')

@contextmanager
def connect():
    con=sqlite3.connect(PATH)
    con.row_factory=sqlite3.Row
    try:
        yield con
        con.commit()
    finally: con.close()

def init(admin_ids):
    admin_ids = tuple(dict.fromkeys(int(i) for i in admin_ids))
    if not admin_ids or any(i <= 0 for i in admin_ids):
        raise ValueError('At least one valid admin ID is required')
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(telegram_id INTEGER PRIMARY KEY,role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS processed_updates(update_id INTEGER PRIMARY KEY,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS drafts(id INTEGER PRIMARY KEY AUTOINCREMENT,telegram_id INTEGER NOT NULL,raw_text TEXT NOT NULL,operations TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,draft_id INTEGER UNIQUE,telegram_id INTEGER NOT NULL,kind TEXT NOT NULL,currency TEXT NOT NULL,category TEXT NOT NULL,amount TEXT NOT NULL,party TEXT DEFAULT '',note TEXT NOT NULL DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        placeholders = ','.join('?' for _ in admin_ids)
        con.execute(f"DELETE FROM users WHERE role='admin' AND telegram_id NOT IN ({placeholders})", admin_ids)
        for admin_id in admin_ids:
            con.execute("INSERT INTO users(telegram_id,role) VALUES (?,'admin') ON CONFLICT(telegram_id) DO UPDATE SET role='admin'",(admin_id,))

def role(uid):
    with connect() as con:
        r=con.execute('SELECT role FROM users WHERE telegram_id=?',(uid,)).fetchone()
        return r['role'] if r else None

def allow(admin_id,cash_id):
    if role(admin_id)!='admin': raise PermissionError()
    with connect() as con: con.execute("INSERT OR IGNORE INTO users VALUES(?,'cashier')",(cash_id,))

def save_draft(uid,text,op):
    data={**op,'amount':str(op['amount'])}
    with connect() as con:
        cur=con.execute('INSERT INTO drafts(telegram_id,raw_text,operations) VALUES(?,?,?)',(uid,text,json.dumps(data,ensure_ascii=False)))
        return cur.lastrowid

def confirm(uid,draft_id):
    from engine import validate_operation
    with connect() as con:
        d=con.execute('SELECT * FROM drafts WHERE id=? AND telegram_id=?',(draft_id,uid)).fetchone()
        if not d:return 'Топилмади ёки рухсат йўқ.'
        if d['status']!='pending':return 'Бу операция аввал қайта ишланган.'
        op=validate_operation(json.loads(d['operations']))
        con.execute('INSERT INTO ledger(draft_id,telegram_id,kind,currency,category,amount,party,note) VALUES(?,?,?,?,?,?,?,?)',(draft_id,uid,op['kind'],op['currency'],op['category'],str(op['amount']),op['party'],op['note']))
        con.execute("UPDATE drafts SET status='confirmed' WHERE id=?",(draft_id,))
        return '✅ Операция кассага сақланди.'

def cancel(uid,draft_id):
    with connect() as con:
        n=con.execute("UPDATE drafts SET status='cancelled' WHERE id=? AND telegram_id=? AND status='pending'",(draft_id,uid)).rowcount
        return '❎ Бекор қилинди.' if n else 'Аввал қайта ишланган ёки топилмади.'

def balances():
    with connect() as con:
        rows=con.execute("SELECT currency,kind,amount FROM ledger").fetchall()
    out={}
    from decimal import Decimal
    for r in rows: out[r['currency']]=out.get(r['currency'],Decimal('0'))+(Decimal(r['amount']) if r['kind']=='income' else -Decimal(r['amount']))
    return [{'currency':k,'balance':v} for k,v in sorted(out.items())]

def report(period='today'):
    tz=timezone(timedelta(hours=5)); now=datetime.now(tz)
    start=(now.replace(hour=0,minute=0,second=0,microsecond=0) if period=='today' else now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    with connect() as con: rows=con.execute("SELECT currency,kind,category,amount FROM ledger WHERE created_at>=?",(start,)).fetchall()
    from decimal import Decimal
    agg={}
    for r in rows:
        key=(r['currency'],r['kind'],r['category']); total,count=agg.get(key,(Decimal('0'),0));agg[key]=(total+Decimal(r['amount']),count+1)
    return [{'currency':k[0],'kind':k[1],'category':k[2],'total':v[0],'entries':v[1]} for k,v in sorted(agg.items())]
