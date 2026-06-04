import os
from dotenv import load_dotenv

load_dotenv()

class DBConfig:
    HOST     = os.getenv("PG_HOST", "localhost")
    PORT     = int(os.getenv("PG_PORT", 5432))
    NAME     = os.getenv("PG_DB")
    USER     = os.getenv("PG_USER")
    PASSWORD = os.getenv("PG_PASSWORD")
    POOL_MIN = int(os.getenv("POOL_MIN", 1))
    POOL_MAX = int(os.getenv("POOL_MAX", 5))

    @classmethod
    def validate(cls):
        missing = [k for k, v in {
            "PG_USER": cls.USER,
            "PG_PASSWORD": cls.PASSWORD,
            "PG_DB": cls.NAME,
        }.items() if not v]
        if missing:
            raise ValueError(f"Thiếu biến môi trường: {', '.join(missing)}")

    @classmethod
    def as_dict(cls):
        return {
            "host": cls.HOST,
            "port": cls.PORT,
            "user": cls.USER,
            "password": cls.PASSWORD,
            "database": cls.NAME,
            "options": "-c search_path=public",
        }


class VectorDBConfig:
    HOST     = os.getenv("VECTOR_PG_HOST", "localhost")
    PORT     = int(os.getenv("VECTOR_PG_PORT", 5433))
    NAME     = os.getenv("VECTOR_PG_DB", "a45839")
    USER     = os.getenv("VECTOR_PG_USER", "a45839")
    PASSWORD = os.getenv("VECTOR_PG_PASSWORD", "a45839")

    @classmethod
    def connection_string(cls) -> str:
        return (
            f"postgresql+psycopg://{cls.USER}:{cls.PASSWORD}"
            f"@{cls.HOST}:{cls.PORT}/{cls.NAME}"
        )

