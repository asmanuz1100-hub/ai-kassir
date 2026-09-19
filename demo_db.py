"""Disposable local SQLite ledger for demos only. Render free filesystem is ephemeral."""
import os, sqlite3, json
from decimal import Decimal
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo
from engine import validate_operation

PATH=os.getenv('TEST_DB_PATH','/tmp/ai_kassir_demo.sqlite3')

@contextmanager
def connect():
    conn=sqlite3.connect(PATH,timeout=20,isolation_level=None)
    conn.row_factory=sqlite3.Row
    try:
        conn.execute('PRAGMA busy_timeout=20000')
        yield conn
    finally:
        conn.close()

def init(admin_id):
    Path(PATH).parent.mkdir(parents=True,exist_ok=True)
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, role TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS processed_updates (update_id INTEGER PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY AUTOINCREMENT,telegram_id INTEGER NOT NULL,raw_text TEXT,operations TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS ledger (id INTEGER PRIMARY KEY AUTOINCREMENT,draft_id INTEGER NOT NULL UNIQUE,telegram_id INTEGER NOT NULL,kind TEXT,currency TEXT,category TEXT,amount TEXT,party TEXT,note TEXT,created_at TEXT NOT NULL);
        """)
        # Keep only the configured administrator; previous misconfigured admin IDs are revoked.
        c.execute("DELETE FROM users WHERE role='admin' AND telegram_id<>?",(admin_id,))
        c.execute("INSERT INTO users(telegram_id,role) VALUES (?,'admin') ON CONFLICT(telegram_id) DO UPDATE SET role='admin'",(admin_id,))

def role(uid):
    with connect() as c:
        row=c.execute('SELECT role FROM users WHERE telegram_id=?',(uid,)).fetchone()
        return row['role'] if row else None

def allow(admin_id,cash_id):
    with connect() as c:
        if role(admin_id)!='admin': raise PermissionError()
        c.execute("INSERT OR IGNORE INTO users(telegram_id,role) VALUES (?,'cashier')",(cash_id,))

def save_draft(uid,text,op):
    payload=json.dumps({**op,'amount':str(op['amount'])},ensure_ascii=False)
    with connect() as c:
        row=c.execute('INSERT INTO drafts(telegram_id,raw_text,operations) VALUES(?,?,?)',(uid,text,payload))
        return row.lastrowid

def confirm(uid,draft_id):
    with connect() as c:
        try:
            c.execute('BEGIN IMMEDIATE')
            draft=c.execute('SELECT * FROM drafts WHERE id=? AND telegram_id=?',(draft_id,uid)).fetchone()
            if not draft:
                c.execute('ROLLBACK');return 'Топилмади ёки рухсат йўқ.'
            if draft['status']!='pending':
                c.execute('ROLLBACK');return 'Бу операция аввал қайта ишланган.'
            op=validate_operation(json.loads(draft['operations']))
            c.execute('INSERT INTO ledger(draft_id,telegram_id,kind,currency,category,amount,party,note,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                      (draft_id,uid,op['kind'],op['currency'],op['category'],str(op['amount']),op['party'],op['note'],datetime.now(ZoneInfo('Asia/Tashkent')).isoformat()))
            c.execute("UPDATE drafts SET status='confirmed' WHERE id=?",(draft_id,))
            c.execute('COMMIT')
            return '✅ ТЕСТ операцияси сақланди (вақтинчалик).'
        except BaseException:
            c.execute('ROLLBACK')
            raise

def cancel(uid,draft_id):
    with connect() as c:
        n=c.execute("UPDATE drafts SET status='cancelled' WHERE id=? AND telegram_id=? AND status='pending'",(draft_id,uid)).rowcount
        return '❎ Бекор қилинди.' if n else 'Аввал қайта ишланган ёки топилмади.'

def claim_update(update_id):
    with connect() as c:
        return bool(c.execute('INSERT OR IGNORE INTO processed_updates(update_id) VALUES (?)',(update_id,)).rowcount)

def release_update(update_id):
    with connect() as c:
        c.execute('DELETE FROM processed_updates WHERE update_id=?',(update_id,))

def balances():
    with connect() as c:
        rows=c.execute('SELECT currency,kind,amount FROM ledger').fetchall()
    totals={}
    for r in rows:
        totals[r['currency']]=totals.get(r['currency'],Decimal(0))+(Decimal(r['amount']) if r['kind']=='income' else -Decimal(r['amount']))
    return [{'currency':currency,'balance':amount} for currency,amount in sorted(totals.items())]

def report(period='today'):
    now=datetime.now(ZoneInfo('Asia/Tashkent'))
    with connect() as c: rows=c.execute('SELECT currency,kind,category,amount,created_at FROM ledger').fetchall()
    results={}
    for r in rows:
        dt=datetime.fromisoformat(r['created_at'])
        if (period=='today' and dt.date()!=now.date()) or (period=='month' and (dt.year,dt.month)!=(now.year,now.month)): continue
        key=r['currency'],r['kind'],r['category']
        if key not in results: results[key]=[Decimal(0),0]
        results[key][0]+=Decimal(r['amount']); results[key][1]+=1
    return [{'currency':k[0],'kind':k[1],'category':k[2],'total':v[0],'entries':v[1]} for k,v in sorted(results.items())]
