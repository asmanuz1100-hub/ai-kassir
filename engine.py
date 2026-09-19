"""Deterministic monetary validation; never use floats for money."""
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

def simple_parse(text):
    """Conservative fallback: never guess complex figures or unspecified currency."""
    lower=text.lower().replace('\u00a0',' ')
    usd=bool(re.search(r'\b(?:usd|доллар|dollar|\$)\b|\$',lower))
    uzs=bool(re.search(r'\b(?:uzs|сўм|сум|som|so.m)\b',lower))
    if usd==uzs: raise ValueError('Валютани USD ёки UZS деб аниқ кўрсатинг.')
    number=re.search(r'(?<!\w)(\d[\d\s,]*)(?:\s*(млн|миллион|минг|тысяч))?(?!\w)',lower)
    if not number: raise ValueError('Сумма аниқланмади; рақам билан ёзинг.')
    amount=Decimal(number.group(1).replace(' ','').replace(',',''))
    scale=number.group(2)
    if scale in ('млн','миллион'): amount*=1000000
    elif scale in ('минг','тысяч'): amount*=1000
    income=bool(re.search(r'олдим|келди|тушум|кирим|получил|поступил',lower))
    expense=bool(re.search(r'бердим|тўладим|сарф|расход|оплатил|выдал',lower))
    if income==expense: raise ValueError('Киримми ёки чиқимми — аниқ кўрсатинг.')
    kind='income' if income else 'expense'
    if re.search(r'ойлик|зарплат|маош|ойлигидан',lower): category='salary_advance' if re.search(r'аванс|ойлигидан',lower) else 'salary'
    elif re.search(r'қарз|долг',lower): category='debt_repayment' if income else 'other_expense'
    elif re.search(r'савдо|продаж',lower): category='sales'
    elif re.search(r'бензин|ёқилғи|топливо',lower): category='fuel'
    elif re.search(r'транспорт|такси',lower): category='transport'
    else: category='other_income' if income else 'other_expense'
    return validate_operation({'kind':kind,'currency':'USD' if usd else 'UZS','amount':str(amount),'category':category,'note':text})
