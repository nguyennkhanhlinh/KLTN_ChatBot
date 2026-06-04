import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from data.database import Database

CSV_PATH = os.path.join(os.path.dirname(__file__), "data_clean.csv")

PROPERTIES_SQL = """
    INSERT INTO properties (ma_code, tieu_de, ngay_dang, quan, phuong, tong_gia, gia_theo_m2, dien_tich, so_tang, so_phong_ngu, so_phong_tam, phap_ly, noi_that)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (ma_code) DO NOTHING
"""


def load_data():
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]
    df = df.where(pd.notna(df), None)

    properties_rows = [
        (
            row["Mã code"],
            row["Tiêu đề"],
            row["Ngày đăng"] if row["Ngày đăng"] else None,
            row["Quận/Huyện"],
            row["Phường/Xã"],
            row["Tổng giá (tỷ)"],
            row["Giá theo m² (triệu/m²)"],
            row["Diện tích (m²)"],
            int(row["Số tầng"]) if row["Số tầng"] is not None else None,
            int(row["Số phòng ngủ"]) if row["Số phòng ngủ"] is not None else None,
            int(row["Số phòng tắm, vệ sinh"]) if row["Số phòng tắm, vệ sinh"] is not None else None,
            row["Pháp lý"],
            row["Nội thất"],
        )
        for _, row in df.iterrows()
    ]

   

    with Database.get_conn() as conn:
        with conn.cursor() as cur:
            from psycopg2.extras import execute_batch
            execute_batch(cur, PROPERTIES_SQL, properties_rows)

    print(f"Inserted {len(properties_rows)} rows into properties ")

if __name__ == "__main__":
    try:
        load_data()
    except Exception as e:
        print("Error ingesting data:", e)
