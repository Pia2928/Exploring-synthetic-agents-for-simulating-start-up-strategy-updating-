"""
Founder Cognition Lab — CLI version.

A sandbox for exploring how synthetic founder agents (grounded in real
background info, with assigned cognitive-tendency dials) interpret and
react to early feedback — individually, in a group discussion, or in
one-on-one chat.

Run: python main.py
"""

import os
import sys

import storage
from agents import (
    new_agent,
    extract_bio_fields,
    react_individually,
    react_in_group_turn,
    call_claude,
    build_system_prompt,
)


def check_api_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "\nANTHROPIC_API_KEY is not set. Set it before running, e.g.:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n"
        )
        sys.exit(1)


def prompt(text, default=None):
    suffix = f" [{default}]" if default is not None else ""
    val = input(f"{text}{suffix}: ").strip()
    return val if val else (default if default is not None else "")


def prompt_int(text, default=5, lo=0, hi=10):
    while True:
        raw = input(f"{text} (0-10) [{default}]: ").strip()
        if not raw:
            return default
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
        except ValueError:
            pass
        print(f"  enter a number between {lo} and {hi}")


def pick_agent(agents, prompt_text="Pick an agent"):
    if not agents:
        print("No agents yet. Add one first.")
        return None
    for i, a in enumerate(agents):
        print(f"  {i + 1}. {a['name']}  (risk {a['assigned']['risk']}, "
              f"bias {a['assigned']['bias']}, dominance {a['assigned']['dominance']})")
    raw = input(f"{prompt_text} (number, or blank to cancel): ").strip()
    if not raw:
        return None
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(agents):
            return agents[idx]
    except ValueError:
        pass
    print("  invalid selection")
    return None


def pick_multiple_agents(agents, prompt_text="Select agents"):
    if not agents:
        print("No agents yet. Add one first.")
        return []
    for i, a in enumerate(agents):
        print(f"  {i + 1}. {a['name']}")
    raw = input(f"{prompt_text} (comma-separated numbers, or 'all'): ").strip()
    if not raw:
        return []
    if raw.lower() == "all":
        return agents
    selected = []
    for part in raw.split(","):
        part = part.strip()
        try:
            idx = int(part) - 1
            if 0 <= idx < len(agents):
                selected.append(agents[idx])
        except ValueError:
            continue
    return selected


# ---------- Agent management ----------

def add_agent(agents):
    print("\n--- New agent ---")
    print("Optional: paste a LinkedIn-style bio to auto-fill the grounded fields.")
    print("Grounded fields describe who this person is. Assigned dials are")
    print("experimental variables you set — not inferred from the bio.\n")

    background = expertise = outcomes = values = ""
    use_bio = prompt("Paste a bio to extract from? (y/n)", "n").lower() == "y"
    if use_bio:
        print("Paste bio text, then press Enter twice:")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        bio_text = "\n".join(lines).strip()
        if bio_text:
            print("Extracting...")
            try:
                fields = extract_bio_fields(bio_text)
                background = fields.get("background", "")
                expertise = fields.get("expertise", "")
                outcomes = fields.get("outcomes", "")
                values = fields.get("values", "")
                print("Extracted. You can edit any field below (blank keeps it).\n")
            except Exception as e:
                print(f"  Extraction failed ({e}) — fill fields in manually.\n")

    name = prompt("Name")
    if not name:
        print("Name is required — cancelled.")
        return
    background = prompt("Background", background)
    expertise = prompt("Domain expertise", expertise)
    outcomes = prompt("Prior outcomes", outcomes)
    values = prompt("Stated values / voice", values)

    print("\nAssigned cognitive tendencies (experimental dials, 0-10):")
    risk = prompt_int("  Risk tolerance")
    bias = prompt_int("  Confirmation bias")
    dominance = prompt_int("  Group dominance")
    optimism = prompt_int("  Optimism")
    note = prompt("  Note (optional)")

    agent = new_agent(name, background, expertise, outcomes, values,
                       risk, bias, dominance, optimism, note)
    agents.append(agent)
    storage.save_agents(agents)
    print(f"\nSaved '{name}'.\n")


