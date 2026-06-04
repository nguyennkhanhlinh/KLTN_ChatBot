"""
LLM-as-Judge evaluators — 4 chỉ số chất lượng, thang 1-5.
"""

import json
import os
import time

from langsmith.schemas import Run, Example
from langchain_openai import ChatOpenAI

_JUDGE_MODEL = os.getenv("JUDGE_MODEL", "gpt-4.1")
_MAX_RETRIES = 5

_judge = ChatOpenAI(
    model=_JUDGE_MODEL,
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
)


_BASE = """Bạn là chuyên gia đánh giá độc lập chất lượng chatbot tư vấn Bất động sản Hà Nội.

Hệ thống gồm 3 agent chuyên biệt:
- Finance Agent       : tính toán tài chính (PMT, LTV, so sánh kịch bản vay, lãi suất hỗn hợp)
- Analyst Agent       : thống kê, phân tích dữ liệu (SQL), vẽ biểu đồ
- Recommendation Agent: tìm và liệt kê tin đăng BĐS cụ thể

CÂU HỎI NGƯỜI DÙNG:
{question}

DỮ LIỆU HỆ THỐNG TRUY XUẤT ĐƯỢC (tool outputs):
{tool_outputs}

CÂU TRẢ LỜI CỦA HỆ THỐNG:
{response}

TIÊU CHÍ ĐÁNH GIÁ:
{criteria}

HƯỚNG DẪN CHẤM ĐIỂM:
- Chỉ dùng điểm nguyên từ 1 đến 5.
- Đọc kỹ bảng tiêu chí và đối chiếu với câu trả lời thực tế.
- Nếu tool outputs rỗng: chấm dựa trên câu trả lời và câu hỏi.
- Lý do phải cụ thể, chỉ rõ điểm đạt/chưa đạt.

Trả về JSON duy nhất, không có text nào khác:
{{"score": <số nguyên 1-5>, "reason": "<1-2 câu giải thích cụ thể>"}}"""


_GROUNDEDNESS = """TÍNH CĂN CỨ DỮ LIỆU (STRICT) — Mức độ bám sát dữ liệu truy xuất

5 — Toàn bộ thông tin có căn cứ trong tool outputs; không thêm bất kỳ
    nhận xét hay số liệu nào ngoài dữ liệu truy xuất.
4 — Tất cả số liệu cứng có căn cứ; có tối đa 1 nhận xét định tính nhỏ
    không gây hiểu nhầm về kết quả.
3 — Có đúng 1 vi phạm CỨNG; phần còn lại bám sát dữ liệu.
2 — Có từ 2 vi phạm CỨNG trở lên, hoặc 1 thông tin sai làm thay đổi kết quả.
1 — Câu trả lời bịa đặt số liệu hoặc gần như không dựa trên dữ liệu truy xuất."""

_RELEVANCE = """TÍNH LIÊN QUAN (LENIENT) — Mức độ phù hợp với yêu cầu người dùng

Bảng điểm:
5 — Trả lời đúng và đầy đủ trọng tâm câu hỏi.
4 — Trả lời đúng trọng tâm; có thể có thông tin thêm hoặc một phần nhỏ lệch
    nhưng không ảnh hưởng đến giá trị câu trả lời.
3 — Trả lời được phần cốt lõi nhưng bỏ sót hoặc lệch một phần quan trọng
    trong yêu cầu của người dùng.
2 — Chỉ trả lời được phần nhỏ của yêu cầu; phần lớn câu hỏi bị bỏ qua.
1 — Câu trả lời lạc đề hoàn toàn, không giải quyết được bất kỳ phần nào."""

_COMPLETENESS = """TÍNH ĐẦY ĐỦ (MAXIMUM LENIENT) — Mức độ đầy đủ của câu trả lời

Bảng điểm:
5 — Trả lời đầy đủ yêu cầu cốt lõi.
4 — Giải quyết được yêu cầu chính; mọi thiếu sót đều là ý phụ không ảnh hưởng
    đến khả năng người dùng hiểu kết quả và ra quyết định.
3 — Yêu cầu chính được trả lời nhưng còn thiếu thông tin quan trọng khiến
    người dùng chưa thể hành động ngay mà cần hỏi thêm.
2 — Yêu cầu chính chưa được trả lời rõ ràng; câu trả lời chỉ đề cập sơ qua.
1 — Không giải quyết được yêu cầu nào của người dùng."""

_CLARITY = """TÍNH RÕ RÀNG (STRICT) — Mức độ rõ ràng và dễ hiểu

Bảng điểm:
5 — Cấu trúc rõ ràng, có tiêu đề/bullet phân tách hợp lý; TẤT CẢ số liệu có đơn vị;
    người dùng đọc một lần hiểu ngay kết quả chính.
4 — Cấu trúc tốt; tất cả số liệu cứng (giá, PMT, diện tích) có đơn vị;
    chỉ thiếu đơn vị ở con số phụ không ảnh hưởng đến quyết định.
3 — Thiếu đơn vị ở ít nhất 1 số liệu quan trọng, HOẶC cấu trúc trình bày chưa nhất quán.
2 — Thiếu đơn vị ở nhiều số liệu; các thông tin bị trộn lẫn, khó theo dõi.
1 — Câu trả lời rất khó đọc hoặc gần như không thể hiểu được."""


def _extract_io(run: Run, example: Example) -> tuple[str, str, str]:
    question = example.inputs.get("question", "")
    tool_outputs = json.dumps(
        run.outputs.get("tool_outputs", {}), ensure_ascii=False, indent=2
    )
    response = run.outputs.get("response", "")
    return question, tool_outputs, response


def _judge_score(question: str, tool_outputs: str, response: str, criteria: str) -> dict:
    prompt = _BASE.format(
        question=question,
        tool_outputs=tool_outputs,
        response=response,
        criteria=criteria,
    )
    for attempt in range(_MAX_RETRIES):
        try:
            raw = _judge.invoke(prompt).content.strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            parsed = json.loads(raw[start:end])
            score = max(1, min(5, int(parsed["score"])))
            return {"score": score / 5.0, "comment": parsed.get("reason", "")}
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                wait = 2 ** attempt
                print(f"[judge] RateLimit, wait {wait}s ({attempt + 1}/{_MAX_RETRIES})")
                time.sleep(wait)
            elif attempt == _MAX_RETRIES - 1:
                raise
            else:
                time.sleep(1)
    return {"score": 0.6, "comment": "judge failed after retries"}

# 4 Evaluators 
def eval_groundedness(run: Run, example: Example) -> dict:
    question, tool_outputs, response = _extract_io(run, example)
    result = _judge_score(question, tool_outputs, response, _GROUNDEDNESS)
    return {"key": "groundedness", **result}


def eval_relevance(run: Run, example: Example) -> dict:
    question, tool_outputs, response = _extract_io(run, example)
    result = _judge_score(question, tool_outputs, response, _RELEVANCE)
    return {"key": "relevance", **result}


def eval_completeness(run: Run, example: Example) -> dict:
    question, tool_outputs, response = _extract_io(run, example)
    result = _judge_score(question, tool_outputs, response, _COMPLETENESS)
    return {"key": "completeness", **result}


def eval_clarity(run: Run, example: Example) -> dict:
    question, tool_outputs, response = _extract_io(run, example)
    result = _judge_score(question, tool_outputs, response, _CLARITY)
    return {"key": "clarity", **result}


ALL_EVALUATORS = [eval_groundedness, eval_relevance, eval_completeness, eval_clarity]
