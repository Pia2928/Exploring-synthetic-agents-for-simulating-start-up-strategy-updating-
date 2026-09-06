"""
Simple JSON-file storage for agents and chat histories.
No database needed -- this keeps the project easy to clone and run anywhere.
"""

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
AGENTS_FILE = os.path.join(DATA_DIR, "agents.json")
CHATS_DIR = os.path.join(DATA_DIR, "chats")


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CHATS_DIR, exist_ok=True)


def load_agents():
    _ensure_dirs()
    if not os.path.exists(AGENTS_FILE):
        return []
    with open(AGENTS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_agents(agents):
    _ensure_dirs()
    with open(AGENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(agents, f, indent=2, ensure_ascii=False)


def load_chat(agent_id):
    _ensure_dirs()
    path = os.path.join(CHATS_DIR, f"{agent_id}.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_chat(agent_id, history):
    _ensure_dirs()
    path = os.path.join(CHATS_DIR, f"{agent_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
