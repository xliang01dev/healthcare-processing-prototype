import asyncpg
from typing import Any, cast


class DataProvider:
    """
    Base Postgres access layer backed by two asyncpg connection pools.

    reader_dsn  — credentials for a read-only role (SELECT only)
    writer_dsn  — credentials for a read-write role (INSERT / UPDATE / DELETE)

    In this project both DSNs share the same host; in prod the reader DSN
    would point to a read replica (except MPI, which has no replica).
    """

    def __init__(
        self,
        reader_dsn: str,
        writer_dsn: str,
        pool_min_size: int = 2,
        pool_max_size: int = 5,
    ) -> None:
        if not reader_dsn:
            raise ValueError("DataProvider requires a reader DSN — set POSTGRES_READER_* env vars")
        if not writer_dsn:
            raise ValueError("DataProvider requires a writer DSN — set POSTGRES_WRITER_* env vars")
        self._reader_dsn = reader_dsn
        self._writer_dsn = writer_dsn
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._reader: asyncpg.Pool | None = None
        self._writer: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._reader = await asyncpg.create_pool(
            self._reader_dsn,
            min_size=self._pool_min_size,
            max_size=self._pool_max_size,
        )
        self._writer = await asyncpg.create_pool(
            self._writer_dsn,
            min_size=self._pool_min_size,
            max_size=self._pool_max_size,
        )

    async def disconnect(self) -> None:
        if self._reader is not None:
            await self._reader.close()
        if self._writer is not None:
            await self._writer.close()

    # ------------------------------------------------------------------
    # Reader helpers — always route through the read-only pool
    # ------------------------------------------------------------------

    async def fetch(self, sql: str, *args: Any) -> list[asyncpg.Record] | None:
        assert self._reader is not None, "DataProvider not connected — call connect() first"
        return await self._reader.fetch(sql, *args)

    async def fetchrow(self, sql: str, *args: Any) -> asyncpg.Record | None:
        assert self._reader is not None, "DataProvider not connected — call connect() first"
        return await self._reader.fetchrow(sql, *args)

    # ------------------------------------------------------------------
    # Writer helpers — always route through the read-write pool
    # ------------------------------------------------------------------

    async def execute(self, sql: str, *args: Any) -> Any:
        assert self._writer is not None, "DataProvider not connected — call connect() first"
        return await self._writer.execute(sql, *args)

    async def executemany(self, sql: str, args_seq: Any) -> None:
        assert self._writer is not None, "DataProvider not connected — call connect() first"
        await self._writer.executemany(sql, args_seq)
