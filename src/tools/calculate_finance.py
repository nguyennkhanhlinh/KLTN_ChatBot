import sys
import os
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class FinanceInput(BaseModel):
    equity: float = Field(description="Vốn tự có, đơn vị tỷ VNĐ")
    interest_rate: float = Field(description="Lãi suất năm, %, ví dụ 9.0")
    loan_term_years: int = Field(description="Thời hạn vay, năm")
    monthly_income: Optional[float] = Field(
        default=None,
        description="Thu nhập ròng hàng tháng, triệu VNĐ. None nếu user không cung cấp",
    )
    target_price: Optional[float] = Field(
        default=None,
        description="Giá BĐS mục tiêu, tỷ VNĐ. None nếu chưa biết",
    )


@tool("calculate_finance", args_schema=FinanceInput)
def calculate_finance(
    equity: float,
    interest_rate: float,
    loan_term_years: int,
    monthly_income: Optional[float] = None,
    target_price: Optional[float] = None,
) -> dict:
    """
    Tính toàn bộ kế hoạch tài chính mua BĐS.
    """
    r = (interest_rate / 100) / 12  # lãi suất tháng
    n = loan_term_years * 12         # số tháng

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
        max_budget = equity + max_loan

        result.update({
            "monthly_income_m": monthly_income,
            "pmt_max_m": round(pmt_max, 2),
            "max_loan_ty": round(max_loan, 3),
            "max_budget_ty": round(max_budget, 3),
        })
    else:
        result["max_budget_ty"] = None

    # Trả góp và LTV theo giá mục tiêu
    if target_price is not None:
        loan = target_price - equity # số tiền cần va
        if loan > 0:
            monthly_pmt = loan * 1_000_000_000 * (r * (1 + r) ** n) / ((1 + r) ** n - 1) # số tiền trả góp mỗi tháng
            monthly_pmt_m = monthly_pmt / 1_000_000 
            total_paid = monthly_pmt_m * n
            total_interest = total_paid - loan * 1000  # ra triệu
            ltv = (loan / target_price) * 100 

            if ltv <= 60:
                ltv_level = "An toàn"
            elif ltv <= 70:
                ltv_level = "Chấp nhận được"
            else:
                ltv_level = "Rủi ro cao"

            result.update({
                "target_price_ty": target_price,
                "loan_needed_ty": round(loan, 3),
                "monthly_payment_m": round(monthly_pmt_m, 2),
                "total_interest_ty": round(total_interest / 1000, 3),
                "interest_to_principal_pct": round(total_interest / (loan * 1000) * 100, 1),
                "ltv_pct": round(ltv, 1),
                "ltv_level": ltv_level,
            })
        else:
            result["loan_needed_ty"] = 0

    # Chi phí phát sinh
    base = target_price or result.get("max_budget_ty") or equity
    result["extra_cost_min_ty"] = round(base * 0.08, 3)
    result["extra_cost_max_ty"] = round(base * 0.10, 3)

    return result
