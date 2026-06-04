import sys
import os
import json
import re
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import before_model
from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime
from dotenv import load_dotenv

load_dotenv()

from src.llm.llm_client import OpenAIClient
from src.memory.short_memory import get_checkpointer, MAX_USER_TURNS
from src.memory.long_memory import update_user_preferences, update_user_profile, get_store
from src.prompts.Supervisor_prompt import SUPERVISOR_PROMPT
from src.agents.Analyst_agent import create_analyst_agent
from src.agents.Finance_agent import create_finance_agent
from src.agents.Recommendation_Agent import create_Recommendation_agent
from src.utils.chart_labels_loader import load_chart_labels
from src.tools.execute_sql import execute_sql as _sql_tool


@dataclass
class Context:
    user_id: str


_REASONING_MODELS = frozenset({"o4-mini"})
_DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


@before_model
def _trim_history(state: AgentState, runtime: Runtime):
    """Giữ tối đa MAX_USER_TURNS lượt hội thoại gần nhất trước mỗi lần gọi LLM."""
    messages = state["messages"]
    human_indices = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    if len(human_indices) <= MAX_USER_TURNS:
        return None
    cutoff = human_indices[-MAX_USER_TURNS]
    kept = messages[cutoff:]
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *kept]}

_supervisor_cache: dict = {}
_sentinel = object()  # default marker for checkpointer param


_CHART_KEYWORDS = frozenset({"biểu đồ", "chart", "vẽ", "pie", "visualize", "trực quan", "histogram"})


# Các trường số trong danh sách BĐS mà giá trị 0/NAN/NULL/rỗng = không có thông tin.
_NOINFO_FIELDS = ("Giá/m²", "Giá", "Diện tích", "Số phòng ngủ", "Số phòng tắm")
_NOINFO_LINE_RE = re.compile(
    r"^(\s*-\s*(?:" + "|".join(re.escape(f) for f in _NOINFO_FIELDS) + r"):\s*)(.+)$"
)


def _clean_no_info(text: str) -> str:
    """Chuẩn hóa các trường số trong danh sách BĐS: 0/NAN/NULL/rỗng → "Không rõ".

    Phòng khi LLM không tự áp dụng quy tắc này (model nhẹ hay bỏ sót).
    """
    def _fix(line: str) -> str:
        m = _NOINFO_LINE_RE.match(line)
        if not m:
            return line
        prefix, value = m.group(1), m.group(2).strip()
        num = value.split()[0] if value else ""  # tách số khỏi đơn vị (tỷ, m², ...)
        if value.upper() in ("NAN", "NULL", "") or num in ("0", "0.0", "0,0"):
            return prefix + "Không rõ"
        return line

    return "\n".join(_fix(l) for l in text.split("\n"))


