"""IMAP fetch must persist before archiving, otherwise Etsy orders vanish."""

from __future__ import annotations

import email
import unittest
from email.message import EmailMessage
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.etsy_mail import (
    _imap_download,
    _message_id,
    fetch_new_mails,
    fetch_new_mails_standalone,
)
from app.models import IncomingMail


def _raw_email(*, message_id: str | None, subject: str, from_addr: str, body: str) -> bytes:
    msg = EmailMessage()
    if message_id is not None:
        msg["Message-ID"] = message_id
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["Date"] = "Thu, 17 Sep 2026 12:00:00 +0000"
    msg.set_content(body)
    return msg.as_bytes()


class FakeSock:
    def settimeout(self, _value: float) -> None:
        return None


class FakeIMAP:
    """Minimal IMAP4_SSL stand-in. Shared inbox state across connections."""

    inbox: dict[bytes, bytes] = {}
    copied: list[bytes] = []
    stored: list[bytes] = []
    instances: list["FakeIMAP"] = []

    def __init__(self, *args, **kwargs) -> None:
        self.sock = FakeSock()
        self.selected: str | None = None
        FakeIMAP.instances.append(self)

    @classmethod
    def reset(cls, inbox: dict[bytes, bytes] | None = None) -> None:
        cls.inbox = dict(inbox or {})
        cls.copied = []
        cls.stored = []
        cls.instances = []

    def login(self, user: str, password: str):
        return "OK", [b"Logged in"]

    def select(self, name: str):
        self.selected = name
        return "OK", [b"1"]

    def create(self, name: str):
        return "OK", [b"created"]

    def uid(self, cmd: str, *args):
        command = (cmd or "").upper()
        if command == "SEARCH":
            if not FakeIMAP.inbox:
                return "OK", [None]
            return "OK", [b" ".join(FakeIMAP.inbox.keys())]
        if command == "FETCH":
            uid = args[0]
            raw = FakeIMAP.inbox.get(uid)
            if raw is None:
                return "OK", [None]
            return "OK", [(b"1 (RFC822 {%d}" % len(raw), raw)]
        if command == "COPY":
            FakeIMAP.copied.append(args[0])
            return "OK", [b"copied"]
        if command == "STORE":
            FakeIMAP.stored.append(args[0])
            FakeIMAP.inbox.pop(args[0], None)
            return "OK", [b"stored"]
        raise AssertionError(f"unexpected UID command {cmd!r}")

    def expunge(self):
        return "OK", []

    def logout(self):
        return "BYE", []


class EtsyImapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        FakeIMAP.reset(
            {
                b"101": _raw_email(
                    message_id="<order-101@etsy>",
                    subject="Etsy-Bestellung 101",
                    from_addr="Etsy <noreply@etsy.com>",
                    body="Neue Bestellung 101",
                )
            }
        )
        self.imap_patch = patch("app.etsy_mail.imaplib.IMAP4_SSL", FakeIMAP)
        self.settings_patch = patch("app.etsy_mail.settings")
        self.imap_patch.start()
        self.settings = self.settings_patch.start()
        self.settings.imap_host = "imap.example.com"
        self.settings.imap_port = 993
        self.settings.imap_user = "user"
        self.settings.imap_password = "secret"
        self.settings.imap_folder = "INBOX"
        self.settings.imap_processed_folder = "verarbeitet"
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.addCleanup(self.settings_patch.stop)
        self.addCleanup(self.imap_patch.stop)

    def test_download_does_not_archive_new_mail(self) -> None:
        new_mails, errors = _imap_download(set())
        self.assertEqual(errors, [])
        self.assertEqual(len(new_mails), 1)
        self.assertEqual(new_mails[0]["message_id"], "<order-101@etsy>")
        self.assertEqual(FakeIMAP.copied, [])
        self.assertEqual(FakeIMAP.stored, [])
        self.assertIn(b"101", FakeIMAP.inbox)

    def test_fetch_archives_only_after_commit(self) -> None:
        result = fetch_new_mails(self.db)
        self.assertEqual(result["fetched"], 1)
        self.assertEqual(result["errors"], [])
        self.assertEqual(FakeIMAP.copied, [b"101"])
        self.assertEqual(FakeIMAP.stored, [b"101"])

        row = self.db.scalars(select(IncomingMail)).first()
        self.assertIsNotNone(row)
        self.assertEqual(row.message_id, "<order-101@etsy>")
        self.assertEqual(row.status, "pending")

    def test_committed_mail_survives_later_rollback(self) -> None:
        fetch_new_mails(self.db)
        self.db.rollback()
        other = self.Session()
        try:
            row = other.scalars(select(IncomingMail)).first()
            self.assertIsNotNone(row)
            self.assertEqual(row.message_id, "<order-101@etsy>")
        finally:
            other.close()

    def test_persist_failure_leaves_mail_in_inbox(self) -> None:
        with patch(
            "app.etsy_mail._persist_downloaded_mails",
            side_effect=RuntimeError("db down"),
        ):
            with self.assertRaises(RuntimeError):
                fetch_new_mails(self.db)
        self.assertEqual(FakeIMAP.copied, [])
        self.assertEqual(FakeIMAP.stored, [])
        self.assertIn(b"101", FakeIMAP.inbox)
        self.assertIsNone(self.db.scalars(select(IncomingMail)).first())

    def test_standalone_archives_after_own_commit(self) -> None:
        with patch("app.database.SessionLocal", self.Session):
            result = fetch_new_mails_standalone()
        self.assertEqual(result["fetched"], 1)
        self.assertEqual(FakeIMAP.copied, [b"101"])
        other = self.Session()
        try:
            self.assertEqual(other.scalars(select(IncomingMail)).first().message_id, "<order-101@etsy>")
        finally:
            other.close()

    def test_already_stored_mail_is_archived_on_retry(self) -> None:
        self.db.add(
            IncomingMail(
                origin="etsy",
                message_id="<order-101@etsy>",
                subject="Etsy-Bestellung 101",
                from_addr="Etsy <noreply@etsy.com>",
                body_text="Neue Bestellung 101",
                status="pending",
            )
        )
        self.db.commit()
        new_mails, errors = _imap_download({"<order-101@etsy>"})
        self.assertEqual(errors, [])
        self.assertEqual(new_mails, [])
        self.assertEqual(FakeIMAP.copied, [b"101"])
        self.assertNotIn(b"101", FakeIMAP.inbox)

    def test_fallback_message_id_is_stable(self) -> None:
        raw = _raw_email(
            message_id=None,
            subject="Ohne Message-ID",
            from_addr="Etsy <noreply@etsy.com>",
            body="x",
        )
        first = _message_id(email.message_from_bytes(raw))
        second = _message_id(email.message_from_bytes(raw))
        self.assertTrue(first.startswith("local-"))
        self.assertEqual(first, second)
        self.assertNotIn("None", first)


if __name__ == "__main__":
    unittest.main()
