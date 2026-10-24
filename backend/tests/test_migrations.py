from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.core.config import get_settings
from app.core.database import Base, make_engine
from conftest import ROOT


def test_initial_migration_matches_models_and_is_reversible(tmp_path):
    settings = get_settings()
    previous_url = settings.database_url
    settings.database_url = f"sqlite:///{tmp_path}/migrated.db"
    engine = make_engine(settings.database_url)
    config = Config(str(ROOT / "backend/alembic.ini"))
    try:
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "base")
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        command.upgrade(config, "head")
        assert {"rules", "rule_versions", "test_runs"}.issubset(inspect(engine).get_table_names())
    finally:
        settings.database_url = previous_url
        engine.dispose()
