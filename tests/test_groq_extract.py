"""No live Groq requests: exercise mock structured responses and cash validation."""
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock
from types import SimpleNamespace
from groq_extract import extract, normalize_voice_text

def fake_client(payload):
    create=AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]))
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

class GroqCashTests(unittest.IsolatedAsyncioTestCase):
    async def test_uzbek_spoken_usd_income(self):
        client=fake_client('{"kind":"income","currency":"USD","category":"sales","amount":"500","party":"Фурқат","note":"Наманган"}')
        op=await extract(client,'Фурқатдан беш юз доллар олдим','test-model')
        self.assertEqual(op['amount'],Decimal('500'))
        self.assertEqual(op['currency'],'USD')
        self.assertEqual(op['kind'],'income')

    async def test_uzbek_spoken_salary_advance(self):
        client=fake_client('{"kind":"expense","currency":"UZS","category":"salary_advance","amount":"1000000","party":"","note":""}')
        op=await extract(client,'Ишчига ойлигидан бир миллион сўм бердим','test-model')
        self.assertEqual(op['amount'],Decimal('1000000'))
        self.assertEqual(op['category'],'salary_advance')

    async def test_voice_spellings_normalized(self):
        self.assertIn('доллар', normalize_voice_text('кирим 500 долор'))
        self.assertIn('сўм', normalize_voice_text('чиқим 1200 сом'))
        self.assertIn('кирим', normalize_voice_text('kirim 500 dollor'))

    async def test_short_spoken_cash_when_model_uncertain(self):
        client=fake_client('{"error":"unclear"}')
        op=await extract(client,'кирим 500 долор наманган','test-model')
        self.assertEqual(op['kind'],'income')
        self.assertEqual(op['currency'],'USD')
        self.assertEqual(op['amount'],Decimal('500'))

    async def test_real_voice_furgatdan_dolar_oldum(self):
        client=fake_client('{"error":"unclear"}')
        op=await extract(client,'Namangan, Furgatdan 500 dolar oldum.','test-model')
        self.assertEqual((op['kind'],op['currency'],op['amount'],op['category']),
                         ('income','USD',Decimal('500'),'other_income'))

    async def test_real_voice_dolara_ending(self):
        client=fake_client('{"error":"unclear"}')
        op=await extract(client,'Namangan Furgatdan 500 dolara oldum.','test-model')
        self.assertEqual((op['kind'],op['currency'],op['amount']),
                         ('income','USD',Decimal('500')))

    async def test_spoken_expense_latin(self):
        client=fake_client('{"error":"unclear"}')
        op=await extract(client,'Ishchiga oyligidan 1 million som berdim','test-model')
        self.assertEqual((op['kind'],op['currency']),('expense','UZS'))

    async def test_model_cannot_invent_sales_category(self):
        client=fake_client('{"kind":"income","currency":"USD","category":"sales","amount":"500","party":"Furgat","note":""}')
        op=await extract(client,'Namangan Furgatdan 500 dolar oldum','test-model')
        self.assertEqual(op['category'],'other_income')
        self.assertEqual(op['party'],'Furgat')

    async def test_unstated_currency_stays_ambiguous(self):
        with self.assertRaises(ValueError):
            await extract(fake_client('{"error":"unclear"}'),'кирим 500','test-model')

    async def test_ambiguous_rejected(self):
        with self.assertRaises(ValueError):
            await extract(fake_client('{"error":"unclear"}'),'Бугун пул бердим','test-model')

    async def test_invalid_currency_rejected(self):
        with self.assertRaises(ValueError):
            await extract(fake_client('{"kind":"expense","currency":"EUR","category":"fuel","amount":"100","party":"","note":""}'),'100 евро бензинга бердим','test-model')

    async def test_fallback_requires_explicit_currency(self):
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError('provider unavailable')))))
        with self.assertRaises(ValueError):
            await extract(client,'500 олдим','test-model')

if __name__=='__main__':
    unittest.main()
