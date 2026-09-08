# Founder Cognition Lab

A sandbox for exploring how synthetic founder agents interpret and react to
early feedback -- individually, in a group discussion, or in one-on-one chat.

## Project structure

Structured after the module split in
[Social-Simulations-for-Survey-based-Research](https://github.com/Pia2928/Social-Simulations-for-Survey-based-Research):
one file per responsibility, so construction, validation, and API calls
never mix.

```
founder_cognition_lab/
├── app.py                   -- Flask web server + API routes
├── main.py                  -- terminal CLI (same backend as app.py)
├── agent_library.py         -- agent construction, reference tables, prompt assembly
├── agent_validator.py       -- consistency checks before an agent is saved
├── response_engine.py       -- everything that calls the Anthropic API
├── storage.py                -- JSON-file persistence
├── universal_instructions.py -- the fixed behavioural rule set, verbatim for every agent
├── requirements.txt
├── templates/
│   └── index.html            -- the web UI shell
└── static/
    ├── style.css              -- visual design
    └── script.js              -- client-side logic (talks only to the local API)
```

## Agent architecture

Every agent's system prompt is assembled from exactly **two pieces**:

**Piece 1 -- per-agent qualities** (`agent_library.py::render_qualities_block`, varies per agent):
1. **Demographics** -- age, gender, region, education, socioeconomic background.
2. **Grounded facts** -- background, expertise, prior outcomes, stated values.
3. **Alignment strategy** (Zellweger & Djokovic, 2026) -- Visionary, Engineer,
   or Experimenter. Each mitigates two of four uncertainty types (state,
   perception, execution, effect) and is structurally blind to the other two.
4. **Founder identity blend** (Fauchart & Gruber / Sieger et al.) --
   Missionary, Darwinian, and Communitarian scored 0-10 each.
5. **Assigned cognitive dials** -- risk tolerance, confirmation bias, group
   dominance, optimism.
6. **Memory + reflection** (Park et al., 2023) -- retrieved relevant memories
   from the agent's own scenario history.

**Piece 2 -- universal instructions** (`universal_instructions.py`, identical
for every agent, appended verbatim at the very end of the prompt): stay in
character, no forced hedging or thoroughness, allowed to be blunt, wrong,
biased, or brief.

Every scenario response is additionally logged as two separate fields:
private **reasoning** and public **stance** (Csaszar et al., 2026 --
reasoning before the forced choice). In group discussions, other agents
only see each other's stance, never their reasoning.

## Validation

`agent_validator.py` checks every agent before it's saved, following the
same design principle as the reference repo's validator: **flag
contradictions or unconfigured defaults, not unusual-but-plausible
combinations.** For example, a founder who scores high on both Missionary
and Darwinian identity at once is real (Ossenbrink et al. found exactly
this correlation) and is never flagged. What *is* flagged:
- No name (blocks saving)
- An implausible age if one is given
- An Engineer strategy with no stated domain expertise (warning only)
- An entire settings section left untouched at its default (warning only)

Warnings never block saving -- they're returned alongside the created/updated
agent so you can double-check before running an experiment on it.

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

The app has six pages, navigated via the top bar:

- **Build Agent** -- the main construction page. Pick a construction tier
  (Tier 1: trait-based Persona, or Tier 2: idiographic/interview-grounded),
  fill in demographics, grounded facts, alignment strategy, founder identity
  blend, cognitive dials, and temperature. A live JSON preview on the right
  updates as you type, and "Preview System Prompt" shows exactly what the
  agent will see, before you spend an API call on it.
- **Agent Library** -- a card grid of every saved agent, with edit/delete.
- **Chat with Agent** -- free-form one-on-one conversation with any agent.
- **Individual Reaction Elicitation** -- select agent(s), give a stimulus,
  see each agent's independent reasoning/stance.
- **Group Interaction Elicitation** -- select two or more agents, run a
  turn-based discussion, with private reasoning tucked behind an expandable
  toggle per turn.
- **Guidance** -- reference material only, no interactive elements: what
  each alignment strategy, founder identity, and construction tier means,
  plus research guidance on writing feedback stimuli.

Agents and chat histories are stored in Supabase (see setup notes in
`storage.py`), shared between the web app and the CLI below.

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

- Default model is `claude-sonnet-5`, set at the top of `response_engine.py`.
- Memory retrieval is a simplified recency+importance blend (no embeddings)
  -- see `agent_library.py::retrieve_memories`.
- This is intentionally exploratory: no scoring, no forced pivot/persevere
  vote, no docking-experiment analysis yet. The goal is to see whether
  grounded background + theory-derived strategy/identity + assigned dials
  produce distinguishable, theoretically legible reasoning before building
  anything more rigorous on top.
