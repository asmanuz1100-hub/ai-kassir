"""No live Groq requests: exercise mock structured responses and cash validation."""
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock
from types import SimpleNamespace
from groq_extract import extract

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
