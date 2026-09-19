"""Telegram webhook cashier MVP. Set webhook to PUBLIC_URL/webhook/<secret>."""
import io, json, logging, os, re
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, Request
from openai import AsyncOpenAI
import db as postgres_db
import demo_db
from engine import validate_operation, simple_parse, CATEGORIES

logging.basicConfig(level=logging.INFO)
# Telegram bot credentials must never appear in HTTP request logs.
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
TOKEN=os.getenv('BOT_TOKEN','')
SECRET=os.getenv('WEBHOOK_SECRET','')
def configured_admin_ids():
    raw = os.getenv('ADMIN_TELEGRAM_IDS', '').strip() or os.getenv('ADMIN_TELEGRAM_ID', '').strip()
    if not raw:
        return ()
    try:
        ids = tuple(dict.fromkeys(int(part.strip()) for part in raw.split(',')))
    except ValueError:
        logging.error('Invalid administrator ID configuration')
        return ()
    if any(value <= 0 for value in ids):
        logging.error('Administrator IDs must be positive integers')
        return ()
    return ids

ADMIN_IDS=configured_admin_ids()
AI_KEY=os.getenv('OPENAI_API_KEY','')
GROQ_KEY=os.getenv('GROQ_API_KEY','')
client=AsyncOpenAI(api_key=AI_KEY) if AI_KEY else None
groq_client=AsyncOpenAI(api_key=GROQ_KEY,base_url='https://api.groq.com/openai/v1',timeout=45.0,max_retries=1) if GROQ_KEY else None
BASE=f'https://api.telegram.org/bot{TOKEN}'
TEST_MODE=os.getenv('TEST_MODE','0')=='1'
db=demo_db if TEST_MODE else postgres_db

@asynccontextmanager
async def lifespan(app):
    # The free disposable test DB is strictly isolated from all other bots.
    # Production requires a separate durable DATABASE_URL and TEST_MODE=0.
    app.state.test_mode=TEST_MODE
    app.state.ready=bool(TOKEN and SECRET and ADMIN_IDS and (TEST_MODE or os.getenv('DATABASE_URL')))
    if app.state.ready:
        db.init(ADMIN_IDS)
        base_url=os.getenv('APP_BASE_URL','').rstrip('/')
        if base_url:
            try:
                async with httpx.AsyncClient(timeout=15) as http:
                    response=await http.post(BASE+'/setWebhook',json={
                        'url':base_url+'/webhook/'+SECRET,
                        'allowed_updates':['message','callback_query'],
                        'drop_pending_updates':False
                    })
                    response.raise_for_status()
                    if not response.json().get('ok'):
                        logging.error('Telegram webhook registration rejected')
                    else: logging.info('Telegram webhook registered')
            except Exception:
                logging.exception('Unable to register webhook')
    else:
        logging.warning('AI Kassir setup incomplete')
    yield

app=FastAPI(lifespan=lifespan)

async def tg(method,body):
    async with httpx.AsyncClient(timeout=30) as h:
        r=await h.post(f'{BASE}/{method}',json=body)
        r.raise_for_status()
        result=r.json()
        if not result.get('ok'): logging.error('Telegram %s failed: %s',method,result.get('description'))
        return result

async def send(chat_id,text,markup=None):
    if TEST_MODE: text='🧪 ТЕСТ РЕЖИМИ: ёзувлар вақтинчалик, ҳақиқий касса учун эмас.\n'+text
    body={'chat_id':chat_id,'text':text}
    if markup: body['reply_markup']=markup
    await tg('sendMessage',body)

async def transcribe(file_id):
    speech_client = groq_client or client
    if speech_client is None:
        raise ValueError('Овоз учун GROQ_API_KEY ни Render Environment га киритинг.')
    info=await tg('getFile',{'file_id':file_id})
    if not info.get('ok'): raise ValueError('Овоз файлини олиб бўлмади.')
    async with httpx.AsyncClient(timeout=60) as h:
        r=await h.get(f"https://api.telegram.org/file/bot{TOKEN}/{info['result']['file_path']}")
        r.raise_for_status()
        if not r.content or len(r.content)>15_000_000:
            raise ValueError('Овоз файли бўш ёки жуда катта.')
        audio=io.BytesIO(r.content)
        audio.name='telegram_voice.ogg'
    try:
        if groq_client:
            result=await groq_client.audio.transcriptions.create(
                model=os.getenv('GROQ_TRANSCRIBE_MODEL','whisper-large-v3'),
                file=audio,
                response_format='json',
                prompt='Ўзбекча ва русча касса: сўм, доллар, кирим, чиқим, иш ҳақи, Наманган, Фурқат.'
            )
        else:
            result=await client.audio.transcriptions.create(
                model=os.getenv('TRANSCRIBE_MODEL','whisper-1'),
                file=audio,
                prompt='Ўзбекча ва русча кирим, чиқим, сўм, доллар, маош, Наманган.'
            )
    except Exception:
        logging.warning('Speech recognition failed: verify provider configuration and quota')
        raise ValueError('Овозни таниб бўлмади. Groq калити ва лимитини текширинг ёки матн ёзинг.')
    recognized=(result.text or '').strip()
    if not recognized:
        raise ValueError('Овоз тушунарсиз. Қайта айтиб кўринг ёки матн ёзинг.')
    return recognized

