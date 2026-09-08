# Founder Cognition Lab

A sandbox for exploring how synthetic founder agents interpret and react to
early feedback -- individually, in a group discussion, or in one-on-one chat.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...     # Windows: set ANTHROPIC_API_KEY=sk-ant-...
export SUPABASE_URL=https://xxxxx.supabase.co
export SUPABASE_KEY=your-service-role-key
```

See the top of `storage.py` for the one-time Supabase table setup (SQL to
run in the Supabase SQL editor).

## Run the web app

```bash
python app.py
```

Then open **http://127.0.0.1:5000**.

The app has six pages, navigated via the top bar:

- **Build Agent** -- construct a new agent: demographics, grounded facts,
  alignment strategy, founder identity blend, cognitive dials, temperature.
  A live JSON preview updates as you type; "Preview System Prompt" shows
  exactly what the agent will see before you spend an API call on it.
- **Agent Library** -- a card grid of every saved agent, with edit/delete.
- **Chat with Agent** -- free-form one-on-one conversation with any agent.
- **Individual Reaction Elicitation** -- select agent(s), give a stimulus,
  see each agent's independent reasoning/stance.
- **Group Interaction Elicitation** -- select two or more agents, run a
  turn-based discussion, with private reasoning tucked behind an expandable
  toggle per turn.
- **Guidance** -- reference material: what each alignment strategy, founder
  identity, and construction tier means, plus research guidance on writing
  feedback stimuli.

## Run the CLI (alternative)

```bash
python main.py
```

## Notes

- Default model is `claude-sonnet-5`, set at the top of `response_engine.py`.
- Agents and chat histories are stored in Supabase, shared between the web
  app and the CLI.
