from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.database.session import get_db

# Re-export get_db for clean dependency injection
__all__ = ["get_db", "Session"]
