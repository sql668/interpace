"""T5.4 回归测试：题库 JSON 契约的解析容错与模板可渲染性。

全是纯函数测试，不连数据库、不打网络。
"""

import sys
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

# 将项目根目录加入导入路径，避免在不同虚拟环境下出现 `No module named 'app'`。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.prompt_template_seed_service import (  # noqa: E402
    QUIZ_GENERATE_TEMPLATE,
)
from app.services.quiz_service import (  # noqa: E402
    DIFFICULTY_LEVELS,
    QuizPayload,
    parse_quiz_evaluation,
    parse_quiz_payload,
)

CLEAN_JSON = (
    '{"target_job": "Python 后端", "difficulty": "中级", "question_count": 2, '
    '"questions": ['
    '{"question": "什么是 GIL？", "reference_answer": "全局解释器锁"},'
    '{"question": "索引失效的常见原因？", "reference_answer": "函数包裹列"}'
    "]}"
)


def test_clean_json_parses() -> None:
    payload = parse_quiz_payload(CLEAN_JSON)
    assert isinstance(payload, QuizPayload)
    assert payload.target_job == "Python 后端"
    assert payload.difficulty == "中级"
    assert payload.question_count == 2
    assert payload.questions[0].question == "什么是 GIL？"
    assert payload.questions[0].reference_answer == "全局解释器锁"


def test_markdown_code_fence_is_stripped() -> None:
    text = f"```json\n{CLEAN_JSON}\n```"
    payload = parse_quiz_payload(text)
    assert payload is not None
    assert payload.question_count == 2


def test_bare_code_fence_is_stripped() -> None:
    payload = parse_quiz_payload(f"```\n{CLEAN_JSON}\n```")
    assert payload is not None
    assert payload.question_count == 2


def test_surrounding_prose_is_tolerated() -> None:
    text = f"好的，这是为你准备的题目：\n{CLEAN_JSON}\n祝练习顺利！"
    payload = parse_quiz_payload(text)
    assert payload is not None
    assert payload.question_count == 2


def test_blank_text_returns_none() -> None:
    assert parse_quiz_payload("") is None
    assert parse_quiz_payload("   \n  ") is None


def test_invalid_json_returns_none() -> None:
    assert parse_quiz_payload("{不是合法 JSON") is None
    assert parse_quiz_payload('{"questions": [}') is None


def test_no_json_object_returns_none() -> None:
    assert parse_quiz_payload("请先确认参数，确认后我再出题。") is None


def test_json_array_is_rejected() -> None:
    assert parse_quiz_payload('[{"question": "x", "reference_answer": "y"}]') is None


def test_empty_questions_list_returns_none() -> None:
    assert parse_quiz_payload('{"questions": []}') is None


def test_all_blank_questions_return_none() -> None:
    text = '{"questions": [{"question": ""}, {"question": "   "}]}'
    assert parse_quiz_payload(text) is None


def test_blank_questions_are_dropped_but_valid_kept() -> None:
    text = (
        '{"questions": ['
        '{"question": "", "reference_answer": "x"},'
        '{"question": "有效题干", "reference_answer": "答案"}'
        "]}"
    )
    payload = parse_quiz_payload(text)
    assert payload is not None
    assert payload.question_count == 1
    assert payload.questions[0].question == "有效题干"


def test_non_dict_question_items_are_skipped() -> None:
    text = '{"questions": ["字符串条目", 42, {"question": "有效题干"}]}'
    payload = parse_quiz_payload(text)
    assert payload is not None
    assert payload.question_count == 1


def test_missing_reference_answer_is_tolerated() -> None:
    text = '{"questions": [{"question": "只有题干"}]}'
    payload = parse_quiz_payload(text)
    assert payload is not None
    assert payload.questions[0].reference_answer is None


def test_question_count_trusts_actual_list_length() -> None:
    """模型自报 question_count=5 但只给了 2 道，以实际列表长度为准。"""
    text = (
        '{"question_count": 5, "questions": ['
        '{"question": "第一题"}, {"question": "第二题"}]}'
    )
    payload = parse_quiz_payload(text)
    assert payload is not None
    assert payload.question_count == 2


