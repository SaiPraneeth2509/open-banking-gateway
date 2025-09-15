from app.db.base import Base
from app.db.session import engine
import app.models.consent

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
