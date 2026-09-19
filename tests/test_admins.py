"""Tests for multi-admin configuration and preservation of cashier accounts."""
import os
import tempfile
import unittest
from unittest.mock import patch

import demo_db

class MultiAdminTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.original_path = demo_db.PATH
        demo_db.PATH = os.path.join(self.folder.name, "cashier.sqlite3")

    def tearDown(self):
        demo_db.PATH = self.original_path
        self.folder.cleanup()

    def test_two_admins_can_access(self):
        demo_db.init((101, 202))
        self.assertEqual(demo_db.role(101), "admin")
        self.assertEqual(demo_db.role(202), "admin")
        self.assertIsNone(demo_db.role(303))
        demo_db.allow(202, 303)
        self.assertEqual(demo_db.role(303), "cashier")

    def test_reconfigure_admins_does_not_remove_cashier(self):
        demo_db.init((101,))
        demo_db.allow(101, 303)
        demo_db.init((202, 101))
        self.assertEqual(demo_db.role(101), "admin")
        self.assertEqual(demo_db.role(202), "admin")
        self.assertEqual(demo_db.role(303), "cashier")
        demo_db.init((202,))
        self.assertIsNone(demo_db.role(101))
        self.assertEqual(demo_db.role(202), "admin")
        self.assertEqual(demo_db.role(303), "cashier")

    def test_disallow_missing_admins(self):
        with self.assertRaises(ValueError):
            demo_db.init(())
        with self.assertRaises(ValueError):
            demo_db.init((-10,))

    def test_non_admin_cannot_grant_cashier(self):
        demo_db.init((101, 202))
        with self.assertRaises(PermissionError):
            demo_db.allow(303, 404)

if __name__ == "__main__":
    unittest.main()
