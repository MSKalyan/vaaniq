from sqlalchemy.engine import make_url

from app.core.config import Settings


def test_database_urls_escape_credentials() -> None:
    settings = Settings(
        _env_file=None,
        database_host="postgres",
        database_user="voice user",
        database_password="p@ss:/#%",
        database_name="VoiceAI",
    )

    async_url = make_url(settings.database_url)
    sync_url = make_url(settings.database_url_sync)

    assert async_url.drivername == "postgresql+asyncpg"
    assert sync_url.drivername == "postgresql+psycopg2"
    for url in (async_url, sync_url):
        assert url.username == "voice user"
        assert url.password == "p@ss:/#%"
        assert url.host == "postgres"
        assert url.database == "VoiceAI"
