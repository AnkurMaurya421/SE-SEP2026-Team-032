"""The database address is tidied up before SQLAlchemy uses it (needed for Supabase on the live site)."""
from config import database_url


def test_no_setting_means_sqlite(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database_url() == "sqlite:///mentor_connect.db"


def test_empty_setting_means_sqlite(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    assert database_url() == "sqlite:///mentor_connect.db"


def test_supabase_address_uses_psycopg2_and_ssl(monkeypatch):
    for start in ["postgres://", "postgresql://"]:
        monkeypatch.setenv("DATABASE_URL", start + "user:pw@host:5432/postgres")
        assert database_url() == "postgresql+psycopg2://user:pw@host:5432/postgres?sslmode=require"


def test_existing_options_are_kept(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host:5432/postgres?sslmode=verify-full")
    assert database_url() == "postgresql+psycopg2://user:pw@host:5432/postgres?sslmode=verify-full"