async def interpret(text):
    if not client: return simple_parse(text)
    schema={'type':'object','properties':{'kind':{'type':'string','enum':['income','expense']},'currency':{'type':'string','enum':['USD','UZS']},'category':{'type':'string','enum':sorted(CATEGORIES)},'amount':{'type':'string'},'party':{'type':'string'},'note':{'type':'string'}},'required':['kind','currency','category','amount','party','note'],'additionalProperties':False}
    response=await client.chat.completions.create(model=os.getenv('AI_MODEL','gpt-4o-mini'),messages=[{'role':'system','content':'Extract exactly ONE actual cash transaction from Uzbek/Russian. Never infer a missing amount or currency. If there are multiple transactions or unclear details, refuse. Numeric amount should be decimal digits in smallest currency unit (million=1000000, thousand=1000); no separators. Expense and income are from the cashier cashbox perspective. A debt repayment is income/debt_repayment; wage advance is expense/salary_advance. Never mark a bank-to-bank noncash transfer as cash.'},{'role':'user','content':text}],response_format={'type':'json_schema','json_schema':{'name':'cash_operation','strict':True,'schema':schema}})
    if response.choices[0].finish_reason!='stop' or not response.choices[0].message.content:
        raise ValueError('Маълумот аниқ эмас.')
    return validate_operation(json.loads(response.choices[0].message.content))

def format_op(op):
    sign='🟢 Кирим' if op['kind']=='income' else '🔴 Чиқим'
    return f"{sign}\n{op['amount']} {op['currency']}\nКатегория: {op['category']}\nҲамкор: {op['party'] or '—'}\nИзоҳ: {op['note'] or '—'}"

async def process(update):
    msg=update.get('message') or {}
    cb=update.get('callback_query')
    user=(cb or msg).get('from') or {}
    uid=user.get('id')
    chat=(msg.get('chat') or (cb or {}).get('message',{}).get('chat') or {}).get('id')
    if not uid or not chat: return
    # No group-chat financial operations. This also prevents a cashier leaking data to groups.
    if chat != uid:
        await send(chat,'Касса амалиётлари учун ботга шахсий чатдан ёзинг.')
        return
    user_role=db.role(uid)
    if not user_role:
        await send(chat,f'Рухсат йўқ. Telegram ID: {uid}. Админга юборинг.')
        return
    if cb:
        payload=cb.get('data','')
        m=re.fullmatch(r'(confirm|cancel):(\d+)',payload)
        if not m: return
        result=db.confirm(uid,int(m.group(2))) if m.group(1)=='confirm' else db.cancel(uid,int(m.group(2)))
        await tg('answerCallbackQuery',{'callback_query_id':cb['id'],'text':result[:180]})
        await send(chat,result)
        return
    text=(msg.get('text') or '').strip()
    if text in ('/start','/help'):
        await send(chat,'AI Кассир 💰\nОвозли ёки матнли кирим/чиқим юборинг.\n/balance — касса ҳаракати (бошланғич қолдиқсиз)\n/today — кунлик ҳисобот\n/month — ойлик ҳисобот\n/id — Telegram ID\nАдмин: /allow TELEGRAM_ID')
        return
    if text=='/id': await send(chat,f'Telegram ID: {uid}');return
    if text=='/balance':
        data=db.balances()
        await send(chat,'Касса ҳаракати (бошланғич қолдиқ киритилмаган):\n'+('\n'.join(f"{x['currency']}: {x['balance']}" for x in data) or 'Операциялар йўқ.'))
        return
    if text in ('/today','/month'):
        rows=db.report('today' if text=='/today' else 'month')
        await send(chat,'Ҳисобот:\n'+('\n'.join(f"{r['currency']} / {r['kind']} / {r['category']}: {r['total']} ({r['entries']} та)" for r in rows) or 'Операциялар йўқ.'))
        return
    if text.startswith('/allow '):
        if user_role!='admin': await send(chat,'Фақат админ учун.');return
        try:
            db.allow(uid,int(text.split()[1]))
            await send(chat,'✅ Кассирга рухсат берилди.')
        except (ValueError, IndexError): await send(chat,'Намуна: /allow 123456789')
        return
    if msg.get('voice'):
        text=await transcribe(msg['voice']['file_id'])
    if not text:
        await send(chat,'Овозли хабар ёки матн юборинг.')
        return
    op=await interpret(text)
    draft_id=db.save_draft(uid,text,op)
    markup={'inline_keyboard':[[{'text':'✅ Тасдиқлаш','callback_data':f'confirm:{draft_id}'},{'text':'❎ Бекор қилиш','callback_data':f'cancel:{draft_id}'}]]}
    await send(chat,f'Эшитилган матн: {text}\n\n{format_op(op)}\n\nТўғри бўлса тасдиқланг.',markup)

@app.get('/health')
async def health(): return {'status':'ok' if app.state.ready else 'setup_required','mode':'disposable_test' if TEST_MODE else 'production'}

@app.post('/webhook/{secret}')
async def webhook(secret:str,request:Request):
    if not app.state.ready: raise HTTPException(503,'Bot not configured')
    import secrets
    if not secrets.compare_digest(secret,SECRET): raise HTTPException(403)
    update=await request.json()
    update_id=update.get('update_id')
    if not isinstance(update_id,int): raise HTTPException(400)
    if not db.claim_update(update_id): return {'ok':True,'duplicate':True}
    try: await process(update)
    except (ValueError,PermissionError) as exc:
        m=update.get('message') or update.get('callback_query',{}).get('message',{})
        if m.get('chat',{}).get('id'): await send(m['chat']['id'],f'⚠️ {str(exc)[:300]}\nАниқроқ ёзинг ёки овозни қайта юборинг.')
    except Exception:
        logging.exception('Update failed: %s',update_id)
        db.release_update(update_id)
        raise HTTPException(500,'Processing failed; inspect logs')
    return {'ok':True}
