import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from psycopg2 import sql as pgsql
from data.database import Database

@tool
def get_schema(table_name: str = "properties") -> str:
    """Lấy schema (cấu trúc bảng) trực tiếp từ PostgreSQL.

    Tool này PHẢI được gọi đầu tiên trong mỗi lượt phân tích trước khi gọi
    execute_sql, get_unique_values hoặc viết SQL.

    Dùng khi cần xác nhận tên cột, kiểu dữ liệu hoặc mô tả cột chính xác
    trước khi viết câu SQL.

    Args:
        table_name: Tên bảng cần lấy schema (mặc định: "properties").
    """
    try:
        query = pgsql.SQL(
            "SELECT a.attname,"
            " format_type(a.atttypid, a.atttypmod),"
            " col_description(a.attrelid, a.attnum)"
            " FROM pg_attribute a"
            " WHERE a.attrelid = {}::regclass"
            " AND a.attnum > 0 AND NOT a.attisdropped"
            " ORDER BY a.attnum"
        ).format(pgsql.Literal(f"public.{table_name}"))

        with Database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()

        if not rows:
            return f"Không tìm thấy bảng '{table_name}'."

        lines = [f"Table: {table_name}"]
        for col_name, col_type, col_desc in rows:
            desc = f" — {col_desc}" if col_desc else ""
            lines.append(f"  - {col_name} ({col_type}){desc}")
        return "\n".join(lines)

    except Exception as e:
        return f"Lỗi khi lấy schema: {e}"
