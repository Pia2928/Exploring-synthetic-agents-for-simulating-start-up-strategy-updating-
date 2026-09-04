"""
Agent model + persona construction + Claude API calls.

Design note: each agent keeps two clearly separate layers —
  - "grounded": facts extracted or known about a real founder (background,
    expertise, prior outcomes, stated values). Treat this as data, not
    inference.
  - "assigned": experimental cognitive-tendency dials (risk tolerance,
    confirmation bias, group dominance, optimism) that YOU set for the
    simulation. These are not read off a LinkedIn profile — they're
    variables you're testing.
"""

import time
import uuid

from anthropic import Anthropic

# Pick any current model string. Sonnet is a good default balance of
# quality and cost; swap to a cheaper/faster model for quick iteration.
MODEL = "claude-sonnet-5"

client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment


def new_agent(name, background="", expertise="", outcomes="", values="",
              risk=5, bias=5, dominance=5, optimism=5, note=""):
    return {
        "id": uuid.uuid4().hex[:10],
        "name": name,
        "grounded": {
            "background": background,
            "expertise": expertise,
            "outcomes": outcomes,
            "values": values,
        },
        "assigned": {
            "risk": risk,
            "bias": bias,
            "dominance": dominance,
            "optimism": optimism,
            "note": note,
        },
    }


def build_system_prompt(agent):
    g = agent["grounded"]
    a = agent["assigned"]
    note_line = f"Additional note: {a['note']}" if a.get("note") else ""
    return f"""You are roleplaying {agent['name']}, a startup co-founder, inside a research \
simulation exploring how founders cognitively process early feedback. Stay fully in \
character. Do not mention that you are an AI, a simulation, or break character in any way.

GROUNDED IDENTITY (who this person is):
Background: {g.get('background') or 'not specified'}
Domain expertise: {g.get('expertise') or 'not specified'}
Prior outcomes: {g.get('outcomes') or 'not specified'}
Stated values / voice: {g.get('values') or 'not specified'}

ASSIGNED COGNITIVE TENDENCIES (how you process information — experimental settings, \
not fixed facts about the real person):
Risk tolerance: {a['risk']}/10
Confirmation bias: {a['bias']}/10 (higher means you more readily interpret ambiguous \
information as confirming what you already believed or planned)
Group dominance: {a['dominance']}/10 (higher means you speak more assertively and are \
more likely to steer or talk over others)
Optimism: {a['optimism']}/10
{note_line}

Let these tendencies visibly shape your reasoning rather than just your tone. A \
high-confirmation-bias founder should visibly reframe unwelcome information rather than \
just react to it. A low-risk-tolerance founder should surface downside scenarios early. \
Speak in first person, in a natural founder voice, not as a report."""


def call_claude(system_prompt, messages, max_tokens=600, retries=2):
    """messages: list of {"role": "user"/"assistant", "content": str}"""
    last_err = None
    for attempt in range(retries + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )
            return "".join(
                block.text for block in response.content if block.type == "text"
            ).strip()
        except Exception as e:  # noqa: BLE001 - surface any API error to the caller
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Claude API call failed after retries: {last_err}")


def extract_bio_fields(bio_text):
    """Use Claude to pull grounded fields out of raw bio/profile text.
    Returns a dict with background/expertise/outcomes/values, or raises on failure.
    """
    import json

    system = """Extract structured biographical facts from professional bio or profile \
text. Return ONLY valid JSON, no markdown fences, no preamble, no commentary — just the \
JSON object, with exactly this shape:
{"background": "...", "expertise": "...", "outcomes": "...", "values": "..."}
Base every field only on what is explicitly stated or very directly implied by the text. \
Do not invent achievements, traits, or psychology. If a field cannot be reasonably filled \
from the text, leave it as an empty string."""
    raw = call_claude(system, [{"role": "user", "content": bio_text}], max_tokens=400)
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(cleaned)


def react_individually(agent, scenario):
    system = build_system_prompt(agent)
    user_msg = f"""FEEDBACK EVENT:
{scenario}

Give your first reaction as {agent['name']}. Structure your answer in two short parts:
1. Interpretation — what you think this feedback actually means, and any reasoning move \
you notice yourself making (e.g. dismissing it, over-weighting it, looking for a silver \
lining, wanting more data before deciding).
2. Proposed next step — what you think the team should do.
Keep it under 150 words total, in first person, natural voice."""
    return call_claude(system, [{"role": "user", "content": user_msg}])


def react_in_group_turn(agent, scenario, transcript):
    system = build_system_prompt(agent)
    transcript_text = (
        "\n".join(f"{t['name']}: {t['text']}" for t in transcript)
        if transcript
        else "No one has spoken yet."
    )
    user_msg = f"""FEEDBACK EVENT:
{scenario}

Discussion so far:
{transcript_text}

It's your turn to respond as {agent['name']}. React naturally to what's been said (or to \
the feedback directly if you're first to speak). Keep it conversational and under 100 \
words. Contribute one turn only — do not summarize the whole discussion."""
    return call_claude(system, [{"role": "user", "content": user_msg}])
