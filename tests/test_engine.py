import unittest
from decimal import Decimal
from engine import validate_operation, simple_parse

class CashTests(unittest.TestCase):
    def test_income_usd(self):
        op=simple_parse('Савдодан 500 доллар олдим')
        self.assertEqual((op['kind'],op['currency'],op['amount'],op['category']),('income','USD',Decimal('500'),'sales'))
    def test_wage_advance(self):
        op=simple_parse('Ишчига ойлигидан 1 млн сўм бердим')
        self.assertEqual((op['kind'],op['amount'],op['category']),('expense',Decimal('1000000'),'salary_advance'))
    def test_missing_currency(self):
        with self.assertRaises(ValueError): simple_parse('500 олдим')
    def test_negative_rejected(self):
        with self.assertRaises(ValueError): validate_operation({'kind':'income','currency':'USD','category':'sales','amount':'-500'})
    def test_uzs_fraction_rejected(self):
        with self.assertRaises(ValueError): validate_operation({'kind':'income','currency':'UZS','category':'sales','amount':'2.50'})
if __name__=='__main__': unittest.main()