def edit_agent(agents):
    agent = pick_agent(agents, "Edit which agent")
    if not agent:
        return
    print(f"\n--- Editing {agent['name']} (blank keeps current value) ---")
    agent["name"] = prompt("Name", agent["name"])
    g = agent["grounded"]
    g["background"] = prompt("Background", g["background"])
    g["expertise"] = prompt("Domain expertise", g["expertise"])
    g["outcomes"] = prompt("Prior outcomes", g["outcomes"])
    g["values"] = prompt("Stated values / voice", g["values"])
    a = agent["assigned"]
    a["risk"] = prompt_int("Risk tolerance", a["risk"])
    a["bias"] = prompt_int("Confirmation bias", a["bias"])
    a["dominance"] = prompt_int("Group dominance", a["dominance"])
    a["optimism"] = prompt_int("Optimism", a["optimism"])
    a["note"] = prompt("Note", a["note"])
    storage.save_agents(agents)
    print("Saved.\n")


def delete_agent(agents):
    agent = pick_agent(agents, "Delete which agent")
    if not agent:
        return
    if prompt(f"Type 'yes' to delete {agent['name']}", "no").lower() == "yes":
        agents.remove(agent)
        storage.save_agents(agents)
        print("Deleted.\n")


def list_agents(agents):
    if not agents:
        print("No agents yet.\n")
        return
    print("\n--- Roster ---")
    for a in agents:
        g, asn = a["grounded"], a["assigned"]
        print(f"* {a['name']}  [{a['id']}]")
        print(f"    expertise: {g['expertise'] or '-'}")
        print(f"    risk {asn['risk']}  bias {asn['bias']}  "
              f"dominance {asn['dominance']}  optimism {asn['optimism']}")
    print()


# ---------- Scenario runs ----------

def run_individual(agents):
    scenario = prompt("Describe the feedback stimulus")
    if not scenario:
        return
    selected = pick_multiple_agents(agents, "Which agents should react")
    if not selected:
        print("No agents selected.\n")
        return
    print()
    for agent in selected:
        print(f"--- {agent['name']} ---")
        try:
            reply = react_individually(agent, scenario)
            print(reply)
        except Exception as e:
            print(f"  [error: {e}]")
        print()


def run_group(agents):
    scenario = prompt("Describe the feedback stimulus")
    if not scenario:
        return
    selected = pick_multiple_agents(agents, "Which agents join the discussion")
    if len(selected) < 2:
        print("Select at least two agents for a group discussion.\n")
        return
    rounds = 0
    while rounds < 1:
        try:
            rounds = int(prompt("Rounds per agent", "2"))
        except ValueError:
            rounds = 0

    transcript = []
    print()
    for r in range(rounds):
        print(f"== Round {r + 1} ==")
        for agent in selected:
            try:
                reply = react_in_group_turn(agent, scenario, transcript)
                transcript.append({"name": agent["name"], "text": reply})
                print(f"{agent['name']}: {reply}\n")
            except Exception as e:
                print(f"{agent['name']}: [error: {e}]\n")


def chat_with_agent(agents):
    agent = pick_agent(agents, "Chat with which agent")
    if not agent:
        return
    history = storage.load_chat(agent["id"])
    print(f"\nChatting with {agent['name']}. Type 'exit' to leave, 'clear' to reset.\n")
    system = build_system_prompt(agent)

    for m in history:
        speaker = "you" if m["role"] == "user" else agent["name"]
        print(f"{speaker}: {m['content']}")

    while True:
        msg = input("you: ").strip()
        if msg.lower() == "exit":
            break
        if msg.lower() == "clear":
            history = []
            storage.save_chat(agent["id"], history)
            print("Cleared.\n")
            continue
        if not msg:
            continue
        history.append({"role": "user", "content": msg})
        try:
            reply = call_claude(system, history)
            history.append({"role": "assistant", "content": reply})
            storage.save_chat(agent["id"], history)
            print(f"{agent['name']}: {reply}")
        except Exception as e:
            print(f"  [error: {e}]")


# ---------- Main menu ----------

MENU = """
=== Founder Cognition Lab ===
1. List agents
2. Add agent
3. Edit agent
4. Delete agent
5. Run individual reactions
6. Run group discussion
7. Chat with an agent
0. Exit
"""


def main():
    check_api_key()
    agents = storage.load_agents()
    while True:
        print(MENU)
        choice = input("Choose: ").strip()
        if choice == "1":
            list_agents(agents)
        elif choice == "2":
            add_agent(agents)
        elif choice == "3":
            edit_agent(agents)
        elif choice == "4":
            delete_agent(agents)
        elif choice == "5":
            run_individual(agents)
        elif choice == "6":
            run_group(agents)
        elif choice == "7":
            chat_with_agent(agents)
        elif choice == "0":
            print("Bye.")
            break
        else:
            print("Not a valid option.\n")


if __name__ == "__main__":
    main()
