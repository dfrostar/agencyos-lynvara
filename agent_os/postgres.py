"""PostgreSQL adapter for AgencyOS outreach/engagement/feedback.

Uses asyncpg connection pool pointing at cmmc20's existing PostgreSQL.
Mirrors the SQLite AgentOSStore interface but with async operations.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import asyncpg

log = logging.getLogger(__name__)

# ─── SQL for creating tables (idempotent — only if not already in cmmc20 DB) ───

OUTREACH_SCHEMA = """
CREATE TABLE IF NOT EXISTS outreach_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    company_name TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    phone TEXT,
    linkedin_url TEXT,
    naics_code TEXT,
    employee_count INTEGER,
    source TEXT DEFAULT 'manual',
    status TEXT DEFAULT 'identified',
    notes TEXT,
    assigned_to UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outreach_leads_tenant ON outreach_leads (tenant_id);
CREATE INDEX IF NOT EXISTS idx_outreach_leads_tenant_status ON outreach_leads (tenant_id, status);

CREATE TABLE IF NOT EXISTS outreach_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES outreach_leads(id) ON DELETE CASCADE,
    type TEXT DEFAULT 'note',
    direction TEXT DEFAULT 'outbound',
    subject TEXT,
    summary TEXT,
    next_follow_up TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outreach_activities_lead ON outreach_activities (lead_id);
"""

ENGAGEMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS engagements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    client_id UUID NOT NULL,
    name TEXT NOT NULL,
    type TEXT DEFAULT 'gap_assessment',
    target_cmmc_level TEXT DEFAULT 'L2_self',
    status TEXT DEFAULT 'active',
    start_date TIMESTAMPTZ,
    target_end_date TIMESTAMPTZ,
    actual_end_date TIMESTAMPTZ,
    engagement_owner TEXT,
    assigned_assessors JSONB DEFAULT '[]',
    coi_declared BOOLEAN DEFAULT false,
    nda_signed BOOLEAN DEFAULT false,
    msa_signed BOOLEAN DEFAULT false,
    sow_reference TEXT,
    billing_model TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_engagements_tenant ON engagements (tenant_id);
CREATE INDEX IF NOT EXISTS idx_engagements_client ON engagements (client_id);
CREATE INDEX IF NOT EXISTS idx_engagements_tenant_status ON engagements (tenant_id, status);

CREATE TABLE IF NOT EXISTS engagement_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    engagement_id UUID NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    author TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_engagement_notes_engagement ON engagement_notes (engagement_id);
"""

FEEDBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    skill_name TEXT NOT NULL,
    trigger_event TEXT NOT NULL,
    trigger_context TEXT NOT NULL,
    original_execution TEXT,
    user_correction TEXT,
    suggested_improvement TEXT NOT NULL,
    git_commit_sha TEXT,
    status TEXT DEFAULT 'pending',
    reviewed_by TEXT,
    applied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON skill_feedback (tenant_id);
CREATE INDEX IF NOT EXISTS idx_feedback_tenant_status ON skill_feedback (tenant_id, status);

CREATE TABLE IF NOT EXISTS knowledge_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    entry_type TEXT DEFAULT 'feedback',
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source_feedback_id UUID,
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_tenant ON knowledge_entries (tenant_id);
"""


async def init_schema(dsn: str) -> None:
    """Create tables if they don't exist. Idempotent."""
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(OUTREACH_SCHEMA)
        await conn.execute(ENGAGEMENT_SCHEMA)
        await conn.execute(FEEDBACK_SCHEMA)
        log.info("PostgreSQL schema initialized")
    finally:
        await conn.close()


