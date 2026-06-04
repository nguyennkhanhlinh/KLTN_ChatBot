from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class HybridRateInput(BaseModel):
    equity: float = Field(description="Vốn tự có, đơn vị tỷ VNĐ")
    target_price: float = Field(description="Giá BĐS mục tiêu, đơn vị tỷ VNĐ")
    promo_rate: float = Field(description="Lãi suất ưu đãi (%/năm), ví dụ 8.5")
    promo_years: int = Field(description="Số năm được hưởng lãi suất ưu đãi, ví dụ 3")
    floating_rate: float = Field(description="Lãi suất thả nổi sau khi hết ưu đãi (%/năm), ví dụ 11.0")
    loan_term_years: int = Field(description="Tổng thời hạn vay (năm), ví dụ 25")
    monthly_income: Optional[float] = Field(
        default=None,
        description="Thu nhập ròng hàng tháng (triệu VNĐ). Dùng để đánh giá khả năng chi trả",
    )


def _pmt(principal_m: float, annual_rate_pct: float, n_months: int) -> float:
    r = (annual_rate_pct / 100) / 12
    return principal_m * r * (1 + r) ** n_months / ((1 + r) ** n_months - 1)


def _remaining_balance(principal_m: float, annual_rate_pct: float, pmt_m: float, n_paid: int) -> float:
    """Dư nợ còn lại sau n_paid tháng đã trả."""
    r = (annual_rate_pct / 100) / 12
    return principal_m * (1 + r) ** n_paid - pmt_m * ((1 + r) ** n_paid - 1) / r