def test_unexpected_difficulty_is_kept_as_is() -> None:
    text = '{"difficulty": "地狱级", "questions": [{"question": "题干"}]}'
    payload = parse_quiz_payload(text)
    assert payload is not None
    assert payload.difficulty == "地狱级"
    assert "地狱级" not in DIFFICULTY_LEVELS


def test_text_fields_are_stripped() -> None:
    text = (
        '{"target_job": "  Python 后端  ", "difficulty": " 高级 ", '
        '"questions": [{"question": " 题干 ", "reference_answer": " 答案 "}]}'
    )
    payload = parse_quiz_payload(text)
    assert payload is not None
    assert payload.target_job == "Python 后端"
    assert payload.difficulty == "高级"
    assert payload.questions[0].question == "题干"
    assert payload.questions[0].reference_answer == "答案"


def test_missing_optional_fields_are_none() -> None:
    payload = parse_quiz_payload('{"questions": [{"question": "题干"}]}')
    assert payload is not None
    assert payload.target_job is None
    assert payload.difficulty is None


def test_quiz_template_renders_into_chat_prompt_template() -> None:
    """刷题模板里的 JSON 示例必须已转义，否则 ChatPromptTemplate 会抛 KeyError。"""
    prompt = ChatPromptTemplate.from_messages(
        [("system", QUIZ_GENERATE_TEMPLATE), ("human", "{user_input}")]
    )
    rendered = prompt.format(user_input="我想练 Python 后端的题")
    # 双写花括号渲染后应还原成单个花括号的 JSON 结构
    assert '"questions"' in rendered
    assert "{{" not in rendered


EVALUATION_JSON = (
    '{"total_score": 60, "weak_topics": ["GIL", "索引失效"], '
    '"questions": ['
    '{"order_index": 1, "score": 40, "analysis": "只说了名字"},'
    '{"order_index": 2, "score": 80, "analysis": "思路对"}'
    "]}"
)


def test_clean_evaluation_parses() -> None:
    evaluation = parse_quiz_evaluation(EVALUATION_JSON)
    assert evaluation is not None
    assert evaluation.total_score == 60
    assert evaluation.weak_topics == ["GIL", "索引失效"]
    assert [q.order_index for q in evaluation.questions] == [1, 2]
    assert [q.score for q in evaluation.questions] == [40, 80]


def test_evaluation_tolerates_code_fence_and_prose() -> None:
    text = f"批改如下：\n```json\n{EVALUATION_JSON}\n```\n希望有帮助。"
    evaluation = parse_quiz_evaluation(text)
    assert evaluation is not None
    assert evaluation.total_score == 60


def test_evaluation_blank_returns_none() -> None:
    assert parse_quiz_evaluation("") is None
    assert parse_quiz_evaluation("   ") is None


def test_evaluation_invalid_json_returns_none() -> None:
    assert parse_quiz_evaluation("不是 JSON") is None
    assert parse_quiz_evaluation("[1, 2, 3]") is None
    assert parse_quiz_evaluation('{"weak_topics": []}') is None


def test_evaluation_score_is_clamped_and_rounded() -> None:
    text = (
        '{"total_score": 120, "weak_topics": ["A"], '
        '"questions": [{"order_index": 1, "score": -5}, '
        '{"order_index": 2, "score": 79.6, "analysis": "  "}]}'
    )
    evaluation = parse_quiz_evaluation(text)
    assert evaluation is not None
    assert evaluation.total_score == 100  # 越界收敛到 0-100
    assert evaluation.questions[0].score == 0
    assert evaluation.questions[1].score == 80
    # 只有空白的解析文本归一成 None，而不是留下空字符串
    assert evaluation.questions[1].analysis is None


def test_evaluation_dedupes_weak_topics() -> None:
    text = '{"weak_topics": ["GIL", "GIL", " 索引 ", ""], "questions": []}'
    evaluation = parse_quiz_evaluation(text)
    assert evaluation is not None
    assert evaluation.weak_topics == ["GIL", "索引"]


def test_evaluation_skips_items_without_valid_order_index() -> None:
    text = (
        '{"questions": ['
        '{"score": 10}, {"order_index": "x", "score": 20},'
        '{"order_index": 0, "score": 30}, {"order_index": 4, "score": 40}'
        "]}"
    )
    evaluation = parse_quiz_evaluation(text)
    assert evaluation is not None
    assert [q.order_index for q in evaluation.questions] == [4]
