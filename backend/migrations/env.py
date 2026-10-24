from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.core.database import Base
from app.models import entities  # noqa: F401

config = context.config
url = get_settings().database_url
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
