# Founder Cognition Lab

A sandbox for exploring how synthetic founder agents interpret and react to
early feedback -- individually, in a group discussion, or in one-on-one chat.

## Agent architecture

Every agent's prompt is assembled from exactly **two pieces**, kept
deliberately separate in code (`agents.py` builds piece 1,
`universal_instructions.py` holds piece 2 verbatim, `build_system_prompt()`
is the only place they're joined):

**Piece 1 — per-agent qualities** (`render_qualities_block`, varies per agent):

1. **Demographics** -- age, gender, region, education, socioeconomic
   background. Always set, so a roster of agents doesn't default to
   whatever the model's implicit "typical founder" looks like.
2. **Grounded facts** -- background, expertise, prior outcomes, stated
   values.
3. **Alignment strategy** (Zellweger & Djokovic, 2026) -- Visionary,
   Engineer, or Experimenter, each with a named structural blind spot.
4. **Founder identity blend** (Fauchart & Gruber / Sieger et al.) --
   Missionary, Darwinian, and Communitarian scored 0-10 each.
5. **Assigned cognitive dials** -- risk tolerance, confirmation bias, group
   dominance, optimism.
6. **Memory + reflection** (Park et al., 2023) -- retrieved relevant
   memories from the agent's own scenario history.

**Piece 2 — universal instructions** (`universal_instructions.py`, identical
for every agent, appended verbatim at the very end of the prompt): a fixed
behavioural rule set -- stay in character, no forced hedging or thoroughness,
allowed to be blunt, wrong, biased, or brief. Same text for every agent,
regardless of who they are.

Agents are still created **one at a time** through `new_agent()` -- the
two-piece split is about how each individual agent's prompt is composed,
not about batching.

Every scenario response is additionally logged as two separate fields
(distinct from the two-piece prompt split above): private **reasoning** and
public **stance** (Csaszar et al., 2026 -- reasoning before the forced
choice). In group discussions, other agents only see each other's stance,
never their reasoning.

Older summary of the six qualities layers, for reference:

1. **Demographics** -- age, gender, region, education, socioeconomic
   background. Always set, so a roster of agents doesn't default to
   whatever the model's implicit "typical founder" looks like.
2. **Grounded facts** -- background, expertise, prior outcomes, stated
   values. Sparse for pure trait-based agents, rich if built from a real
   bio or interview.
3. **Alignment strategy** (Zellweger & Djokovic, 2026) -- Visionary,
   Engineer, or Experimenter. Each mitigates two of four uncertainty types
   (state, perception, execution, effect) and is structurally blind to the
   other two -- this predicts, not just describes, where an agent's
   reasoning should break down.
4. **Founder identity blend** (Fauchart & Gruber / Sieger et al.) --
   Missionary, Darwinian, and Communitarian scored 0-10 each, since real
   founders score on more than one, not a single category.
5. **Assigned cognitive dials** -- risk tolerance, confirmation bias, group
   dominance, optimism. Experimental variables you set, not psychology
   read off a resume.
6. **Memory + reflection** (Park et al., 2023) -- every scenario reaction
   and group turn is logged as a memory with an importance score. Retrieval
   pulls back the most important/recent memories for new scenarios.
   Periodic reflection synthesizes recent memories into a higher-level
   insight, citing what it drew on.

Every scenario response is logged as two separate fields: private
**reasoning** and public **stance** (Csaszar et al., 2026 -- reasoning
before the forced choice). In group discussions, other agents only see
each other's stance, never their reasoning -- mirroring the real gap
between what a founder privately concludes and what they say out loud.

Two ways to run it:
- **`app.py`** -- a local web app (Flask + browser UI) at `http://127.0.0.1:5000`.
- **`main.py`** -- a plain terminal CLI, no browser needed.

Both share the same backend (`agents.py`, `storage.py`).

## Setup

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...     # Windows: set ANTHROPIC_API_KEY=sk-ant-...
```

## Run the web app (recommended)

```bash
python app.py
```

Then open **http://127.0.0.1:5000**. Leave the terminal running -- that's
your local server. `Ctrl+C` stops it.

The page has:
- A **roster** on the left -- add agents from scratch or by pasting a bio.
- A **stimulus box** -- describe the feedback event, pick which agents take part.
- Four tabs: **Individual reactions**, **Group scenario**, **Chat with an
  agent**, and **Memory stream** (inspect what a given agent has logged and
  reflected on so far).

Agents and chat histories are saved to `data/` on your machine (gitignored),
shared between the web app and the CLI below.

## Run the CLI (alternative)

```bash
python main.py
```

```
=== Founder Cognition Lab ===
1. List agents
2. Add agent
3. Delete agent
4. Run individual reactions
5. Run group discussion
6. Chat with an agent
7. View an agent's memory stream
0. Exit
```

## Publishing to GitHub

```bash
git init
git add .
git commit -m "Initial commit: Founder Cognition Lab"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

## Notes

- Default model is `claude-sonnet-5`, set at the top of `agents.py`.
- Memory retrieval is a simplified recency+importance blend (no embeddings)
  -- see the comment in `agents.py::retrieve_memories` for what a fuller
  semantic-relevance version would add.
- This is intentionally exploratory: no scoring, no forced pivot/persevere
  vote, no docking-experiment analysis yet. The goal is to see whether
  grounded background + theory-derived strategy/identity + assigned dials
  produce distinguishable, theoretically legible reasoning before building
  anything more rigorous on top.
