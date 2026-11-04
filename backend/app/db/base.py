from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Matches PostgreSQL's default constraint names, so databases created by the old
# create_all() code and databases created by Alembic end up with identical names.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
