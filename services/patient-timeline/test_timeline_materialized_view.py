"""
Integration test for timeline materialized view refresh.
Tests that the materialized view can be refreshed both initially and concurrently.
"""
import asyncio
import asyncpg
import os
from uuid import uuid4
from datetime import datetime, timezone

async def test_refresh_materialized_view_on_empty_view():
    """
    Test that we can refresh a materialized view even when it's initially empty.

    This test reproduces the bug where REFRESH MATERIALIZED VIEW CONCURRENTLY
    fails on an unpopulated view. The fix is to do an initial non-concurrent
    refresh before using CONCURRENTLY.
    """
    # Connection setup
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("POSTGRES_WRITER_USER", "hs_writer")
    password = os.getenv("POSTGRES_WRITER_PASSWORD", "hs_writer")
    db = os.getenv("POSTGRES_DB", "healthcare")

    conn = await asyncpg.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=db
    )

    try:
        # Insert a timeline event
        canonical_patient_id = str(uuid4())
        now = datetime.now(timezone.utc)
        await conn.execute("""
            INSERT INTO patient_timeline.timeline_events (
                canonical_patient_id,
                event_log_ids,
                event_processing_start,
                event_processing_end,
                clinical_notes,
                resolution_log
            ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
        canonical_patient_id,
        [1, 2, 3],
        now,
        now,
        "Test clinical notes",
        "Test resolution log"
        )

        # The schema initialization (init_tables.sql) includes REFRESH MATERIALIZED VIEW
        # so the view is already populated. Now CONCURRENTLY refresh should work.
        # If init_tables.sql doesn't have the REFRESH, this will fail with FeatureNotSupportedError.
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY patient_timeline.patient_timeline")

        # Verify the view contains the inserted data
        row = await conn.fetchrow(
            "SELECT canonical_patient_id FROM patient_timeline.patient_timeline WHERE canonical_patient_id = $1",
            canonical_patient_id
        )
        assert row is not None, "Materialized view should contain the inserted patient event"
        assert row['canonical_patient_id'] == canonical_patient_id

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_refresh_materialized_view_on_empty_view())
    print("✓ Test passed")
