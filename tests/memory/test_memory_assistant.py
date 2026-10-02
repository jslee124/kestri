"""Authority and presentation boundaries independent of provider behavior."""

import pytest

from kestri.integrations.telegram import authorized_callback
from kestri.memory.management import MemoryAction, MemoryManager, authorized, management_intent
from kestri.memory.presentation import html_text, presentation


@pytest.mark.parametrize(
    "text",
    [
        "你现在记住了我哪些事情？",
        "帮我开启自动记忆和语义检索。",
        "回答时先不要使用我的记忆",
        "为什么刚才觉得我喜欢清淡的菜？",
    ],
)
def test_management_routes(text: str) -> None:
    assert management_intent(text)


@pytest.mark.parametrize(
    "text",
    [
        "只依据有效记忆回答我的饮食偏好，不搜索。",
        "解释记忆的实现原理。",
        "如果我说开启自动记忆会发生什么？",
        "他说“开启自动记忆”。",
    ],
)
def test_research_and_untrusted_text_do_not_become_management(text: str) -> None:
    assert not management_intent(text)


def test_setting_proposal_requires_exact_named_current_authority() -> None:
    op = MemoryAction(action="set", evidence="开启自动记忆", setting="auto", enabled=True)
    assert authorized("请开启自动记忆。", op)
    assert not authorized("请关闭自动记忆。", op)
    assert not authorized("如果我说开启自动记忆。", op)
    assert not authorized("开启语义检索", op)
    assert not authorized("开启自动记忆", op.model_copy(update={"setting": "use"}))
    assert not authorized("开启自动记忆", op.model_copy(update={"enabled": False}))
    assert not authorized("我不想开启自动记忆", op)
    assert not authorized(
        "不要关闭自动记忆", op.model_copy(update={"evidence": "关闭自动记忆", "enabled": False})
    )


@pytest.mark.parametrize(
    ("text", "action"),
    [
        ("最近记住了什么？", "changes"),
        ("查看待确认记忆", "pending"),
        ("为什么刚才这样回答？", "why"),
        ("查看记忆设置", "settings"),
    ],
)
def test_read_navigation_selects_the_requested_view(text: str, action: str) -> None:
    plan = MemoryManager.read_plan(text)
    assert plan is not None
    assert plan.actions[0].action == action


def test_html_escaping_does_not_keep_private_body_in_metadata() -> None:
    assert (
        html_text("标题 <b>\n内容 & <script>") == "<b>标题 &lt;b&gt;</b>\n内容 &amp; &lt;script&gt;"
    )
    assert "text" not in presentation("私人正文")
    assert "inspect:12345678" not in str(presentation("回答编号：12345678\n编号：abcdef12"))
    assert "inspect:abcdef12" in str(presentation("  编号：abcdef12\n  编号：abcdef34"))
    assert "下一页" in str(presentation("下一页：/memory list 1"))


def test_callbacks_are_owner_private_and_allowlisted() -> None:
    update = {
        "update_id": 42,
        "callback_query": {
            "id": "callback",
            "data": "mem:list:1",
            "from": {"id": 111},
            "message": {
                "from": {"id": 999, "is_bot": True},
                "chat": {"id": 111, "type": "private"},
            },
        },
    }
    assert authorized_callback(update, 111)["text"] == "/memory list 1"
    assert authorized_callback(update, 222) is None
    update["callback_query"]["data"] = "mem:auto:on"
    assert authorized_callback(update, 111) is None
    update["callback_query"]["data"] = "mc:0123456789abcdef:2"
    assert authorized_callback(update, 111)["text"] == "选择记忆 0123456789abcdef 2"
    update["callback_query"]["message"]["chat"]["type"] = "group"
    assert authorized_callback(update, 111) is None
