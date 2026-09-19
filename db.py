import os
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row

SCHEMA="""
CREATE TABLE IF NOT EXISTS users (telegram_id BIGINT PRIMARY KEY, role TEXT NOT NULL CHECK(role IN ('admin','cashier')));
CREATE TABLE IF NOT EXISTS processed_updates (update_id BIGINT PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS drafts (id BIGSERIAL PRIMARY KEY, telegram_id BIGINT NOT NULL REFERENCES users(telegram_id), raw_text TEXT NOT NULL, operations JSONB NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','confirmed','cancelled')), created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS ledger (id BIGSERIAL PRIMARY KEY, draft_id BIGINT UNIQUE REFERENCES drafts(id), telegram_id BIGINT NOT NULL REFERENCES users(telegram_id), kind TEXT NOT NULL CHECK(kind IN ('income','expense')), currency TEXT NOT NULL CHECK(currency IN ('USD','UZS')), category TEXT NOT NULL, amount NUMERIC(18,2) NOT NULL CHECK(amount>0), party TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ledger_created_idx ON ledger(created_at);
CREATE TABLE IF NOT EXISTS adjustments (id BIGSERIAL PRIMARY KEY, ledger_id BIGINT NOT NULL REFERENCES ledger(id), admin_id BIGINT NOT NULL REFERENCES users(telegram_id), reason TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
"""

@contextmanager
def connect():
    with psycopg.connect(os.environ['DATABASE_URL'],row_factory=dict_row) as conn:
        yield conn

def init(admin_id):
    with connect() as con:
        con.execute(SCHEMA)
        con.execute("INSERT INTO users(telegram_id,role) VALUES (%s,'admin') ON CONFLICT (telegram_id) DO UPDATE SET role='admin'",(admin_id,))

def role(telegram_id):
    with connect() as con:
        r=con.execute('SELECT role FROM users WHERE telegram_id=%s',(telegram_id,)).fetchone()
        return r['role'] if r else None

def allow(admin_id, cash_id):
    with connect() as con:
        if not con.execute("SELECT 1 FROM users WHERE telegram_id=%s AND role='admin'",(admin_id,)).fetchone(): raise PermissionError()
        con.execute("INSERT INTO users VALUES (%s,'cashier') ON CONFLICT (telegram_id) DO NOTHING",(cash_id,))

def save_draft(user_id,text,op):
    from json import dumps
    with connect() as con:
        row=con.execute('INSERT INTO drafts(telegram_id,raw_text,operations) VALUES(%s,%s,%s::jsonb) RETURNING id',(user_id,text,dumps({**op,'amount':str(op['amount'])},ensure_ascii=False))).fetchone()
        return row['id']

def confirm(user_id,draft_id):
    from engine import validate_operation
    with connect() as con:
        draft=con.execute('SELECT * FROM drafts WHERE id=%s AND telegram_id=%s FOR UPDATE',(draft_id,user_id)).fetchone()
        if not draft: return 'Топилмади ёки рухсат йўқ.'
        if draft['status']!='pending': return 'Бу операция аввал қайта ишланган.'
        op=validate_operation(draft['operations'])
        con.execute('INSERT INTO ledger(draft_id,telegram_id,kind,currency,category,amount,party,note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',(draft_id,user_id,op['kind'],op['currency'],op['category'],op['amount'],op['party'],op['note']))
        con.execute("UPDATE drafts SET status='confirmed' WHERE id=%s",(draft_id,))
        return '✅ Операция кассага сақланди.'

def cancel(user_id,draft_id):
    with connect() as con:
        n=con.execute("UPDATE drafts SET status='cancelled' WHERE id=%s AND telegram_id=%s AND status='pending'",(draft_id,user_id)).rowcount
        return '❎ Бекор қилинди.' if n else 'Аввал қайта ишланган ёки топилмади.'

def balances():
    with connect() as con:
        return con.execute("SELECT currency,SUM(CASE WHEN kind='income' THEN amount ELSE -amount END) AS balance FROM ledger GROUP BY currency ORDER BY currency").fetchall()

def report(period='today'):
    where="created_at >= (now() AT TIME ZONE 'Asia/Tashkent')::date AT TIME ZONE 'Asia/Tashkent'" if period=='today' else "created_at >= date_trunc('month',now() AT TIME ZONE 'Asia/Tashkent') AT TIME ZONE 'Asia/Tashkent'"
    with connect() as con:
        return con.execute(f'SELECT currency,kind,category,COUNT(*) AS entries,SUM(amount) AS total FROM ledger WHERE {where} GROUP BY currency,kind,category ORDER BY currency,kind,category').fetchall()

def claim_update(update_id):
    with connect() as con:
        return bool(con.execute('INSERT INTO processed_updates(update_id) VALUES(%s) ON CONFLICT DO NOTHING RETURNING update_id',(update_id,)).fetchone())

def release_update(update_id):
    with connect() as con:
        con.execute('DELETE FROM processed_updates WHERE update_id=%s',(update_id,))
