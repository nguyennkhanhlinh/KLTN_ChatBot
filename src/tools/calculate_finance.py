import sys
import os
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class FinanceInput(BaseModel):
    interest_rate: float = Field(description="Lãi suất năm, %, ví dụ 9.0")
    loan_term_years: int = Field(description="Thời hạn vay, năm")
    equity: Optional[float] = Field(
        default=None,
        description="Vốn tự có, đơn vị tỷ VNĐ. None nếu user không cung cấp",
    )
    monthly_income: Optional[float] = Field(
        default=None,
        description="Thu nhập ròng hàng tháng, triệu VNĐ. None nếu user không cung cấp",
    )
    target_price: Optional[float] = Field(
        default=None,
        description="Giá BĐS mục tiêu, tỷ VNĐ. None nếu chưa biết",
    )
    loan_amount: Optional[float] = Field(
        default=None,
        description=(
            "Số tiền vay trực tiếp, tỷ VNĐ. Dùng khi user nói thẳng 'vay X tỷ' "
            "mà không qua (giá nhà - vốn). Ưu tiên hơn target_price khi tính trả góp."
        ),
    )


@tool("calculate_finance", args_schema=FinanceInput)
def calculate_finance(
    interest_rate: float,
    loan_term_years: int,
    equity: Optional[float] = None,
    monthly_income: Optional[float] = None,
    target_price: Optional[float] = None,
    loan_amount: Optional[float] = None,
) -> dict:
    """
    Tính toàn bộ kế hoạch tài chính mua BĐS.

    Khoản vay được xác định theo thứ tự ưu tiên:
    1. loan_amount (user nói thẳng "vay X tỷ") — chỉ cần lãi suất + thời hạn.
    2. target_price - equity (suy từ giá nhà và vốn tự có).
    LTV chỉ tính khi biết giá nhà (target_price).
    """
    # --- Guardrail: chặn đầu vào bất thường, báo lỗi rõ thay vì tính ra số sai ---
    if not (0 < interest_rate <= 50):
        return {"error": f"Lãi suất {interest_rate}%/năm có vẻ bất thường. "
                         "Nhập lãi suất theo %/năm (ví dụ 9.0)."}
    if not (1 <= loan_term_years <= 50):
        return {"error": f"Thời hạn vay {loan_term_years} năm có vẻ bất thường. "
                         "Nên trong khoảng 1–50 năm."}
    for _name, _val in (("equity", equity), ("target_price", target_price),
                        ("loan_amount", loan_amount), ("monthly_income", monthly_income)):
        if _val is not None and _val < 0:
            return {"error": f"Giá trị {_name} không được âm."}
    # Số tiền tính bằng TỶ mà quá lớn → có thể user nhầm đơn vị (triệu ↔ tỷ)
    for _name, _val in (("equity", equity), ("target_price", target_price),
                        ("loan_amount", loan_amount)):
        if _val is not None and _val > 1000:
            return {"error": f"{_name} = {_val} tỷ có vẻ quá lớn — bạn nhập đúng đơn vị 'tỷ' chưa?"}

    r = (interest_rate / 100) / 12  # lãi suất tháng
    n = loan_term_years * 12         # số tháng

    eq = equity or 0.0  # dùng cho số học khi user chưa cung cấp vốn

    result = {
        "equity_ty": equity,
        "interest_rate_pct": interest_rate,
        "loan_term_years": loan_term_years,
    }

    # Khoản vay tối đa từ thu nhập (annuity ngược)
    if monthly_income is not None:
        pmt_max = monthly_income * 0.40 # Số tiền trả góp tối đa
        factor = ((1 + r) ** n - 1) / (r * (1 + r) ** n) # Hệ số vay
        max_loan = pmt_max * factor / 1000  # triệu → tỷ # Khoản vay tối đa
        max_budget = eq + max_loan

        result.update({
            "monthly_income_m": monthly_income,
            "pmt_max_m": round(pmt_max, 2),
            "max_loan_ty": round(max_loan, 3),
            "max_budget_ty": round(max_budget, 3),
        })
    else:
        result["max_budget_ty"] = None

    # Số tiền vay: ưu tiên loan_amount, nếu không thì suy từ giá nhà − vốn
    if loan_amount is not None:
        loan = loan_amount
    elif target_price is not None:
        loan = target_price - eq
    else:
        loan = None

    # Trả góp (và LTV nếu biết giá nhà)
    if loan is not None:
        if loan > 0:
            monthly_pmt = loan * 1_000_000_000 * (r * (1 + r) ** n) / ((1 + r) ** n - 1) # số tiền trả góp mỗi tháng
            monthly_pmt_m = monthly_pmt / 1_000_000
            total_paid = monthly_pmt_m * n
            total_interest = total_paid - loan * 1000  # ra triệu

            result.update({
                "loan_needed_ty": round(loan, 3),
                "monthly_payment_m": round(monthly_pmt_m, 2),
                "total_interest_ty": round(total_interest / 1000, 3),
                "interest_to_principal_pct": round(total_interest / (loan * 1000) * 100, 1),
            })

            # LTV chỉ tính khi biết giá BĐS
            if target_price is not None:
                ltv = (loan / target_price) * 100

                if ltv <= 60:
                    ltv_level = "An toàn"
                elif ltv <= 70:
                    ltv_level = "Chấp nhận được"
                else:
                    ltv_level = "Rủi ro cao"

                result.update({
                    "target_price_ty": target_price,
                    "ltv_pct": round(ltv, 1),
                    "ltv_level": ltv_level,
                })
        else:
            result["loan_needed_ty"] = 0

    # Chi phí phát sinh
    base = target_price or loan_amount or result.get("max_budget_ty") or eq
    result["extra_cost_min_ty"] = round(base * 0.08, 3)
    result["extra_cost_max_ty"] = round(base * 0.10, 3)

    return result
