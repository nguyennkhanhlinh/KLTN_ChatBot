import re
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from data.database import Database

@tool
def execute_sql(sql_query: str, output_format: str = "text") -> str:
    """Thực thi truy vấn SQL trên cơ sở dữ liệu PostgreSQL.

    Args:
        sql_query: Câu truy vấn SQL cần thực thi.
        output_format: Định dạng kết quả trả về. Dùng "json" nếu người dùng yêu cầu vẽ biểu đồ, "text" cho các trường hợp còn lại.
    """
    sql = sql_query.strip()
    sql = re.sub(r"^```(?:sql)?", "", sql, flags=re.IGNORECASE).rstrip("```").strip()

    _FORBIDDEN = {"DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE",
                  "CREATE", "GRANT", "REVOKE", "REPLACE"}
    tokens = {t.upper() for t in sql.split()}
    blocked = _FORBIDDEN & tokens
    if blocked:
        return f"Lỗi: câu SQL chứa keyword không được phép: {', '.join(sorted(blocked))}."

    if "limit" not in sql.lower():
        sql = sql.rstrip(";") + " LIMIT 100"

    try:
        with Database.get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)

                if cursor.description is None:
                    return "Truy vấn thực thi thành công (không có dữ liệu trả về)."

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

                if not rows:
                    return "Không tìm thấy dữ liệu phù hợp."

                if output_format == "json":
                    return json.dumps({
                        "columns": columns,
                        "data": [[str(v) if v is not None else None for v in row] for row in rows]
                    }, ensure_ascii=False)

                lines = [" | ".join(columns)]
                lines.append("-" * len(lines[0]))
                for row in rows:
                    lines.append(" | ".join(str(v) if v is not None else "NULL" for v in row))
                return "\n".join(lines)

    except Exception as e:
        return f"Lỗi khi thực thi SQL: {e}"
