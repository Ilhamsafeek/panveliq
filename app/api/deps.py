# Dependency placeholders (db session, auth)
from typing import Generator

def get_db() -> Generator:
    """Yield database session"""
    yield None
