from typing import Any

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.errors import RaiseException

from tests.helpers import TEST_DSN

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="Set a dedicated KESTRI_TEST_DATABASE_URL")
TABLES = ("checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes")


async def test_checkpoint_schema_preserves_legacy_tables(store: Any) -> None:
    assert (await store.one("SHOW search_path"))["search_path"] == "public"
    await AsyncPostgresSaver(store.pool).setup()
    before = await store.all("SELECT * FROM public.checkpoint_migrations ORDER BY v")
    for table in TABLES:
        await store.execute(f"ALTER TABLE public.{table} SET SCHEMA kestri")
    await store.open()
    assert await store.all("SELECT * FROM public.checkpoint_migrations ORDER BY v") == before
    for table in TABLES:
        assert (await store.one("SELECT to_regclass(%s) AS name", (f"kestri.{table}",)))[
            "name"
        ] is None


async def test_checkpoint_schema_conflict_preserves_both_copies(store: Any) -> None:
    await AsyncPostgresSaver(store.pool).setup()
    await store.execute("CREATE TABLE kestri.checkpoints (marker text)")
    await store.execute("INSERT INTO kestri.checkpoints VALUES ('keep')")
    with pytest.raises(RaiseException, match="CheckpointSchemaConflict"):
        await store.open()
    assert (await store.one("SELECT marker FROM kestri.checkpoints"))["marker"] == "keep"
    assert (await store.one("SELECT to_regclass('public.checkpoints') AS name"))["name"]
