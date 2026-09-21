import os
import unittest
from spool import MetricSpooler

class SpoolerTests(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_spool.db"
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self.spooler = MetricSpooler(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_push_and_pop(self):
        metrics = [{"a": 1}, {"b": 2}]
        self.spooler.push(metrics)
        self.assertEqual(self.spooler.get_count(), 2)

        ids, batch = self.spooler.pop_batch(10)
        self.assertEqual(len(batch), 2)
        self.assertEqual(len(ids), 2)

        # Should not be deleted yet
        self.assertEqual(self.spooler.get_count(), 2)

        # Ack batch
        self.spooler.ack_batch(ids)
        self.assertEqual(self.spooler.get_count(), 0)

if __name__ == "__main__":
    unittest.main()
