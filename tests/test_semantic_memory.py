from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from kestri.memory_embedding import content_hash, embedding_space
from kestri.memory_retriever import (
    MemorySelection,
    bounded_query,
    lexical_rank,
    lexical_terms,
    reciprocal_rank_fusion,
)

from .helpers import research_settings


def record(content: str) -> dict:
    return {"id": uuid4(), "content": content, "created_at": datetime.now(UTC)}


def test_chinese_overlapping_terms_and_no_zero_match_padding() -> None:
    assert {"智能", "能体", "体工", "工程"} <= lexical_terms("智能体工程")
    assert "agent" in lexical_terms("ＡＧＥＮＴ development")
    assert "这个" not in lexical_terms("这个项目")
    facts = [record("我学习智能体工程"), record("晚上喜欢吃面条")]
    assert lexical_rank(facts, "体工程能力") == [facts[0]]
    assert lexical_rank(facts, "量子物理") == []


def test_rrf_combines_duplicates_deterministically() -> None:
    a, b, c = record("a"), record("b"), record("c")
    fused = reciprocal_rank_fusion([a, b], [b, c])
    assert fused[0] == b and len(fused) == 3


def test_query_bounded_in_bytes_and_characters() -> None:
    query = bounded_query("中文" * 4000, [HumanMessage(content="old dialogue")] * 4)
    assert len(query) <= 4000 and len(query.encode()) <= 8192
    assert query.startswith("中文")


def test_spaces_include_endpoint_recipe_and_dimension() -> None:
    settings = research_settings(
        DASHSCOPE_API_KEY="embedding-test-only",
        embedding_base_url="https://test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    )
    config = settings.embedding_config()
    assert config is not None
    assert embedding_space(config) != embedding_space(
        config.model_copy(update={"embedding_dimensions": 512})
    )
    assert content_hash("中文事实") == content_hash("中文事实")
    assert content_hash("中文事实") != content_hash("changed")
    with pytest.raises(ValidationError):
        research_settings(embedding_dimensions=512)
    with pytest.raises(ValidationError):
        MemorySelection(ids=[uuid4()] * 2)
