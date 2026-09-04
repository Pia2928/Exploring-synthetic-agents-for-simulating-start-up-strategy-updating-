# Founder Cognition Lab (CLI)

A sandbox for exploring how synthetic founder agents interpret and react to
early feedback — individually, in a group discussion, or in one-on-one chat.

Each agent is split into two layers:
- **Grounded** — real background info (career, expertise, prior outcomes,
  stated values), either typed in or extracted from a pasted bio.
- **Assigned** — experimental cognitive dials (risk tolerance, confirmation
  bias, group dominance, optimism) that *you* set for the simulation. These
  are not inferred from the bio — they're variables you're testing.

## Setup

1. **Clone the repo**
   ```bash
   git clone <your-repo-url>
   cd founder_cognition_lab
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python3 -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set your Anthropic API key**

   Get a key from the [Anthropic Console](https://console.anthropic.com/),
   then export it:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...     # Windows: set ANTHROPIC_API_KEY=sk-ant-...
   ```

## Run

```bash
python main.py
```

You'll get a menu:

```
=== Founder Cognition Lab ===
1. List agents
2. Add agent
3. Edit agent
4. Delete agent
5. Run individual reactions
6. Run group discussion
7. Chat with an agent
0. Exit
```

- **Add agent** — fill fields manually, or paste a bio and let Claude extract
  the grounded fields, then set the assigned dials yourself.
- **Run individual reactions** — describe a feedback event (e.g. "first
  customer call, mixed signals on pricing"), pick which agents react, and
  each responds independently with an interpretation + proposed next step.
- **Run group discussion** — same idea, but selected agents take turns in a
  shared transcript over however many rounds you set, each seeing what's
  been said so far.
- **Chat with an agent** — a persistent one-on-one thread with a single
  agent, outside of any scenario.

Agents are saved to `data/agents.json`; chat histories to
`data/chats/<agent_id>.json`. Both are gitignored by default so your
experimental data doesn't get committed alongside the code.

## Publishing to GitHub

```bash
git init
git add .
git commit -m "Initial commit: Founder Cognition Lab CLI"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

## Notes

- Default model is `claude-sonnet-5` (set in `agents.py`) — swap to a
  cheaper/faster model for quick iteration if you're running many agents
  or many rounds.
- This is intentionally exploratory: there's no scoring or forced
  pivot/persevere decision. The goal is to see whether grounded background +
  assigned cognitive dials actually produce distinguishable reasoning before
  building anything more rigorous (e.g. structured belief logging, repeated
  trials across conditions) on top.
