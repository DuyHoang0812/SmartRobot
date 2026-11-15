import pytest
from pydantic import ValidationError

from app.core.config import Settings
from tests.support import validate_test_database_url


def test_settings_normalize_postgresql_driver_and_hide_secret():
    settings = Settings(_env_file=None, database_url="postgresql://user:secret@localhost/example")
    assert settings.database_url.get_secret_value().startswith("postgresql+psycopg://")
    assert "secret" not in repr(settings)


@pytest.mark.parametrize("url", ["sqlite:///test.db", "invalid", "postgresql://localhost"])
def test_settings_reject_invalid_database_urls(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url=url)


def test_invalid_settings_errors_do_not_expose_input():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url="sqlite://user:private-secret@localhost/test")
    assert "private-secret" not in str(error.value)


@pytest.mark.parametrize(
    "url, development_url",
    [
        ("postgresql://localhost/smartrobot", "postgresql://localhost/smartrobot"),
        ("postgresql://localhost/smartrobot_test", "postgresql://otherhost/smartrobot_test"),
        ("sqlite:///app_test", "postgresql://localhost/smartrobot"),
        (
            "postgresql://localhost/app_test?options=-csearch_path=public",
            "postgresql://localhost/smartrobot",
        ),
    ],
)
def test_database_guard_rejects_unsafe_targets(url, development_url):
    with pytest.raises(ValueError):
        validate_test_database_url(url, development_url)


def test_database_guard_accepts_separate_postgres_test_database():
    url = validate_test_database_url(
        "postgresql://localhost/smartrobot_test", "postgresql://localhost/smartrobot"
    )
    assert url.database == "smartrobot_test"
