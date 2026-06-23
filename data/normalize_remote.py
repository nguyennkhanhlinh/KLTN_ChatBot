"""Chuẩn hoá phap_ly + noi_that TẠI CHỖ trên DB đang cấu hình (qua biến môi trường PG_*).

Dùng cho Render: đặt PG_HOST/PG_PORT/PG_DB/PG_USER/PG_PASSWORD trỏ tới Render Postgres
(lấy External Database URL trong dashboard), rồi chạy:
    python data/normalize_remote.py
Script chỉ UPDATE 2 cột, KHÔNG xoá hay đụng dữ liệu khác.
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.database import Database
from data.ingest_data import normalize_phap_ly, normalize_noi_that


def _fix(cur, col, fn):
    cur.execute(f"SELECT DISTINCT {col} FROM properties")
    vals = [r[0] for r in cur.fetchall()]
    changed = 0
    for old in vals:
        new = fn(old)
        if new == old:
            continue
        if old is None:
            cur.execute(f"UPDATE properties SET {col}=%s WHERE {col} IS NULL", (new,))
        else:
            cur.execute(f"UPDATE properties SET {col}=%s WHERE {col}=%s", (new, old))
        changed += cur.rowcount
    return changed


def main():
    with Database.get_conn() as conn:
        with conn.cursor() as cur:
            n1 = _fix(cur, "phap_ly", normalize_phap_ly)
            n2 = _fix(cur, "noi_that", normalize_noi_that)
    print(f"phap_ly: cập nhật {n1} dòng | noi_that: cập nhật {n2} dòng")


if __name__ == "__main__":
    main()
