import json

import pytest

from src.tools.calculate_finance import calculate_finance
from src.tools.compare_loan_scenarios import compare_loan_scenarios
from src.tools.calculate_hybrid_rate import calculate_hybrid_rate


# calculate_finance
class TestCalculateFinance:
    def test_only_equity_no_income_no_target(self):
        r = calculate_finance.invoke({"equity": 2.0, "interest_rate": 9.0, "loan_term_years": 20})
        assert r["equity_ty"] == 2.0
        assert r["interest_rate_pct"] == 9.0
        assert r["loan_term_years"] == 20
        assert r["max_budget_ty"] is None          # không có thu nhập -> không tính ngân sách
        # chi phí phát sinh tính trên equity (base = equity)
        assert r["extra_cost_min_ty"] == round(2.0 * 0.08, 3)
        assert r["extra_cost_max_ty"] == round(2.0 * 0.10, 3)

    def test_with_monthly_income(self):
        r = calculate_finance.invoke({
            "equity": 2.0, "interest_rate": 9.0, "loan_term_years": 20, "monthly_income": 30.0,
        })
        assert r["pmt_max_m"] == round(30.0 * 0.40, 2)   # trả góp tối đa = 40% thu nhập
        assert r["max_loan_ty"] > 0
        assert r["max_budget_ty"] == pytest.approx(r["equity_ty"] + r["max_loan_ty"], abs=1e-6)

    def test_ltv_safe_boundary(self):
        # target=10, equity=4 -> loan=6 -> LTV=60% -> "An toàn"
        r = calculate_finance.invoke({
            "equity": 4.0, "interest_rate": 9.0, "loan_term_years": 20, "target_price": 10.0,
        })
        assert r["loan_needed_ty"] == 6.0
        assert r["ltv_pct"] == 60.0
        assert r["ltv_level"] == "An toàn"
        assert r["monthly_payment_m"] > 0

    def test_ltv_acceptable_boundary(self):
        # loan=7 -> LTV=70% -> "Chấp nhận được"
        r = calculate_finance.invoke({
            "equity": 3.0, "interest_rate": 9.0, "loan_term_years": 20, "target_price": 10.0,
        })
        assert r["ltv_pct"] == 70.0
        assert r["ltv_level"] == "Chấp nhận được"

    def test_ltv_high_risk(self):
        # loan=8 -> LTV=80% -> "Rủi ro cao"
        r = calculate_finance.invoke({
            "equity": 2.0, "interest_rate": 9.0, "loan_term_years": 20, "target_price": 10.0,
        })
        assert r["ltv_pct"] == 80.0
        assert r["ltv_level"] == "Rủi ro cao"

    def test_equity_covers_price(self):
        # equity >= target -> không cần vay
        r = calculate_finance.invoke({
            "equity": 12.0, "interest_rate": 9.0, "loan_term_years": 20, "target_price": 10.0,
        })
        assert r["loan_needed_ty"] == 0
        assert "monthly_payment_m" not in r

    def test_income_and_target_combined(self):
        r = calculate_finance.invoke({
            "equity": 3.0, "interest_rate": 10.0, "loan_term_years": 25,
            "monthly_income": 40.0, "target_price": 8.0,
        })
        assert "max_budget_ty" in r and r["max_budget_ty"] is not None
        assert "monthly_payment_m" in r
        assert r["extra_cost_min_ty"] == round(8.0 * 0.08, 3)  # base = target_price


