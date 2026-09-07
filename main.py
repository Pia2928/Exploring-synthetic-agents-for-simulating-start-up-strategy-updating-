"""
Founder Cognition Lab -- CLI version.

Same backend as app.py (agents.py / storage.py), no browser needed.
Run: python main.py
"""

import os
import sys

import storage
import agents as agent_lib


def check_api_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nANTHROPIC_API_KEY is not set. Set it before running, e.g.:\n"
              "  export ANTHROPIC_API_KEY=sk-ant-...\n")
        sys.exit(1)


def prompt(text, default=None):
    suffix = f" [{default}]" if default not in (None, "") else ""
    val = input(f"{text}{suffix}: ").strip()
    return val if val else (default if default is not None else "")


def prompt_int(text, default=5, lo=0, hi=10):
    while True:
        raw = input(f"{text} ({lo}-{hi}) [{default}]: ").strip()
        if not raw:
            return default
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
        except ValueError:
            pass
        print(f"  enter a number between {lo} and {hi}")


def prompt_choice(text, options, default):
    keys = list(options.keys())
    for i, k in enumerate(keys):
        marker = " (default)" if k == default else ""
        print(f"  {i + 1}. {options[k]['label']} -- {options[k]['question']}{marker}")
    raw = input(f"{text} [{default}]: ").strip()
    if not raw:
        return default
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(keys):
            return keys[idx]
    except ValueError:
        if raw in options:
            return raw
    print("  invalid choice, using default")
    return default


def pick_agent(agents, prompt_text="Pick an agent"):
    if not agents:
        print("No agents yet. Add one first.")
        return None
    for i, a in enumerate(agents):
        strat = agent_lib.ALIGNMENT_STRATEGIES[a["alignment_strategy"]]["label"]
        print(f"  {i + 1}. {a['name']}  [{strat}]")
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
        try:
            idx = int(part.strip()) - 1
            if 0 <= idx < len(agents):
                selected.append(agents[idx])
        except ValueError:
            continue
    return selected


def add_agent(agents):
    print("\n--- New agent ---")
    background = expertise = outcomes = values = ""
    if prompt("Paste a bio to extract grounded fields from? (y/n)", "n").lower() == "y":
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
                fields = agent_lib.extract_bio_fields(bio_text)
                background, expertise = fields.get("background", ""), fields.get("expertise", "")
                outcomes, values = fields.get("outcomes", ""), fields.get("values", "")
                print("Extracted. Demographics, strategy, identity, and traits are still yours to set.\n")
            except Exception as e:
                print(f"  Extraction failed ({e}) -- fill fields in manually.\n")

    name = prompt("Name")
    if not name:
        print("Name is required -- cancelled.")
        return

    print("\nDemographics (baseline for every agent):")
    age = prompt("  Age")
    gender = prompt("  Gender")
    region = prompt("  Region / nationality")
    education = prompt("  Education level")
    socioeconomic = prompt("  Socioeconomic background")

    background = prompt("Background", background)
    expertise = prompt("Domain expertise", expertise)
    outcomes = prompt("Prior outcomes", outcomes)
    values = prompt("Stated values / voice", values)

    print("\nAlignment strategy (Zellweger & Djokovic):")
    strategy = prompt_choice("Choose", agent_lib.ALIGNMENT_STRATEGIES, "visionary")

    print("\nFounder identity blend (0-10 each -- real founders score on more than one):")
    missionary = prompt_int("  Missionary")
    darwinian = prompt_int("  Darwinian")
    communitarian = prompt_int("  Communitarian")

    print("\nAssigned cognitive dials (0-10):")
    risk = prompt_int("  Risk tolerance")
    bias = prompt_int("  Confirmation bias")
    dominance = prompt_int("  Group dominance")
    optimism = prompt_int("  Optimism")
    note = prompt("  Note (optional)")

    agent = agent_lib.new_agent(
        name=name,
        demographics={"age": age, "gender": gender, "region": region,
                      "education_level": education, "socioeconomic_background": socioeconomic},
        background=background, expertise=expertise, outcomes=outcomes, values=values,
        alignment_strategy=strategy,
        founder_identity={"missionary": missionary, "darwinian": darwinian, "communitarian": communitarian},
        risk=risk, bias=bias, dominance=dominance, optimism=optimism, note=note,
    )
    agents.append(agent)
    storage.save_agents(agents)
    print(f"\nSaved '{name}'.\n")


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
        strat = agent_lib.ALIGNMENT_STRATEGIES[a["alignment_strategy"]]["label"]
        fi = a["founder_identity"]
        d = a["demographics"]
        asn = a["assigned"]
        print(f"* {a['name']}  [{a['id']}]  -- {strat}")
        print(f"    demographics: age {d.get('age') or '-'}, {d.get('gender') or '-'}, {d.get('region') or '-'}")
        print(f"    identity: missionary {fi['missionary']}  darwinian {fi['darwinian']}  communitarian {fi['communitarian']}")
        print(f"    dials: risk {asn['risk']}  bias {asn['bias']}  dominance {asn['dominance']}  optimism {asn['optimism']}")
        print(f"    memories logged: {len(a.get('memory', []))}")
    print()


def view_memory(agents):
    agent = pick_agent(agents, "View memory for which agent")
    if not agent:
        return
    memory = agent.get("memory", [])
    if not memory:
        print("No memories logged yet.\n")
        return
    print(f"\n--- Memory stream: {agent['name']} ---")
    for m in memory:
        tag = "[REFLECTION]" if m["type"] == "reflection" else f"[{m['type']}]"
        print(f"{tag} (importance {m['importance']}/10, turn {m['turn']}): {m['text']}")
    print()


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
            result = agent_lib.react_individually(agent, scenario)
            print(f"  Reasoning (private): {result['reasoning']}")
            print(f"  Stance: {result['stance']}")
        except Exception as e:
            print(f"  [error: {e}]")
        print()
    storage.save_agents(agents)


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
                result = agent_lib.react_in_group_turn(agent, scenario, transcript)
                transcript.append({"name": agent["name"], "stance": result["stance"]})
                print(f"{agent['name']}: {result['stance']}")
                print(f"   (private reasoning: {result['reasoning']})\n")
            except Exception as e:
                print(f"{agent['name']}: [error: {e}]\n")
    storage.save_agents(agents)


def chat_with_agent(agents):
    agent = pick_agent(agents, "Chat with which agent")
    if not agent:
        return
    history = storage.load_chat(agent["id"])
    print(f"\nChatting with {agent['name']}. Type 'exit' to leave, 'clear' to reset.\n")
    system = agent_lib.build_system_prompt(agent, include_memory=False, json_output=False)

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
            reply = agent_lib.call_claude(system, history)
            history.append({"role": "assistant", "content": reply})
            storage.save_chat(agent["id"], history)
            print(f"{agent['name']}: {reply}")
        except Exception as e:
            print(f"  [error: {e}]")


MENU = """
=== Founder Cognition Lab ===
1. List agents
2. Add agent
3. Delete agent
4. Run individual reactions
5. Run group discussion
6. Chat with an agent
7. View an agent's memory stream
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
            delete_agent(agents)
        elif choice == "4":
            run_individual(agents)
        elif choice == "5":
            run_group(agents)
        elif choice == "6":
            chat_with_agent(agents)
        elif choice == "7":
            view_memory(agents)
        elif choice == "0":
            print("Bye.")
            break
        else:
            print("Not a valid option.\n")


if __name__ == "__main__":
    main()
