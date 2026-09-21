
import os
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
import time
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Setup environment for testing
os.environ["DB_USER"] = "test-user"
os.environ["DB_PASSWORD"] = "test-pass"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "1521"
os.environ["DB_SERVICE_NAME"] = "TEST"
os.environ["SECRET_KEY"] = "super-secret-key-for-tests"

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.event import Event, AlertPolicy, AlertOutbox, AlertHistory
from app.core.notifier import Notifier
from app.alert_worker import process_alerts, MAX_RETRY

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class ALT001Tests(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

        # Insert Alert Policy
        policy = AlertPolicy(
            policy_id="POL-001",
            policy_name="Test Policy",
            severity_level="CRITICAL",
            notify_channel="TEST",
            is_active=1,
            created_at=datetime.now().date()
        )
        self.db.add(policy)

        # Insert Event
        event = Event(
            event_id=1,
            event_uid="evt-001",
            severity_code="CRITICAL",
            status_code="OPEN",
            title="Test Critical Event",
            message="Disk space is full",
            first_occurred_at=datetime.now(timezone.utc),
            occurrence_count=1
        )
        self.db.add(event)
        self.db.commit()

    def tearDown(self):
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()
        self.db.close()

    @patch('app.alert_worker.SessionLocal')
    @patch.object(Notifier, 'dispatch')
    def test_outbox_success_flow(self, mock_dispatch, mock_session_local):
        mock_session_local.return_value = self.db

        # 1st run: Enqueue + Process -> Success
        process_alerts()

        # Verify Notifier was called with TEST channel
        mock_dispatch.assert_called_once_with(
            channel="TEST",
            target="test-target",
            title="Test Critical Event",
            message="Disk space is full"
        )

        # Verify Outbox is empty (deleted)
        outbox_count = self.db.execute(select(AlertOutbox)).scalars().all()
        self.assertEqual(len(outbox_count), 0)

        # Verify History is created with SUCCESS
        history = self.db.execute(select(AlertHistory)).scalars().first()
        self.assertIsNotNone(history)
        self.assertEqual(history.status, "SUCCESS")

        # Verify Event is marked
        event = self.db.execute(select(Event).where(Event.event_id == 1)).scalars().first()
        self.assertIn("[ENQUEUED]", event.message)

        # Verify Duplication Prevention: 2nd run shouldn't dispatch again
        mock_dispatch.reset_mock()
        process_alerts()
        mock_dispatch.assert_not_called()

    @patch('app.alert_worker.SessionLocal')
    @patch.object(Notifier, 'dispatch')
    def test_outbox_failure_and_retry(self, mock_dispatch, mock_session_local):
        mock_session_local.return_value = self.db
        mock_dispatch.side_effect = Exception("Test Notification Failed")

        # 1st run: Fail (retry 1)
        process_alerts()
        outbox = self.db.execute(select(AlertOutbox)).scalars().first()
        self.assertIsNotNone(outbox)
        self.assertEqual(outbox.status, "FAILED")
        self.assertEqual(outbox.retry_count, 1)

        # 2nd run: Fail (retry 2)
        process_alerts()
        outbox = self.db.execute(select(AlertOutbox)).scalars().first()
        self.assertEqual(outbox.retry_count, 2)

        # 3rd run: Fail (retry 3 -> Max Retry, moved to history)
        process_alerts()

        # Should be deleted from outbox
        outbox_all = self.db.execute(select(AlertOutbox)).scalars().all()
        self.assertEqual(len(outbox_all), 0)

        # Should be in history as FAILED
        history = self.db.execute(select(AlertHistory)).scalars().first()
        self.assertIsNotNone(history)
        self.assertEqual(history.status, "FAILED")
        self.assertIn("Test Notification Failed", history.error_msg)

if __name__ == "__main__":
    unittest.main()
