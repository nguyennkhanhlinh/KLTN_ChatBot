import json
from typing import Optional, List

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class CompareScenariosInput(BaseModel):
    equity: float = Field(description="Vốn tự có, đơn vị tỷ VNĐ")
    target_price: float = Field(description="Giá BĐS mục tiêu, đơn vị tỷ VNĐ")
    compare_by: str = Field(
        default="term",
        description="'term': so sánh theo thời hạn vay (10/15/20/25/30 năm), 'rate': so sánh theo lãi suất",
    )
    interest_rate: Optional[float] = Field(
        default=None,
        description="Lãi suất %/năm. Bắt buộc khi compare_by='term'",
    )
    loan_term_years: Optional[int] = Field(
        default=None,
        description="Thời hạn vay (năm). Bắt buộc khi compare_by='rate'",
    )
    custom_rates: Optional[List[float]] = Field(
        default=None,
        description="Danh sách lãi suất tùy chỉnh khi compare_by='rate'. Mặc định: [7, 8, 9, 10, 11, 12]",
    )


def _pmt(loan_ty: float, rate_pct: float, term_years: int) -> float:
    """Tính trả góp tháng (đơn vị triệu VNĐ)."""
    r = (rate_pct / 100) / 12
    n = term_years * 12
    return round(loan_ty * 1_000 * r * (1 + r) ** n / ((1 + r) ** n - 1), 2)


def _total_interest(loan_ty: float, pmt_m: float, term_years: int) -> float:
    """Tổng lãi phải trả (đơn vị triệu VNĐ)."""
    return round(pmt_m * term_years * 12 - loan_ty * 1_000, 1)


@tool("compare_loan_scenarios", args_schema=CompareScenariosInput)
def compare_loan_scenarios(
    equity: float,
    target_price: float,
    compare_by: str = "term",
    interest_rate: Optional[float] = None,
    loan_term_years: Optional[int] = None,
    custom_rates: Optional[List[float]] = None,
) -> str:
    """So sánh nhiều kịch bản vay BĐS theo thời hạn hoặc lãi suất. Trả về JSON chart."""
    loan = target_price - equity
    if loan <= 0:
        return json.dumps({"error": "Vốn tự có đã đủ để mua, không cần vay."}, ensure_ascii=False)

    ltv = round(loan / target_price * 100, 1)
    ltv_label = "An toàn" if ltv <= 60 else ("Chấp nhận được" if ltv <= 70 else "Rủi ro cao")

    scenarios = []

    if compare_by == "term":
        if interest_rate is None:
            return json.dumps(
                {"error": "Cần cung cấp interest_rate khi compare_by='term'."},
                ensure_ascii=False,
            )
        for t in [10, 15, 20, 25, 30]:
            p = _pmt(loan, interest_rate, t)
            ti = _total_interest(loan, p, t)
            scenarios.append({
                "label": f"{t} năm",
                "term_years": t,
                "rate_pct": interest_rate,
                "monthly_payment_m": p,
                "total_interest_m": ti,
                "total_interest_ty": round(ti / 1_000, 3),
            })
        title = f"So sánh trả góp/tháng theo thời hạn vay (lãi suất {interest_rate}%/năm)"

    else:  # compare_by == "rate"
        if loan_term_years is None:
            return json.dumps(
                {"error": "Cần cung cấp loan_term_years khi compare_by='rate'."},
                ensure_ascii=False,
            )
        rates = custom_rates or [7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        for rate in rates:
            p = _pmt(loan, rate, loan_term_years)
            ti = _total_interest(loan, p, loan_term_years)
            scenarios.append({
                "label": f"{rate}%",
                "term_years": loan_term_years,
                "rate_pct": rate,
                "monthly_payment_m": p,
                "total_interest_m": ti,
                "total_interest_ty": round(ti / 1_000, 3),
            })
        title = f"So sánh trả góp/tháng theo lãi suất (thời hạn {loan_term_years} năm)"

    min_s = min(scenarios, key=lambda s: s["monthly_payment_m"])  # thời hạn dài / lãi thấp
    max_s = max(scenarios, key=lambda s: s["monthly_payment_m"])  # thời hạn ngắn / lãi cao
    saved = round(abs(min_s["total_interest_ty"] - max_s["total_interest_ty"]), 2)

    tong_quan = (
        f"Kịch bản {min_s['label']}: trả góp thấp nhất {min_s['monthly_payment_m']:.1f} triệu/tháng "
        f"nhưng tổng lãi {min_s['total_interest_ty']:.2f} tỷ. "
        f"Kịch bản {max_s['label']}: trả góp {max_s['monthly_payment_m']:.1f} triệu/tháng "
        f"nhưng tiết kiệm {saved:.2f} tỷ tiền lãi. "
        f"LTV: {ltv}% — {ltv_label}."
    )

    return json.dumps({
        "chart_type": "horizontal_bar",
        "title": title,
        "x_label": "Kịch bản",
        "y_label": "Triệu VNĐ/tháng",
        "columns": ["Kịch bản", "Trả góp/tháng (triệu)"],
        "data": [[s["label"], s["monthly_payment_m"]] for s in scenarios],
        "tong_quan": tong_quan,
        "scenarios": scenarios,  # chỉ dùng nội bộ bởi Finance LLM
    }, ensure_ascii=False)
