import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_batch
from contextlib import contextmanager
from configs.db import DBConfig

class Database:
    _pool = None

    @classmethod
    def get_pool(cls):
        if cls._pool is None:
            DBConfig.validate()
            cls._pool = pool.SimpleConnectionPool(
                minconn=DBConfig.POOL_MIN,
                maxconn=DBConfig.POOL_MAX,
                **DBConfig.as_dict(),
            )
        return cls._pool

    @classmethod
    @contextmanager
    def get_conn(cls):
        conn = cls.get_pool().getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO public")  
            conn.commit()
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cls.get_pool().putconn(conn)
            
    @classmethod
    def create_tables(cls):
        sql = """
        CREATE TABLE IF NOT EXISTS properties (
            ma_code         int PRIMARY KEY,
            tieu_de         TEXT NOT NULL,
            ngay_dang       DATE,
            quan            TEXT,
            phuong          TEXT,
            tong_gia        float,
            gia_theo_m2     float,
            dien_tich       float,
            so_tang         int,
            so_phong_ngu    int,
            so_phong_tam    int,
            phap_ly         TEXT,
            noi_that        TEXT
        );

        """
        with cls.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("Tables created successfully.")


if __name__ == "__main__":
    try:
        Database.create_tables()
    except Exception as e:
        print("Error creating tables:", e)
