import getpass
import secrets
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import verify_password
from app.models import User
from app.models.enums import UserRole
from app.services.bootstrap import BootstrapError, create_initial_admin
from scripts.create_admin import main
from tests.test_database import add_user

pytestmark = pytest.mark.integration


def test_bootstrap_creates_initial_admin(db):
    password = secrets.token_urlsafe(24)
    admin = create_initial_admin(db, "firstadmin", "admin@example.com", password)
    assert admin.role == UserRole.ADMIN
    assert verify_password(password, admin.password_hash)
    with pytest.raises(BootstrapError, match="Đã có Admin"):
        create_initial_admin(db, "secondadmin", "second@example.com", password)


@pytest.mark.parametrize("field", ["username", "email"])
def test_bootstrap_rejects_duplicate_identity(db, field):
    add_user(db, username="existing", email="existing@example.com")
    db.commit()
    values = {"username": "another", "email": "another@example.com"}
    values[field] = "EXISTING" if field == "username" else "EXISTING@example.com"
    with pytest.raises(BootstrapError, match="đã được sử dụng"):
        create_initial_admin(db, password=secrets.token_urlsafe(24), **values)


def test_cli_uses_hidden_password_input(db_engine, capsys):
    password = secrets.token_urlsafe(24)
    with (
        patch("scripts.create_admin.sys.stdin.isatty", return_value=True),
        patch("builtins.input", side_effect=["bootstrap", "bootstrap@example.com"]),
        patch("scripts.create_admin.getpass.getpass", side_effect=[password, password]) as hidden,
        patch("scripts.create_admin.create_db_engine", return_value=db_engine),
    ):
        main()
    assert hidden.call_count == 2
    output = capsys.readouterr()
    assert "Đã tạo Admin" in output.out
    assert password not in output.out + output.err
    with Session(db_engine) as db:
        assert db.scalar(select(User)).role == UserRole.ADMIN


def test_cli_rejects_noninteractive_password_input():
    with (
        patch("scripts.create_admin.sys.stdin.isatty", return_value=False),
        pytest.raises(SystemExit, match="terminal tương tác"),
    ):
        main()


def test_bootstrap_rolls_back_on_failure(db_engine):
    factory = sessionmaker(db_engine)
    with factory() as db, pytest.raises(BootstrapError):
        create_initial_admin(db, "bad username", "invalid", "short")
    with factory() as db:
        assert db.scalar(select(User)) is None


def test_cli_refuses_password_echo_fallback():
    with (
        patch("scripts.create_admin.sys.stdin.isatty", return_value=True),
        patch("builtins.input", side_effect=["bootstrap", "bootstrap@example.com"]),
        patch("scripts.create_admin.getpass.getpass", side_effect=getpass.GetPassWarning),
        pytest.raises(SystemExit, match="không hỗ trợ nhập ẩn"),
    ):
        main()
