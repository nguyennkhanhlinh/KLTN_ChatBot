import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langchain.agents import create_agent

from src.llm.llm_client import OpenAIClient
from src.tools.calculate_finance import calculate_finance
from src.tools.compare_loan_scenarios import compare_loan_scenarios
from src.tools.calculate_hybrid_rate import calculate_hybrid_rate
from src.tools.calculator import add, subtract, multiply, divide
from src.prompts.Finance_prompt import FINANCE_PROMPT


_REASONING_MODELS = frozenset({"o4-mini"})
_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def create_finance_agent(model: str = _DEFAULT_MODEL):
    temperature = 1 if model in _REASONING_MODELS else 0
    llm = OpenAIClient(model=model, temperature=temperature)

   
    return create_agent(
        model=llm,
        tools=[calculate_finance, compare_loan_scenarios, calculate_hybrid_rate, add, subtract, multiply, divide],
        system_prompt=FINANCE_PROMPT,
        name="Finance_Agent",
    )
