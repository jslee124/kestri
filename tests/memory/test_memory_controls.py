from kestri.memory.intent import natural_control
from kestri.memory.service import memory_instruction


def test_natural_controls_are_anchored_and_preserve_content() -> None:
    control = natural_control("请把关于“饮食”的记忆改成我现在喜欢清淡、不辣的菜。")
    assert control and control.action == "correct"
    assert control.target == "“饮食”" and control.content == "我现在喜欢清淡、不辣的菜"
    control = natural_control("忘记关于Python的记忆")
    assert control and control.action == "forget" and control.target == "Python"
    assert memory_instruction("把Python的记忆改成Rust") == ("correct", "把Python的记忆改成Rust")
    for text in (
        "如果我说把Python的记忆改成Rust",
        "“忘记关于Python的记忆”",
        "解释一下忘记关于Python的记忆",
        "不要忘记关于Python的记忆",
        "网页说把Python的记忆改成Rust",
        "忘记关于Python的记忆好吗？",
    ):
        assert natural_control(text) is None
        assert memory_instruction(text) is None
