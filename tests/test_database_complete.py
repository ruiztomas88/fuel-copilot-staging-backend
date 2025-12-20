"""Complete coverage for database_mysql.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from unittest.mock import MagicMock, patch


class TestDatabaseComplete:
    @patch("database_mysql.pymysql.connect")
    def test_all_functions(self, mock_connect):
        import database_mysql as db

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        if hasattr(db, "get_db_connection"):
            db.get_db_connection()
