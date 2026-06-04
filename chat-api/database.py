from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = (
    "postgresql://bankbot:BankBot@123"
    "@postgres.bankbot.svc.cluster.local:5432/bankbot"
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
