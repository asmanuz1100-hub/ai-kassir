"""Cashier's simple daily notebook: list every confirmed entry and keep currency separate."""
import os
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import demo_db
from daily_book import daily_report

class DailyBookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.previous=demo_db.PATH
        demo_db.PATH=os.path.join(self.temp.name,'test.sqlite3')
        demo_db.init((101,202))

    def tearDown(self):
        demo_db.PATH=self.previous
        self.temp.cleanup()

    def test_empty_day(self):
        self.assertIn('ҳали кирим-чиқим қайд этилмаган', daily_report(demo_db.today_entries()))

    def test_two_currencies_and_transactions(self):
        demo_db.allow(101,303)
        a=demo_db.save_draft(303,'Фурқат 500 доллар олдим',{'kind':'income','amount':Decimal('500'),'currency':'USD','category':'sales','party':'Фурқат','note':'Савдо'})
        b=demo_db.save_draft(303,'ишчига 1 млн сўм бердим',{'kind':'expense','amount':Decimal('1000000'),'currency':'UZS','category':'salary','party':'Ишчи','note':'Ойлик'})
        self.assertIn('сақланди',demo_db.confirm(303,a))
        self.assertIn('сақланди',demo_db.confirm(303,b))
        data=demo_db.today_entries(303)
        output=daily_report(data)
        self.assertIn('Фурқат',output)
        self.assertIn('+500 USD',output)
        self.assertIn('−1 000 000 UZS',output)
        self.assertIn('Жами кирим: 500 USD',output)
        self.assertIn('Жами чиқим: 1 000 000 UZS',output)
        self.assertEqual(len(demo_db.today_entries(202)),0)

    def test_entry_mode_for_one_cashier_only(self):
        demo_db.set_entry_mode(101,'income')
        self.assertEqual(demo_db.get_entry_mode(101),'income')
        self.assertIsNone(demo_db.get_entry_mode(202))
        demo_db.set_entry_mode(101,'expense')
        self.assertEqual(demo_db.get_entry_mode(101),'expense')
        demo_db.clear_entry_mode(101)
        self.assertIsNone(demo_db.get_entry_mode(101))

    def test_one_day_boundary_and_cancel(self):
        draft=demo_db.save_draft(101,'500 USD кирим',{'kind':'income','amount':Decimal('500'),'currency':'USD','category':'other_income','party':'','note':'тест'})
        demo_db.cancel(101,draft)
        self.assertEqual(demo_db.today_entries(),[])
        draft2=demo_db.save_draft(101,'500 USD кирим',{'kind':'income','amount':Decimal('500'),'currency':'USD','category':'other_income','party':'','note':'тест'})
        demo_db.confirm(101,draft2)
        with demo_db.connect() as conn:
            conn.execute("UPDATE ledger SET created_at=? WHERE draft_id=?",('2020-01-01T13:00:00+05:00',draft2))
        self.assertEqual(demo_db.today_entries(),[])

if __name__=='__main__':
    unittest.main()