# compare_loan_scenarios
class TestCompareLoanScenarios:
    def test_no_loan_needed(self):
        out = compare_loan_scenarios.invoke({"equity": 10.0, "target_price": 8.0})
        data = json.loads(out)
        assert "error" in data
        assert "không cần vay" in data["error"]

    def test_term_missing_rate(self):
        out = compare_loan_scenarios.invoke({
            "equity": 2.0, "target_price": 10.0, "compare_by": "term",
        })
        data = json.loads(out)
        assert "error" in data
        assert "interest_rate" in data["error"]

    def test_compare_by_term(self):
        out = compare_loan_scenarios.invoke({
            "equity": 2.0, "target_price": 10.0, "compare_by": "term", "interest_rate": 9.0,
        })
        data = json.loads(out)
        assert data["chart_type"] == "horizontal_bar"
        terms = [s["term_years"] for s in data["scenarios"]]
        assert terms == [10, 15, 20, 25, 30]
        # Thời hạn dài hơn -> trả góp/tháng thấp hơn nhưng tổng lãi cao hơn
        s10 = next(s for s in data["scenarios"] if s["term_years"] == 10)
        s30 = next(s for s in data["scenarios"] if s["term_years"] == 30)
        assert s30["monthly_payment_m"] < s10["monthly_payment_m"]
        assert s30["total_interest_ty"] > s10["total_interest_ty"]
        assert "LTV" in data["tong_quan"]

    def test_rate_missing_term(self):
        out = compare_loan_scenarios.invoke({
            "equity": 2.0, "target_price": 10.0, "compare_by": "rate",
        })
        data = json.loads(out)
        assert "error" in data
        assert "loan_term_years" in data["error"]

    def test_compare_by_rate_default(self):
        out = compare_loan_scenarios.invoke({
            "equity": 2.0, "target_price": 10.0, "compare_by": "rate", "loan_term_years": 20,
        })
        data = json.loads(out)
        rates = [s["rate_pct"] for s in data["scenarios"]]
        assert rates == [7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        # Lãi suất cao hơn -> trả góp/tháng cao hơn
        s7 = next(s for s in data["scenarios"] if s["rate_pct"] == 7.0)
        s12 = next(s for s in data["scenarios"] if s["rate_pct"] == 12.0)
        assert s12["monthly_payment_m"] > s7["monthly_payment_m"]

    def test_compare_by_rate_custom(self):
        out = compare_loan_scenarios.invoke({
            "equity": 2.0, "target_price": 10.0, "compare_by": "rate",
            "loan_term_years": 20, "custom_rates": [6.5, 7.5],
        })
        data = json.loads(out)
        assert [s["rate_pct"] for s in data["scenarios"]] == [6.5, 7.5]


# calculate_hybrid_rate
class TestCalculateHybridRate:
    _BASE = {
        "equity": 3.0, "target_price": 10.0,
        "promo_rate": 8.0, "promo_years": 3,
        "floating_rate": 12.0, "loan_term_years": 25,
    }

    def test_no_loan_needed(self):
        r = calculate_hybrid_rate.invoke({**self._BASE, "equity": 12.0})
        assert "error" in r
        assert "không cần vay" in r["error"]

    def test_promo_years_too_long(self):
        r = calculate_hybrid_rate.invoke({**self._BASE, "promo_years": 25})
        assert "error" in r
        assert "nhỏ hơn" in r["error"]

    def test_structure_and_ltv(self):
        r = calculate_hybrid_rate.invoke(self._BASE)
        # loan = 10 - 3 = 7 -> LTV 70% -> "Chấp nhận được"
        assert r["loan_ty"] == 7.0
        assert r["ltv_pct"] == 70.0
        assert r["ltv_level"] == "Chấp nhận được"
        for key in ("promo_period", "floating_period", "summary",
                    "vs_fixed_promo_rate", "vs_fixed_floating_rate", "canh_bao"):
            assert key in r

    def test_payment_jumps_after_promo(self):
        # floating_rate (12) > promo_rate (8) -> trả góp tăng sau ưu đãi
        r = calculate_hybrid_rate.invoke(self._BASE)
        assert r["floating_period"]["monthly_payment_m"] > r["promo_period"]["monthly_payment_m"]
        assert r["summary"]["payment_jump_m"] > 0
        assert r["summary"]["payment_jump_pct"] > 0

    def test_affordability_with_income(self):
        r = calculate_hybrid_rate.invoke({**self._BASE, "monthly_income": 50.0})
        aff = r["affordability"]
        assert aff["monthly_income_m"] == 50.0
        assert isinstance(aff["promo_feasible"], bool)
        assert isinstance(aff["floating_feasible"], bool)

    def test_no_affordability_without_income(self):
        r = calculate_hybrid_rate.invoke(self._BASE)
        assert "affordability" not in r
