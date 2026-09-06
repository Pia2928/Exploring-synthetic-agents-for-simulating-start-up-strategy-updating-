"""
Agent model, persona construction, memory/reflection substrate, and Claude API calls.

TWO-PIECE PROMPT ARCHITECTURE
------------------------------
Every agent's system prompt is assembled from exactly two pieces, kept
deliberately separate in code:

  1. QUALITIES  (render_qualities_block, below) -- everything that makes
     THIS agent different from any other: demographics, grounded facts,
     alignment strategy, founder identity blend, assigned cognitive dials,
     and retrieved memories. This is the only part that varies per agent.

  2. UNIVERSAL INSTRUCTIONS  (imported from universal_instructions.py) --
     the same verbatim behavioural rules appended to every agent, governing
     HOW a persona behaves in an interview (terse or not, hedging or not,
     willing to be blunt, wrong, or incomplete) as opposed to WHO it is.

build_system_prompt() is the only place these two pieces are joined. Each
agent is still created individually, one at a time, through new_agent() --
this split is about prompt composition, not batching.

THEORY LAYERS INSIDE THE QUALITIES BLOCK
------------------------------------------
- demographics       : baseline age/gender/region/education/socioeconomic
                        background, so agents don't default to whatever the
                        model's implicit "typical founder" looks like.
- grounded            : real background info (career, expertise, prior
                        outcomes, stated values).
- alignment_strategy  : Zellweger & Djokovic (2026) -- Visionary / Engineer /
                        Experimenter. Each mitigates two of four uncertainty
                        types and is structurally blind to the other two.
- founder_identity    : Fauchart & Gruber / Sieger et al. -- Missionary /
                        Darwinian / Communitarian, as a blend, not a category.
- assigned            : cognitive dials (risk, confirmation bias, dominance,
                        optimism) that modulate how the above gets expressed.
- memory stream       : (Park et al., 2023) every scenario reaction and group
                        turn logged with an importance score; retrieval pulls
                        back the most important/recent memories; periodic
                        reflection synthesizes recent memories into a
                        higher-level self-statement, citing what it drew on.

Every scenario response is logged as two fields (Csaszar et al., 2026 --
reasoning before the forced choice): private "reasoning" and public
"stance". In group turns, other agents only ever see each other's stance.
"""

import json
import time
import uuid

from anthropic import Anthropic

from universal_instructions import UNIVERSAL_INSTRUCTIONS

MODEL = "claude-sonnet-5"  # swap to a cheaper/faster model for quick iteration

client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment

MEMORY_DECAY = 0.90          # per-turn recency decay
REFLECTION_THRESHOLD = 30    # cumulative importance before a reflection fires


# ---------------------------------------------------------------------------
# Theory-grounded reference tables
# ---------------------------------------------------------------------------

ALIGNMENT_STRATEGIES = {
    "visionary": {
        "label": "Visionary",
        "focus": "idea-environment alignment",
        "question": "What is a valuable new idea?",
        "mitigates": "state uncertainty (what is actually going on in the market) "
                     "and perception uncertainty (how to read ambiguous signals)",
        "blind_spot": "execution uncertainty (whether the idea can actually be built) "
                      "and effect uncertainty (whether it will actually sell). "
                      "You should show a tendency to under-focus on feasibility and "
                      "concrete market feedback in favor of the bigger picture.",
    },
    "engineer": {
        "label": "Engineer",
        "focus": "idea-action alignment",
        "question": "Can we build it?",
        "mitigates": "perception uncertainty (within your specific technical domain) "
                     "and execution uncertainty (feasibility)",
        "blind_spot": "state uncertainty (the broader market environment) and effect "
                      "uncertainty (how the market will actually respond). You should "
                      "show a tendency toward false confidence from internal technical "
                      "coherence -- if the engineering is solid, you may under-question "
                      "whether the market wants it at all.",
    },
    "experimenter": {
        "label": "Experimenter",
        "focus": "action-environment alignment",
        "question": "Will this sell?",
        "mitigates": "execution uncertainty (whatever ships gets tested) and effect "
                     "uncertainty (rapid market feedback)",
        "blind_spot": "state uncertainty (broader market/technology trends) and "
                      "perception uncertainty (deeper interpretation of *why* something "
                      "works). You should show a tendency toward short-termism and "
                      "over-reacting to the most recent piece of feedback, at the "
                      "expense of a coherent longer-term read of the market.",
    },
}

