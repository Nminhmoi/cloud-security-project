import os
import sys
import unittest
from unittest.mock import patch

from sqlalchemy.engine import make_url


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_ROOT = os.path.join(PROJECT_ROOT, "app")
sys.path.insert(0, APP_ROOT)

from config import _database_uri, _engine_options  # noqa: E402


class DatabaseConfigTests(unittest.TestCase):
    def test_discrete_mysql_settings_escape_password(self):
        environment = {
            "DB_HOST": "db.internal",
            "DB_PORT": "3307",
            "DB_NAME": "cloudbox",
            "DB_USER": "cloudbox_user",
            "DB_PASSWORD": "p@ss:/word",
        }
        with patch.dict(os.environ, environment, clear=True):
            url = make_url(_database_uri())

        self.assertEqual(url.drivername, "mysql+pymysql")
        self.assertEqual(url.host, "db.internal")
        self.assertEqual(url.port, 3307)
        self.assertEqual(url.database, "cloudbox")
        self.assertEqual(url.password, "p@ss:/word")

    def test_database_url_takes_precedence_and_selects_pymysql(self):
        environment = {
            "DATABASE_URL": "mysql://chosen:secret@database:3306/chosen_db",
            "DB_HOST": "ignored",
        }
        with patch.dict(os.environ, environment, clear=True):
            url = make_url(_database_uri())

        self.assertEqual(url.drivername, "mysql+pymysql")
        self.assertEqual(url.host, "database")
        self.assertEqual(url.database, "chosen_db")

    def test_incomplete_mysql_settings_fail_fast(self):
        with patch.dict(os.environ, {"DB_HOST": "database"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DB_NAME, DB_PASSWORD, DB_USER"):
                _database_uri()

    def test_invalid_mysql_port_fails_fast(self):
        environment = {
            "DB_HOST": "database",
            "DB_PORT": "not-a-number",
            "DB_NAME": "cloudbox",
            "DB_USER": "cloudbox",
            "DB_PASSWORD": "secret",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(RuntimeError, "DB_PORT must be an integer"):
                _database_uri()

    def test_mysql_tls_ca_is_passed_to_driver(self):
        with patch.dict(os.environ, {"DB_SSL_CA": "/run/secrets/rds-ca.pem"}, clear=True):
            options = _engine_options("mysql+pymysql://user:password@db/cloudbox")

        self.assertTrue(options["pool_pre_ping"])
        self.assertEqual(
            options["connect_args"],
            {"ssl": {"ca": "/run/secrets/rds-ca.pem"}},
        )


if __name__ == "__main__":
    unittest.main()
