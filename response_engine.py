"""
response_engine.py
====================
Everything that calls the Anthropic API: raw completions, memory scoring
and reflection, bio extraction, and the two scenario-run functions
(individual reactions, group discussion turns).

Kept separate from agent_library.py (construction) and agent_validator.py
(consistency checks) so each file has exactly one job -- mirroring the
db.py / agent_library_v2.py / survey_response_engine.py split in
Social-Simulations-for-Survey-based-Research.
"""

import json
import time
import uuid

from anthropic import Anthropic

from agent_library import build_system_prompt

MODEL = "claude-sonnet-5"  # swap to a cheaper/faster model for quick iteration

client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

REFLECTION_THRESHOLD = 30  # cumulative importance before a reflection fires


# ---------------------------------------------------------------------------
# Raw API calls
# ---------------------------------------------------------------------------

def call_claude(system_prompt, messages, max_tokens=700, retries=2, temperature=None):
    """messages: list of {"role": "user"/"assistant", "content": str}
    temperature: 0.0-1.0, or None to use the API's own default. Passed
    per-call so each agent's own temperature setting genuinely affects
    every response generated on its behalf."""
    last_err = None
    for attempt in range(retries + 1):
        try:
            kwargs = dict(
                model=MODEL,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )
            if temperature is not None:
                kwargs["temperature"] = temperature
            response = client.messages.create(**kwargs)
            return "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Claude API call failed after retries: {last_err}")


def _parse_reasoning_stance(raw):
    """Expects JSON like {"reasoning": "...", "stance": "..."}.
    Falls back gracefully if the model didn't comply."""
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(cleaned)
        return {
            "reasoning": parsed.get("reasoning", "").strip(),
            "stance": parsed.get("stance", "").strip() or cleaned,
        }
    except (json.JSONDecodeError, AttributeError):
        return {"reasoning": "", "stance": raw.strip()}


def extract_bio_fields(bio_text):
    """Extract grounded (factual) fields from a pasted bio. Deliberately does
    NOT infer demographics or cognitive traits."""
    system = """Extract structured biographical facts from professional bio or profile \
text. Return ONLY valid JSON, no markdown fences, no preamble, no commentary -- just the \
JSON object, with exactly this shape:
{"background": "...", "expertise": "...", "outcomes": "...", "values": "..."}
Base every field only on what is explicitly stated or very directly implied by the text. \
Do not invent achievements, traits, or psychology. If a field cannot be reasonably filled \
from the text, leave it as an empty string."""
    raw = call_claude(system, [{"role": "user", "content": bio_text}], max_tokens=400)
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Memory stream (Park et al., 2023) -- the pieces that need the API
# ---------------------------------------------------------------------------

def _score_importance(text):
    system = ("On a scale of 1 to 10, where 1 is purely mundane and 10 is extremely "
              "poignant or decision-relevant, rate the likely importance of the "
              "following memory for a startup founder. Reply with ONLY the integer.")
    try:
        raw = call_claude(system, [{"role": "user", "content": text}], max_tokens=5)
        return max(1, min(10, int("".join(ch for ch in raw if ch.isdigit()) or "5")))
    except Exception:  # noqa: BLE001
        return 5


def add_memory(agent, text, mtype="observation", importance=None):
    if importance is None:
        importance = _score_importance(text)
    agent["memory"].append({
        "id": uuid.uuid4().hex[:8],
        "text": text,
        "type": mtype,
        "importance": importance,
        "turn": len(agent["memory"]),
    })
    return agent["memory"][-1]


def maybe_reflect(agent):
    memory = agent["memory"]
    recent = memory[agent["last_reflection_index"]:]
    if not recent:
        return None
    cumulative_importance = sum(m["importance"] for m in recent)
    if cumulative_importance < REFLECTION_THRESHOLD:
        return None

    numbered = "\n".join(f"{i+1}. {m['text']}" for i, m in enumerate(recent))
    system = (f"You are synthesizing memories for {agent['name']}, a startup founder. "
              "Given the numbered statements below, what is the single most salient "
              "high-level insight you can infer about this founder's situation, "
              "beliefs, or trajectory? Respond in one sentence, and cite which "
              "statement numbers support it, like: 'insight text (because of 2, 4).'")
    try:
        reflection_text = call_claude(system, [{"role": "user", "content": numbered}], max_tokens=150)
    except Exception:  # noqa: BLE001
        return None

    agent["last_reflection_index"] = len(memory)
    return add_memory(agent, reflection_text, mtype="reflection")


# ---------------------------------------------------------------------------
# Scenario runs
# ---------------------------------------------------------------------------

def react_individually(agent, scenario):
    system = build_system_prompt(agent)
    user_msg = f"""FEEDBACK EVENT:
{scenario}

What's your reaction to this?"""
    raw = call_claude(system, [{"role": "user", "content": user_msg}], temperature=agent.get("temperature"))
    result = _parse_reasoning_stance(raw)

    add_memory(
        agent,
        f"Reacted to feedback ('{scenario[:80]}...'): said '{result['stance']}' "
        f"(privately thought: {result['reasoning']})",
        mtype="observation",
    )
    maybe_reflect(agent)
    return result


def react_in_group_turn(agent, scenario, transcript):
    """transcript: list of {"name": str, "stance": str} -- reasoning is private
    and never shown to other agents, only to the researcher afterward."""
    system = build_system_prompt(agent)
    transcript_text = (
        "\n".join(f"{t['name']}: {t['stance']}" for t in transcript)
        if transcript
        else "No one has spoken yet."
    )
    user_msg = f"""FEEDBACK EVENT:
{scenario}

Discussion so far (you only hear what people said out loud, not their private thoughts):
{transcript_text}

It's your turn. Say whatever you'd actually say -- could be one line, could be more."""
    raw = call_claude(system, [{"role": "user", "content": user_msg}], temperature=agent.get("temperature"))
    result = _parse_reasoning_stance(raw)

    add_memory(
        agent,
        f"In group discussion about '{scenario[:60]}...', said: '{result['stance']}' "
        f"(privately thought: {result['reasoning']})",
        mtype="observation",
    )
    maybe_reflect(agent)
    return result
