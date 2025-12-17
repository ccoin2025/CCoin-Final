from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import Pool
from dotenv import load_dotenv
import os
import structlog
from CCOIN.config import BOT_USERNAME

logger = structlog.get_logger()

load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")

BOT_USERNAME = os.getenv("BOT_USERNAME", "CTG_COIN_BOT")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20, 
    max_overflow=40, 
    pool_timeout=30,
    pool_pre_ping=True,  
    pool_recycle=3600, 
    echo=False,
)

@event.listens_for(Pool, "connect")
def receive_connect(dbapi_conn, connection_record):
    logger.debug("New database connection established")

@event.listens_for(Pool, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    logger.debug("Connection checked out from pool")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """
    Dependency for getting a database session
    with automatic close management
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def get_db_health():
    """
    Check database connection health
    """
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
