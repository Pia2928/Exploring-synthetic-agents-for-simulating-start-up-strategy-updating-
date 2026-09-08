"""
storage.py
===========
Persistence layer, backed by Supabase (Postgres) instead of local JSON
files. Every function keeps the EXACT same name and signature as the
original file-based version, so nothing in app.py, main.py, agent_library.py,
agent_validator.py, or response_engine.py needs to change -- swapping the
backend was the entire point of keeping persistence isolated in one module.

REQUIRED SETUP (one-time, on your Supabase project)
-------------------------------------------------------
1. Create a project at https://supabase.com.
2. In the SQL Editor, run:

    create table agents (
      id text primary key,
      name text not null,
      demographics jsonb default '{}'::jsonb,
      grounded jsonb default '{}'::jsonb,
      alignment_strategy text default 'visionary',
      founder_identity jsonb default '{}'::jsonb,
      assigned jsonb default '{}'::jsonb,
      memory jsonb default '[]'::jsonb,
      last_reflection_index integer default 0,
      validation_warnings jsonb default '[]'::jsonb,
      updated_at timestamptz default now()
    );

    create table chats (
      agent_id text primary key references agents(id) on delete cascade,
      history jsonb default '[]'::jsonb,
      updated_at timestamptz default now()
    );

3. In Project Settings -> API, copy the Project URL and the `service_role`
   secret key (NOT the `anon` key -- service_role bypasses row-level
   security, which is what you want for a single-user local tool with no
   separate auth layer; anon would need RLS policies configured to allow
   read/write at all). Treat this key exactly like ANTHROPIC_API_KEY: never
   commit it, never put it in client-side code -- it only ever lives in this
   server-side process's environment.
4. Set both as environment variables before running the app:
     export SUPABASE_URL=https://xxxxx.supabase.co
     export SUPABASE_KEY=your-service-role-key
"""

import os

from supabase import Client, create_client

_SUPABASE_URL = os.environ.get("SUPABASE_URL")
_SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

_client: Client = None


def _get_client() -> Client:
    global _client
    if _client is None:
        if not _SUPABASE_URL or not _SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must both be set as environment "
                "variables before running the app. See the setup notes at the "
                "top of storage.py."
            )
        _client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    return _client


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

def load_agents():
    """Returns the full agent list, shaped exactly like the old JSON-file
    version: a list of agent dicts with 'memory' as a plain Python list."""
    res = _get_client().table("agents").select("*").execute()
    return res.data or []


def save_agents(agents):
    """Reconciles the DB table with the given list, matching the old
    JSON-file semantics where the caller always passes the FULL current
    list (after appending, mutating, or filtering it) and the file becomes
    that list verbatim. Here: upsert everything present, then delete any
    row not present in the given list (handles the delete-an-agent case,
    since app.py calls this with the already-filtered list)."""
    client = _get_client()

    if not agents:
        # Empty list means "delete everything" -- mirrors overwriting the
        # JSON file with an empty array.
        client.table("agents").delete().neq("id", "").execute()
        return

    client.table("agents").upsert(agents).execute()

    existing = client.table("agents").select("id").execute().data or []
    existing_ids = {row["id"] for row in existing}
    keep_ids = {a["id"] for a in agents}
    to_delete = list(existing_ids - keep_ids)
    if to_delete:
        client.table("agents").delete().in_("id", to_delete).execute()


# ---------------------------------------------------------------------------
# Chat histories
# ---------------------------------------------------------------------------

def load_chat(agent_id):
    res = _get_client().table("chats").select("history").eq("agent_id", agent_id).execute()
    if res.data:
        return res.data[0]["history"]
    return []


def save_chat(agent_id, history):
    _get_client().table("chats").upsert({"agent_id": agent_id, "history": history}).execute()