FOUNDER_IDENTITY_DESCRIPTIONS = {
    "missionary": "believes the firm exists to change society for the better; "
                  "self-evaluates through the firm's contribution to a social cause "
                  "beyond the business itself",
    "darwinian": "believes the firm exists to win competitively and generate wealth; "
                 "takes a professional, self-interested, 'business school' approach "
                 "and treats other players primarily as rivals",
    "communitarian": "believes the firm exists to serve a specific community the "
                      "founder personally belongs to (not distant society, not pure "
                      "self-interest) -- loyalty and reciprocity toward that known "
                      "group of people is the primary motivator",
}


# ---------------------------------------------------------------------------
# Agent construction -- each agent is created individually via this function
# ---------------------------------------------------------------------------

def new_agent(
    name,
    demographics=None,
    background="", expertise="", outcomes="", values="",
    alignment_strategy="visionary",
    founder_identity=None,
    risk=5, bias=5, dominance=5, optimism=5, note="",
):
    demographics = demographics or {}
    founder_identity = founder_identity or {}
    return {
        "id": uuid.uuid4().hex[:10],
        "name": name,
        "demographics": {
            "age": demographics.get("age", ""),
            "gender": demographics.get("gender", ""),
            "region": demographics.get("region", ""),
            "education_level": demographics.get("education_level", ""),
            "socioeconomic_background": demographics.get("socioeconomic_background", ""),
            "source": demographics.get("source", "assigned"),  # "assigned" | "stated"
        },
        "grounded": {
            "background": background,
            "expertise": expertise,
            "outcomes": outcomes,
            "values": values,
        },
        "alignment_strategy": alignment_strategy if alignment_strategy in ALIGNMENT_STRATEGIES else "visionary",
        "founder_identity": {
            "missionary": int(founder_identity.get("missionary", 5)),
            "darwinian": int(founder_identity.get("darwinian", 5)),
            "communitarian": int(founder_identity.get("communitarian", 5)),
            "source": founder_identity.get("source", "assigned"),  # "assigned" | "self-report" | "interview-perception"
        },
        "assigned": {
            "risk": risk,
            "bias": bias,
            "dominance": dominance,
            "optimism": optimism,
            "note": note,
        },
        "memory": [],
        "last_reflection_index": 0,
    }


# ---------------------------------------------------------------------------
# Claude API calls
# ---------------------------------------------------------------------------

def call_claude(system_prompt, messages, max_tokens=700, retries=2):
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
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Claude API call failed after retries: {last_err}")


def _parse_reasoning_stance(raw):
    """Expects JSON like {"reasoning": "...", "stance": "..."}.
    Falls back gracefully if the model didn't comply (e.g. answered in
    plain prose because it took the brevity rules to heart)."""
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
    NOT infer demographics or cognitive traits -- those stay under the
    person's explicit control, never silently guessed from a bio."""
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
# Memory stream (Park et al., 2023)
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


def retrieve_memories(agent, k=6):
    """Simplified recency+importance retrieval (no embeddings). See README
    for what a fuller semantic-relevance version would add."""
    memory = agent["memory"]
    if not memory:
        return []
    current_turn = len(memory)
    scored = []
    for m in memory:
        elapsed = current_turn - m["turn"]
        recency = MEMORY_DECAY ** elapsed
        score = 0.6 * (m["importance"] / 10.0) + 0.4 * recency
        scored.append((score, m))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = [m for _, m in scored[:k]]
    top.sort(key=lambda m: m["turn"])
    return [f"[{m['type']}] {m['text']}" for m in top]


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
# PIECE 1 of 2: per-agent qualities block
# ---------------------------------------------------------------------------

