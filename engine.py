"""Conservative Uzbek/Russian cash extraction; do not infer missing amounts or currencies."""
from decimal import Decimal, InvalidOperation
import re

CATEGORIES = {'sales','debt_repayment','cash_in','salary','salary_advance','raw_materials','transport','fuel','household','other_income','other_expense'}

def validate_operation(op):
    if not isinstance(op, dict): raise ValueError('Operation must be an object')
    kind, currency, category = op.get('kind'), op.get('currency'), op.get('category')
    if kind not in ('income','expense'): raise ValueError('Invalid operation direction')
    if currency not in ('USD','UZS'): raise ValueError('Unknown currency')
    if category not in CATEGORIES: raise ValueError('Unknown category')
    raw = str(op.get('amount','')).strip()
    if not re.fullmatch(r'\d+(?:\.\d{1,2})?', raw): raise ValueError('Invalid monetary amount')
    try: amount = Decimal(raw)
    except InvalidOperation: raise ValueError('Invalid monetary amount')
    if not amount.is_finite() or amount <= 0 or amount > Decimal('999999999999'): raise ValueError('Amount out of range')
    if currency == 'UZS' and amount != amount.to_integral_value(): raise ValueError('UZS must be an integer')
    party = str(op.get('party') or '')[:120].strip()
    note = str(op.get('note') or '')[:300].strip()
    return {'kind':kind,'currency':currency,'category':category,'amount':amount,'party':party,'note':note}

def cash_signals(text):
    """Return direction/currency only if explicitly present; recognize common Whisper spellings."""
    t=text.lower().replace('’',"'").replace('‘',"'").replace('ʻ',"'")
    usd=bool(re.search(r'(?<!\w)(?:usd|dollar\w*|dolar\w*|dollor\w*|долл?а?р\w*|долор\w*|доллор\w*)(?!\w)|\$',t))
    uzs=bool(re.search(r"(?<!\w)(?:uzs|с[ўуо]м\w*|so'?m\w*|som\w*|sum\w*)(?!\w)",t))
    income=bool(re.search(r'(?<!\w)(?:кирим\w*|тушум\w*|олдим|олдик|олдум|келди|тушди|олганман|kirim\w*|tushum\w*|oldim|oldum|oldik|aldim|aldum|keldi|tushdi|sotdim|сотдим|получил\w*|поступил\w*|приход\w*)(?!\w)',t))
    expense=bool(re.search(r"(?<!\w)(?:чиқим\w*|чик[иы]м\w*|расход\w*|бердим|бердик|бердум|тўладим|туладим|сарф\w*|chiqim\w*|chikim\w*|chiqimga|berdim|berdum|berdik|toladim|to'ladim|tuladim|sarfladim|расходовал\w*|оплатил\w*|выдал\w*)(?!\w)",t))
    return ('USD' if usd and not uzs else 'UZS' if uzs and not usd else None,
            'income' if income and not expense else 'expense' if expense and not income else None)

def simple_parse(text):
    """Conservative digit-based fallback. Spelled-out numbers require an AI reading."""
    t=text.lower().replace('\u00a0',' ').replace('’',"'").replace('ʻ',"'")
    if re.search(r'(?<!\w)(?:перевод|ўтказма|o\'?tkazma|bankdan bankka)(?!\w)',t):
        raise ValueError('Банк ўтказмасини нақд кассага автоматик киритиб бўлмайди.')
    currency,kind=cash_signals(t)
    if currency is None: raise ValueError('Валютани USD ёки UZS деб аниқ кўрсатинг.')
    if kind is None: raise ValueError('Киримми ёки чиқимми — аниқ кўрсатинг.')
    # Require exactly one numeric amount. A second number might be a second transaction.
    numbers=list(re.finditer(r'(?<!\w)(\d{1,3}(?:[ ,]\d{3})+|\d+)(?:[.,](\d{1,2}))?\s*(млн|миллион|миллиард|минг|тысяч|million|ming|mln)?(?!\w)',t))
    if len(numbers)!=1: raise ValueError('Битта операциянинг битта суммасини аниқ айтиб беринг.')
    num=numbers[0]
    whole=num.group(1).replace(' ','').replace(',','')
    fraction=num.group(2)
    amount=Decimal(whole+('.'+fraction if fraction else ''))
    scale=(num.group(3) or '').lower()
    if scale in ('млн','миллион','million','mln'): amount*=1000000
    elif scale in ('минг','тысяч','ming'): amount*=1000
    elif scale=='миллиард': amount*=1000000000
    is_salary=bool(re.search(r'ойлик|ойлигидан|маош|зарплат|oylik|oyligidan|maosh|zarplat',t))
    if is_salary:
        category='salary_advance' if re.search(r'аванс|ойлигидан|oyligidan',t) else 'salary'
    elif re.search(r'қарз|карз|долг|qarz|karz',t):
        category='debt_repayment' if kind=='income' else 'other_expense'
    elif re.search(r'савдо|сотув|сотдим|продаж|savdo|sotuv|sotdim',t):
        category='sales' if kind=='income' else 'other_expense'
    elif re.search(r'бензин|ёқилғи|екل|топливо|benzin|yoqilgi|yoqilg',t):
        category='fuel'
    elif re.search(r'транспорт|такси|transport|taksi',t):
        category='transport'
    elif re.search(r'хомашё|хомаше|сырь|xomashyo|xomash',t):
        category='raw_materials'
    else:
        category='other_income' if kind=='income' else 'other_expense'
    return validate_operation({'kind':kind,'currency':currency,'amount':str(amount),'category':category,'note':text})