def build_supervisor(model: str = _DEFAULT_MODEL, checkpointer=_sentinel):
    """Tạo supervisor agent với 3 subagents là tools. Kết quả được cache theo model.

    checkpointer: truyền vào để override (vd MemorySaver cho eval).
                  Mặc định dùng get_checkpointer() (AsyncPostgresSaver).
    """
    use_default_cp = checkpointer is _sentinel
    if use_default_cp and model in _supervisor_cache:
        return _supervisor_cache[model]

    analyst = create_analyst_agent(model=model)
    finance = create_finance_agent(model=model)
    recommendation = create_Recommendation_agent(model=model)

    _chart_labels = load_chart_labels()

    @tool("analyst_agent")
    async def call_analyst(query: str) -> str:
        """Thống kê số liệu BĐS Hà Nội, phân tích dữ liệu, vẽ biểu đồ.
        Dùng cho: số lượng, giá trung bình, ranking quận, phân bố, xu hướng, biểu đồ."""
        is_chart = any(kw in query.lower() for kw in _CHART_KEYWORDS)
        agent_query = f"{query}\n\nYêu cầu output_format: \"json\"" if is_chart else query

        result = await analyst.ainvoke({"messages": [HumanMessage(content=agent_query)]})
        content = result["messages"][-1].content

        if not is_chart:
            return content

        # Bước 1: final response đã là JSON chart hợp lệ → dùng ngay
        try:
            parsed = json.loads(content)
            if "chart_type" in parsed:
                return content
        except (json.JSONDecodeError, TypeError):
            pass

        # Bước 2: tìm SQL từ tool_calls trong AIMessages rồi tự re-execute với json
        sql_data = None
        sql_query = None
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("name") == "execute_sql":
                        sql_query = tc.get("args", {}).get("sql_query", "")
        # Dùng SQL cuối cùng analyst viết (loop trên không break → lấy cái sau cùng)

        if sql_query:
            raw = _sql_tool.invoke({"sql_query": sql_query, "output_format": "json"})
            try:
                data = json.loads(raw)
                if "columns" in data and "data" in data:
                    sql_data = data
            except (json.JSONDecodeError, TypeError):
                pass

        if sql_data is None:
            return content  # không lấy được data, trả text

        # Bước 3: gọi LLM riêng để format chart JSON từ sql_data
        llm = OpenAIClient(model=model, temperature=0)
        format_msg = (
            f"Query: {query}\n\n"
            f"Dữ liệu SQL:\n{json.dumps(sql_data, ensure_ascii=False)}\n\n"
            f"Chart labels:\n{_chart_labels}\n\n"
            "Trả về JSON hợp lệ duy nhất, không có text nào khác:\n"
            '{"chart_type":"bar|line|pie|scatter|horizontal_bar|histogram|stacked_bar",'
            '"title":"Biểu đồ <y_label> theo <x_label>",'
            '"x_label":"...","y_label":"...","columns":[...],"data":[...],'
            '"tong_quan":"1-2 câu nhận định từ dữ liệu (so sánh, outlier, xu hướng)."}'
        )
        formatted = llm.invoke([HumanMessage(content=format_msg)]).content.strip()

        # Validate kết quả
        try:
            parsed = json.loads(formatted)
            if "chart_type" in parsed:
                return formatted
        except (json.JSONDecodeError, TypeError):
            pass

        # Regex fallback nếu LLM vẫn wrap JSON trong text
        match = re.search(r'\{[\s\S]*"chart_type"[\s\S]*\}', formatted)
        if match:
            try:
                json.loads(match.group())
                return match.group()
            except (json.JSONDecodeError, TypeError):
                pass

        return content

    @tool("finance_agent")
    async def call_finance(query: str) -> str:
        """Tư vấn tài chính mua BĐS: tính khả năng vay, trả góp, LTV, so sánh kịch bản vay.
        Dùng khi user cung cấp: vốn tự có, thu nhập, lãi suất, thời hạn vay, giá BĐS."""
        result = await finance.ainvoke({"messages": [HumanMessage(content=query)]})

        # Nếu Finance agent dùng compare_loan_scenarios → pass-through chart JSON lên supervisor
        for msg in result["messages"]:
            if getattr(msg, "name", "") == "compare_loan_scenarios":
                try:
                    data = json.loads(msg.content)
                    if "chart_type" in data and "columns" in data and "data" in data:
                        chart = {k: v for k, v in data.items() if k != "scenarios"}
                        return json.dumps(chart, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Trích xuất max_budget_ty từ kết quả calculate_finance để supervisor dùng routing
        max_budget = None
        for msg in result["messages"]:
            if getattr(msg, "name", "") == "calculate_finance":
                try:
                    data = json.loads(msg.content)
                    if isinstance(data, dict) and data.get("max_budget_ty") is not None:
                        max_budget = data["max_budget_ty"]
                except (json.JSONDecodeError, TypeError):
                    pass

        text = result["messages"][-1].content
        if max_budget is not None:
            text += f"\n\n[MAX_BUDGET_TY={max_budget}]"
        return text

    @tool("recommendation_agent")
    async def call_recommendation(query: str) -> str:
        """Tìm và liệt kê tin đăng BĐS cụ thể theo điều kiện lọc.
        Dùng khi user muốn xem căn hộ/nhà theo quận, giá, diện tích, tiện ích."""
        result = await recommendation.ainvoke({"messages": [HumanMessage(content=query)]})
        return _clean_no_info(result["messages"][-1].content)

    @tool("recall_memory")
    async def recall_memory_tool(query: str, runtime: ToolRuntime[Context]) -> str:
        """Truy vấn thông tin đã biết về user từ các cuộc hội thoại trước.
        Gọi tool này khi cần biết: ngân sách, quận ưa thích, loại BĐS, số phòng ngủ,
        thu nhập, tiết kiệm, thành viên gia đình, hoặc bất kỳ thông tin cá nhân nào.
        Truyền query mô tả thông tin cần tìm, ví dụ: "ngân sách và quận ưa thích"."""
        if runtime.store is None:
            return "Memory chưa sẵn sàng."
        user_id = runtime.context.user_id
        memories = await runtime.store.asearch(("users", user_id), query=query, limit=3)
        if not memories:
            return "Chưa có thông tin về user này."
        parts: list[str] = []
        for mem in memories:
            val = mem.value
            score = getattr(mem, "score", None)
            score_str = f" (relevance: {score:.2f})" if score is not None else ""
            rules = val.get("rules", []) if isinstance(val, dict) else []
            if rules:
                parts.append(f"[{mem.key}]{score_str}")
                for rule in reversed(rules):
                    parts.append(f"  - {rule}")
            else:
                parts.append(f"[{mem.key}]{score_str}: {val}")
        return "\n".join(parts)

    @tool("save_preferences")
    async def save_preferences_tool(rules: list[str], *, runtime: ToolRuntime[Context]) -> str:
        """Lưu sở thích bất động sản của user vào long-term memory.
        CHỈ gọi khi user cung cấp thông tin mới chưa được lưu: ngân sách, quận/phường,
        loại BĐS, số phòng ngủ, diện tích, mục đích mua, tiêu chí bắt buộc hoặc điều không chấp nhận.
        KHÔNG gọi nếu user không đề cập thông tin cá nhân mới.
        Truyền list các câu mô tả ngắn gọn bằng tiếng Việt.
        Ví dụ: ["Muốn mua nhà ở Cầu Giấy", "Cần 3 phòng ngủ", "Ngân sách tối đa 5 tỷ"]"""
        user_id = runtime.context.user_id if runtime.context else None
        if not user_id or not rules:
            return "skip: no data"
        await update_user_preferences(user_id, rules)
        return f"Đã lưu sở thích BĐS: {rules}"

    @tool("save_profile")
    async def save_profile_tool(rules: list[str], *, runtime: ToolRuntime[Context]) -> str:
        """Lưu hồ sơ tài chính và cá nhân của user vào long-term memory.
        CHỈ gọi khi user cung cấp thông tin mới chưa được lưu: thu nhập, tiết kiệm/vốn tự có,
        số thành viên gia đình, nghề nghiệp, khoản nợ, khả năng trả góp, có muốn vay không.
        KHÔNG gọi nếu user không đề cập thông tin tài chính mới.
        Truyền list các câu mô tả ngắn gọn bằng tiếng Việt.
        Ví dụ: ["Thu nhập 40 triệu/tháng", "Tiết kiệm 1.5 tỷ", "Gia đình 4 người"]"""
        user_id = runtime.context.user_id if runtime.context else None
        if not user_id or not rules:
            return "skip: no data"
        await update_user_profile(user_id, rules)
        return f"Đã lưu hồ sơ user: {rules}"

    temperature = 1 if model in _REASONING_MODELS else 0
    llm = OpenAIClient(model=model, temperature=temperature)

    actual_checkpointer = get_checkpointer() if use_default_cp else checkpointer

    supervisor = create_agent(
        model=llm,
        tools=[call_analyst, call_finance, call_recommendation, recall_memory_tool, save_preferences_tool, save_profile_tool],
        system_prompt=SUPERVISOR_PROMPT,
        name="Supervisor",
        checkpointer=actual_checkpointer,
        store=get_store(),
        context_schema=Context,
        middleware=[_trim_history],
    )

    if use_default_cp:
        _supervisor_cache[model] = supervisor
    return supervisor


if __name__ == "__main__":
    import asyncio
    from src.memory.short_memory import init_checkpointer, close_checkpointer

    async def _main():
        await init_checkpointer()
        try:
            app = build_supervisor()
            config = {"configurable": {"thread_id": "test"}}

            questions = [
                "Giá trung bình BĐS theo quận tại Hà Nội?",
                
            ]

            for q in questions:
                print(f"\n{'='*60}\nQ: {q}\n{'='*60}")
                result = await app.ainvoke(
                    {"messages": [HumanMessage(content=q)]}, config
                )
                print(result["messages"][-1].content)
        finally:
            await close_checkpointer()

    asyncio.run(_main())
