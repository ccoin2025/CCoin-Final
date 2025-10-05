from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import Pool
from dotenv import load_dotenv
import os
import structlog

logger = structlog.get_logger()

load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")

# بهبود Connection Pool
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,  # افزایش یافت از 5 به 20
    max_overflow=40,  # افزایش یافت از 10 به 40
    pool_timeout=30,
    pool_pre_ping=True,  # جدید: بررسی سلامت connection قبل از استفاده
    pool_recycle=3600,  # جدید: recycle connections هر ساعت
    echo=False,  # غیرفعال کردن SQL logging در production
)

# Event listener برای logging connection pool
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
    Dependency برای دریافت database session
    با مدیریت خودکار close
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
    بررسی سلامت اتصال دیتابیس
    """
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