class PostgresStore:
    """Async PostgreSQL store with connection pool.

    Replaces AgentOSStore for outreach/engagement/feedback.
    Handlers call methods via asyncio.get_event_loop().run_until_complete()
    or the sync wrapper methods.
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._dsn = os.environ.get("DATABASE_URL", "")

    async def connect(self) -> None:
        """Create connection pool."""
        if not self._dsn:
            raise RuntimeError("DATABASE_URL is required")
        self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        log.info("PostgreSQL pool created")

    async def close(self) -> None:
        """Close pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def ensure_schema(self) -> None:
        """Initialize schema on startup."""
        await init_schema(self._dsn)

    # ── sync wrappers for sync HTTP handlers ──

    def _run(self, coro: Any) -> Any:
        """Run async coroutine in event loop (for sync handlers)."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        return loop.run_until_complete(coro)

    # ── outreach leads ──

    def list_leads(self, tenant_id: str, status: str | None = None,
                   source: str | None = None, assigned_to: str | None = None) -> list[dict]:
        """List leads for tenant with optional filters."""
        query = "SELECT * FROM outreach_leads WHERE tenant_id = $1"
        args: list[Any] = [tenant_id]
        if status:
            query += f" AND status = ${len(args) + 1}"
            args.append(status)
        if source:
            query += f" AND source = ${len(args) + 1}"
            args.append(source)
        if assigned_to:
            query += f" AND assigned_to = ${len(args) + 1}"
            args.append(assigned_to)
        query += " ORDER BY updated_at DESC"
        return self._run(self._pool.fetch(query, *args))

    def get_lead(self, lead_id: str, tenant_id: str) -> dict | None:
        """Get single lead by id + tenant."""
        row = self._run(self._pool.fetchrow(
            "SELECT * FROM outreach_leads WHERE id = $1 AND tenant_id = $2",
            lead_id, tenant_id
        ))
        return dict(row) if row else None

    def create_lead(self, data: dict) -> dict:
        """Create a new lead. data keys match DB columns."""
        columns = list(data.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        values = [data[c] for c in columns]
        query = f"INSERT INTO outreach_leads ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING *"
        row = self._run(self._pool.fetchrow(query, *values))
        return dict(row) if row else {}

    def update_lead(self, lead_id: str, tenant_id: str, data: dict) -> bool:
        """Update lead fields. Returns True if row was found."""
        if not data:
            return False
        sets = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(data.keys()))
        values = list(data.values())
        query = f"UPDATE outreach_leads SET {sets}, updated_at = now() WHERE id = $1 AND tenant_id = $2"
        result = self._run(self._pool.execute(query, lead_id, tenant_id, *values))
        return result != "UPDATE 0"

    def delete_lead(self, lead_id: str, tenant_id: str) -> bool:
        """Delete lead (cascades to activities)."""
        result = self._run(self._pool.execute(
            "DELETE FROM outreach_leads WHERE id = $1 AND tenant_id = $2",
            lead_id, tenant_id
        ))
        return result != "DELETE 0"

    def list_activities(self, lead_id: str) -> list[dict]:
        """List activities for a lead."""
        rows = self._run(self._pool.fetch(
            "SELECT * FROM outreach_activities WHERE lead_id = $1 ORDER BY created_at DESC",
            lead_id
        ))
        return [dict(r) for r in rows]

    def create_activity(self, data: dict) -> dict:
        """Create activity. data: {lead_id, type, direction, subject?, summary?, next_follow_up?}."""
        columns = list(data.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        values = [data[c] for c in columns]
        query = f"INSERT INTO outreach_activities ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING *"
        row = self._run(self._pool.fetchrow(query, *values))
        return dict(row) if row else {}

    # ── stats ──

    def outreach_stats(self, tenant_id: str) -> dict[str, int]:
        """Count leads by status for tenant."""
        rows = self._run(self._pool.fetch(
            "SELECT status, COUNT(*)::int FROM outreach_leads WHERE tenant_id = $1 GROUP BY status",
            tenant_id
        ))
        return {r["status"]: r["count"] for r in rows}

    # ── engagements ──

    def list_engagements(self, tenant_id: str, client_id: str | None = None,
                         status: str | None = None) -> list[dict]:
        """List engagements for tenant."""
        query = "SELECT * FROM engagements WHERE tenant_id = $1"
        args: list[Any] = [tenant_id]
        if client_id:
            query += f" AND client_id = ${len(args) + 1}"
            args.append(client_id)
        if status:
            query += f" AND status = ${len(args) + 1}"
            args.append(status)
        query += " ORDER BY updated_at DESC"
        rows = self._run(self._pool.fetch(query, *args))
        return [dict(r) for r in rows]

    def get_engagement(self, eng_id: str, tenant_id: str) -> dict | None:
        """Get engagement with notes."""
        row = self._run(self._pool.fetchrow(
            "SELECT * FROM engagements WHERE id = $1 AND tenant_id = $2",
            eng_id, tenant_id
        ))
        if not row:
            return None
        eng = dict(row)
        notes = self._run(self._pool.fetch(
            "SELECT * FROM engagement_notes WHERE engagement_id = $1 ORDER BY created_at DESC",
            eng_id
        ))
        eng["notes"] = [dict(n) for n in notes]
        return eng

    def create_engagement(self, data: dict) -> dict:
        """Create engagement."""
        columns = list(data.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        values = [data[c] for c in columns]
        query = f"INSERT INTO engagements ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING *"
        row = self._run(self._pool.fetchrow(query, *values))
        return dict(row) if row else {}

    def update_engagement(self, eng_id: str, tenant_id: str, data: dict) -> bool:
        """Update engagement."""
        if not data:
            return False
        sets = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(data.keys()))
        values = list(data.values())
        query = f"UPDATE engagements SET {sets}, updated_at = now() WHERE id = $1 AND tenant_id = $2"
        result = self._run(self._pool.execute(query, eng_id, tenant_id, *values))
        return result != "UPDATE 0"

    def delete_engagement(self, eng_id: str, tenant_id: str) -> bool:
        """Delete engagement."""
        result = self._run(self._pool.execute(
            "DELETE FROM engagements WHERE id = $1 AND tenant_id = $2",
            eng_id, tenant_id
        ))
        return result != "DELETE 0"

    def list_notes(self, eng_id: str) -> list[dict]:
        """List notes for engagement."""
        rows = self._run(self._pool.fetch(
            "SELECT * FROM engagement_notes WHERE engagement_id = $1 ORDER BY created_at DESC",
            eng_id
        ))
        return [dict(r) for r in rows]

    def add_note(self, eng_id: str, content: str, author: str) -> dict:
        """Add note to engagement."""
        row = self._run(self._pool.fetchrow(
            "INSERT INTO engagement_notes (engagement_id, content, author) VALUES ($1, $2, $3) RETURNING *",
            eng_id, content, author
        ))
        return dict(row) if row else {}

    # ── feedback ──

    def list_feedback(self, tenant_id: str, status: str | None = None) -> list[dict]:
        """List feedback for tenant."""
        query = "SELECT * FROM skill_feedback WHERE tenant_id = $1"
        args: list[Any] = [tenant_id]
        if status:
            query += " AND status = $2"
            args.append(status)
        query += " ORDER BY created_at DESC"
        rows = self._run(self._pool.fetch(query, *args))
        return [dict(r) for r in rows]

    def get_feedback(self, fb_id: str, tenant_id: str) -> dict | None:
        """Get single feedback entry."""
        row = self._run(self._pool.fetchrow(
            "SELECT * FROM skill_feedback WHERE id = $1 AND tenant_id = $2",
            fb_id, tenant_id
        ))
        return dict(row) if row else None

    def create_feedback(self, data: dict) -> dict:
        """Create feedback entry."""
        columns = list(data.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        values = [data[c] for c in columns]
        query = f"INSERT INTO skill_feedback ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING *"
        row = self._run(self._pool.fetchrow(query, *values))
        return dict(row) if row else {}

    def update_feedback_status(self, fb_id: str, tenant_id: str, status: str,
                              reviewed_by: str | None = None) -> bool:
        """Update feedback status."""
        applied_at = "now()" if status == "applied" else "applied_at"
        query = f"UPDATE skill_feedback SET status = $1, reviewed_by = $2, applied_at = {applied_at}, updated_at = now() WHERE id = $3 AND tenant_id = $4"
        result = self._run(self._pool.execute(query, status, reviewed_by, fb_id, tenant_id))
        return result != "UPDATE 0"

    def feedback_stats(self, tenant_id: str) -> dict[str, int]:
        """Count feedback by status."""
        rows = self._run(self._pool.fetch(
            "SELECT status, COUNT(*)::int FROM skill_feedback WHERE tenant_id = $1 GROUP BY status",
            tenant_id
        ))
        return {r["status"]: r["count"] for r in rows}

    def create_knowledge_entry(self, data: dict) -> dict:
        """Create knowledge entry from applied feedback."""
        columns = list(data.keys())
        placeholders = [f"${i+1}" for i in range(len(columns))]
        values = [data[c] for c in columns]
        query = f"INSERT INTO knowledge_entries ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING *"
        row = self._run(self._pool.fetchrow(query, *values))
        return dict(row) if row else {}

    # ── digest ──

    def weekly_digest(self, tenant_id: str) -> list[dict]:
        """Get feedback from past 7 days."""
        rows = self._run(self._pool.fetch(
            """SELECT * FROM skill_feedback
               WHERE tenant_id = $1 AND created_at > now() - interval '7 days'
               ORDER BY created_at DESC""",
            tenant_id
        ))
        return [dict(r) for r in rows]