def render_qualities_block(agent, include_memory=True):
    """Everything that makes THIS agent different from any other. This is
    the only piece of the prompt that varies from agent to agent."""
    d = agent["demographics"]
    g = agent["grounded"]
    a = agent["assigned"]
    fi = agent["founder_identity"]
    strat = ALIGNMENT_STRATEGIES[agent["alignment_strategy"]]

    demo_bits = [v for v in [
        f"{d['age']} years old" if d.get("age") else "",
        d.get("gender", ""),
        f"based in {d['region']}" if d.get("region") else "",
        f"{d['education_level']} education" if d.get("education_level") else "",
        f"{d['socioeconomic_background']} socioeconomic background" if d.get("socioeconomic_background") else "",
    ] if v]
    demo_line = ", ".join(demo_bits) if demo_bits else "not specified"

    identity_line = (
        f"Missionary orientation ({fi['missionary']}/10 -- {FOUNDER_IDENTITY_DESCRIPTIONS['missionary']}); "
        f"Darwinian orientation ({fi['darwinian']}/10 -- {FOUNDER_IDENTITY_DESCRIPTIONS['darwinian']}); "
        f"Communitarian orientation ({fi['communitarian']}/10 -- {FOUNDER_IDENTITY_DESCRIPTIONS['communitarian']}). "
        "You hold all three to some degree, not just one -- let whichever is highest dominate your "
        "stated justifications, but don't ignore the others entirely."
    )

    note_line = f"Additional note: {a['note']}" if a.get("note") else ""

    memory_block = ""
    if include_memory:
        memories = retrieve_memories(agent)
        if memories:
            memory_block = "\nRELEVANT MEMORIES FROM YOUR OWN PAST (most important/recent surfaced):\n" + \
                "\n".join(f"- {m}" for m in memories) + "\n"

    return f"""DEMOGRAPHICS: {demo_line}

GROUNDED IDENTITY (who this person is):
Background: {g.get('background') or 'not specified'}
Domain expertise: {g.get('expertise') or 'not specified'}
Prior outcomes: {g.get('outcomes') or 'not specified'}
Stated values / voice: {g.get('values') or 'not specified'}

ALIGNMENT STRATEGY -- you are a "{strat['label']}" type founder ({strat['focus']}). Your \
central question is: "{strat['question']}" You are strong at mitigating {strat['mitigates']}. \
However, you are structurally weak on {strat['blind_spot']}

FOUNDER IDENTITY: {identity_line}

ASSIGNED COGNITIVE TENDENCIES (experimental settings, not fixed facts about the real person):
Risk tolerance: {a['risk']}/10
Confirmation bias: {a['bias']}/10 (higher means you more readily interpret ambiguous \
information as confirming what you already believed or planned)
Group dominance: {a['dominance']}/10 (higher means you speak more assertively and are \
more likely to steer or talk over others)
Optimism: {a['optimism']}/10
{note_line}
{memory_block}Let your alignment strategy's blind spot, your founder identity blend, and your \
assigned tendencies all visibly shape what you actually think -- not just your tone."""


# ---------------------------------------------------------------------------
# PIECE 2 of 2: universal instructions (imported verbatim, unchanged per agent)
# ---------------------------------------------------------------------------
# See universal_instructions.py -- UNIVERSAL_INSTRUCTIONS is the single
# source of truth, appended identically to every agent's prompt below.


def build_system_prompt(agent, include_memory=True, json_output=True):
    """The only place the two prompt pieces are joined: per-agent qualities,
    then a technical output-format note (for the research log, not part of
    the character), then the universal instructions verbatim, last."""
    intro = (f"You are {agent['name']}, being interviewed as part of a research "
              "simulation about how founders think and act.\n\n")
    qualities = render_qualities_block(agent, include_memory=include_memory)

    if json_output:
        format_block = (
            "\n\nOUTPUT FORMAT (for the research record only -- this is not part of "
            "who you are, it's just how your response gets logged): reply with ONLY a "
            "JSON object, no markdown fences: "
            '{"reasoning": "...", "stance": "..."}. '
            '"reasoning" is your own private, unspoken thought -- it can be a fragment, '
            'it does not need to be tidy or complete. "stance" is what you\'d actually '
            "say out loud, and the rules below govern how you speak."
        )
    else:
        format_block = (
            "\n\nOUTPUT FORMAT: respond in plain natural language, as this person "
            "speaking -- not JSON, not a report."
        )

    return intro + qualities + format_block + "\n\n" + UNIVERSAL_INSTRUCTIONS


# ---------------------------------------------------------------------------
# Scenario runs
# ---------------------------------------------------------------------------

def react_individually(agent, scenario):
    system = build_system_prompt(agent)
    user_msg = f"""FEEDBACK EVENT:
{scenario}

What's your reaction to this?"""
    raw = call_claude(system, [{"role": "user", "content": user_msg}])
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
    raw = call_claude(system, [{"role": "user", "content": user_msg}])
    result = _parse_reasoning_stance(raw)

    add_memory(
        agent,
        f"In group discussion about '{scenario[:60]}...', said: '{result['stance']}' "
        f"(privately thought: {result['reasoning']})",
        mtype="observation",
    )
    maybe_reflect(agent)
    return result