@tool("calculate_hybrid_rate", args_schema=HybridRateInput)
def calculate_hybrid_rate(
    equity: float,
    target_price: float,
    promo_rate: float,
    promo_years: int,
    floating_rate: float,
    loan_term_years: int,
    monthly_income: Optional[float] = None,
) -> dict:
    """
    Tính kế hoạch tài chính với lãi suất hỗn hợp: giai đoạn ưu đãi (promo_rate) rồi thả nổi (floating_rate).
    Dùng khi ngân hàng áp dụng lãi suất ưu đãi N năm đầu, sau đó chuyển sang lãi suất thả nổi.
    """
    loan_ty = round(target_price - equity, 3)
    if loan_ty <= 0:
        return {"error": "Vốn tự có đã đủ để mua, không cần vay."}

    if promo_years >= loan_term_years:
        return {"error": f"promo_years ({promo_years}) phải nhỏ hơn loan_term_years ({loan_term_years})."}

    loan_m = loan_ty * 1000  # đổi sang triệu VNĐ

    ltv = round(loan_ty / target_price * 100, 1)
    ltv_level = "An toàn" if ltv <= 60 else ("Chấp nhận được" if ltv <= 70 else "Rủi ro cao")

    n_total = loan_term_years * 12
    n_promo = promo_years * 12
    n_float = (loan_term_years - promo_years) * 12

    # --- Giai đoạn ưu đãi ---
    # PMT tính theo promo_rate nhưng amortize trên toàn bộ thời hạn vay
    promo_pmt_m = _pmt(loan_m, promo_rate, n_total)

    # Dư nợ còn lại cuối giai đoạn ưu đãi
    bal_after_promo_m = _remaining_balance(loan_m, promo_rate, promo_pmt_m, n_promo)
    bal_after_promo_ty = round(bal_after_promo_m / 1000, 3)

    total_promo_paid_m = promo_pmt_m * n_promo
    principal_paid_promo_m = loan_m - bal_after_promo_m
    interest_promo_m = total_promo_paid_m - principal_paid_promo_m

    # --- Giai đoạn thả nổi ---
    # Re-amortize phần dư nợ còn lại theo floating_rate và số tháng còn lại
    float_pmt_m = _pmt(bal_after_promo_m, floating_rate, n_float)

    total_float_paid_m = float_pmt_m * n_float
    interest_float_m = total_float_paid_m - bal_after_promo_m

    total_interest_m = interest_promo_m + interest_float_m
    total_payment_m = loan_m + total_interest_m

    payment_jump_m = round(float_pmt_m - promo_pmt_m, 2)
    payment_jump_pct = round(payment_jump_m / promo_pmt_m * 100, 1)

    # --- So sánh với lãi suất cố định ---
    # Cố định promo_rate suốt kỳ: trả góp bằng promo_pmt_m nhưng ít lãi hơn
    fixed_promo_interest_m = promo_pmt_m * n_total - loan_m
    extra_vs_fixed_promo_m = total_interest_m - fixed_promo_interest_m

    # Cố định floating_rate suốt kỳ: trả góp cao hơn nhưng không hưởng ưu đãi
    fixed_float_pmt_m = _pmt(loan_m, floating_rate, n_total)
    fixed_float_interest_m = fixed_float_pmt_m * n_total - loan_m
    saving_vs_fixed_float_m = fixed_float_interest_m - total_interest_m

    # --- Cảnh báo ---
    canh_bao = []
    if payment_jump_pct >= 30:
        canh_bao.append(
            f"Trả góp tăng {payment_jump_pct:.0f}% sau khi hết ưu đãi "
            f"(từ {promo_pmt_m:.1f} → {float_pmt_m:.1f} triệu/tháng). "
            "Cần chuẩn bị tài chính cho giai đoạn thả nổi."
        )

    result = {
        "equity_ty": equity,
        "target_price_ty": target_price,
        "loan_ty": loan_ty,
        "ltv_pct": ltv,
        "ltv_level": ltv_level,
        "promo_period": {
            "rate_pct": promo_rate,
            "years": promo_years,
            "monthly_payment_m": round(promo_pmt_m, 2),
            "total_paid_m": round(total_promo_paid_m, 1),
            "interest_paid_ty": round(interest_promo_m / 1000, 3),
            "principal_paid_ty": round(principal_paid_promo_m / 1000, 3),
            "remaining_balance_ty": bal_after_promo_ty,
        },
        "floating_period": {
            "rate_pct": floating_rate,
            "years": loan_term_years - promo_years,
            "monthly_payment_m": round(float_pmt_m, 2),
            "total_paid_m": round(total_float_paid_m, 1),
            "interest_paid_ty": round(interest_float_m / 1000, 3),
        },
        "summary": {
            "loan_term_years": loan_term_years,
            "total_interest_ty": round(total_interest_m / 1000, 3),
            "total_payment_ty": round(total_payment_m / 1000, 3),
            "payment_jump_m": payment_jump_m,
            "payment_jump_pct": payment_jump_pct,
        },
        "vs_fixed_promo_rate": {
            "monthly_payment_m": round(promo_pmt_m, 2),
            "total_interest_ty": round(fixed_promo_interest_m / 1000, 3),
            "extra_interest_ty": round(extra_vs_fixed_promo_m / 1000, 3),
        },
        "vs_fixed_floating_rate": {
            "monthly_payment_m": round(fixed_float_pmt_m, 2),
            "total_interest_ty": round(fixed_float_interest_m / 1000, 3),
            "saving_ty": round(saving_vs_fixed_float_m / 1000, 3),
        },
        "extra_cost_min_ty": round(target_price * 0.08, 3),
        "extra_cost_max_ty": round(target_price * 0.10, 3),
    }

    if monthly_income is not None:
        promo_ratio = round(promo_pmt_m / monthly_income * 100, 1)
        float_ratio = round(float_pmt_m / monthly_income * 100, 1)
        result["affordability"] = {
            "monthly_income_m": monthly_income,
            "promo_payment_ratio_pct": promo_ratio,
            "floating_payment_ratio_pct": float_ratio,
            "promo_feasible": promo_ratio <= 40,
            "floating_feasible": float_ratio <= 40,
        }
        if float_ratio > 50:
            canh_bao.append(
                f"Sau ưu đãi, trả góp {float_pmt_m:.1f} triệu chiếm {float_ratio:.0f}% thu nhập. "
                "Vượt ngưỡng an toàn 40%, rủi ro tài chính cao."
            )

    result["canh_bao"] = " ".join(canh_bao) if canh_bao else "Không có cảnh báo đặc biệt."
    return result
