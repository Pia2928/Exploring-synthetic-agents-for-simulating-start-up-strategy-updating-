"""
Founder Cognition Lab -- local web server.

Serves a browser UI (templates/index.html + static/) and a small JSON API
backed by agents.py / storage.py. The Anthropic API key stays server-side --
the browser never sees it.

Run: python app.py
Then open: http://127.0.0.1:5000
"""

import os
import sys

from flask import Flask, jsonify, render_template, request

import storage
import agents as agent_lib

app = Flask(__name__)


def require_api_key():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "\nANTHROPIC_API_KEY is not set. Set it before running, e.g.:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...\n"
        )
        sys.exit(1)


# ---------- Pages ----------

@app.route("/")
def index():
    return render_template("index.html")


# ---------- Reference data (for building the agent form) ----------

@app.route("/api/reference", methods=["GET"])
def reference():
    return jsonify({
        "alignment_strategies": agent_lib.ALIGNMENT_STRATEGIES,
        "founder_identity_descriptions": agent_lib.FOUNDER_IDENTITY_DESCRIPTIONS,
    })


# ---------- Agents ----------

def _agent_payload_to_kwargs(data):
    return dict(
        name=data.get("name", "").strip(),
        demographics={
            "age": data.get("age", ""),
            "gender": data.get("gender", ""),
            "region": data.get("region", ""),
            "education_level": data.get("education_level", ""),
            "socioeconomic_background": data.get("socioeconomic_background", ""),
            "source": data.get("demographics_source", "assigned"),
        },
        background=data.get("background", ""),
        expertise=data.get("expertise", ""),
        outcomes=data.get("outcomes", ""),
        values=data.get("values", ""),
        alignment_strategy=data.get("alignment_strategy", "visionary"),
        founder_identity={
            "missionary": int(data.get("missionary", 5)),
            "darwinian": int(data.get("darwinian", 5)),
            "communitarian": int(data.get("communitarian", 5)),
            "source": data.get("identity_source", "assigned"),
        },
        risk=int(data.get("risk", 5)),
        bias=int(data.get("bias", 5)),
        dominance=int(data.get("dominance", 5)),
        optimism=int(data.get("optimism", 5)),
        note=data.get("note", ""),
    )


@app.route("/api/agents", methods=["GET"])
def list_agents():
    return jsonify(storage.load_agents())


@app.route("/api/agents", methods=["POST"])
def create_agent():
    data = request.get_json(force=True)
    kwargs = _agent_payload_to_kwargs(data)
    if not kwargs["name"]:
        return jsonify({"error": "name is required"}), 400
    agent = agent_lib.new_agent(**kwargs)
    agents = storage.load_agents()
    agents.append(agent)
    storage.save_agents(agents)
    return jsonify(agent), 201


@app.route("/api/agents/<agent_id>", methods=["PUT"])
def update_agent(agent_id):
    data = request.get_json(force=True)
    agents = storage.load_agents()
    for a in agents:
        if a["id"] == agent_id:
            kwargs = _agent_payload_to_kwargs(data)
            a["name"] = kwargs["name"] or a["name"]
            a["demographics"] = kwargs["demographics"]
            a["grounded"] = {
                "background": kwargs["background"],
                "expertise": kwargs["expertise"],
                "outcomes": kwargs["outcomes"],
                "values": kwargs["values"],
            }
            a["alignment_strategy"] = kwargs["alignment_strategy"]
            a["founder_identity"] = kwargs["founder_identity"]
            a["assigned"] = {
                "risk": kwargs["risk"], "bias": kwargs["bias"],
                "dominance": kwargs["dominance"], "optimism": kwargs["optimism"],
                "note": kwargs["note"],
            }
            storage.save_agents(agents)
            return jsonify(a)
    return jsonify({"error": "agent not found"}), 404


@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id):
    agents = storage.load_agents()
    agents = [a for a in agents if a["id"] != agent_id]
    storage.save_agents(agents)
    storage.save_chat(agent_id, [])
    return jsonify({"ok": True})


@app.route("/api/agents/<agent_id>/memory", methods=["GET"])
def get_memory(agent_id):
    agents = storage.load_agents()
    agent = next((a for a in agents if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "agent not found"}), 404
    return jsonify(agent.get("memory", []))


@app.route("/api/extract-bio", methods=["POST"])
def extract_bio():
    bio = request.get_json(force=True).get("bio", "").strip()
    if not bio:
        return jsonify({"error": "no bio text provided"}), 400
    try:
        fields = agent_lib.extract_bio_fields(bio)
        return jsonify(fields)
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500


# ---------- Scenario runs ----------

@app.route("/api/run/individual", methods=["POST"])
def run_individual():
    data = request.get_json(force=True)
    scenario = data.get("scenario", "").strip()
    agent_ids = data.get("agent_ids", [])
    if not scenario or not agent_ids:
        return jsonify({"error": "scenario and at least one agent_id are required"}), 400

    agents = storage.load_agents()
    selected = [a for a in agents if a["id"] in agent_ids]
    results = []
    for a in selected:
        try:
            reaction = agent_lib.react_individually(a, scenario)
            results.append({"agent_id": a["id"], "name": a["name"], **reaction})
        except Exception as e:  # noqa: BLE001
            results.append({"agent_id": a["id"], "name": a["name"], "error": str(e)})
    storage.save_agents(agents)  # persist updated memory streams
    return jsonify(results)


@app.route("/api/run/group", methods=["POST"])
def run_group():
    data = request.get_json(force=True)
    scenario = data.get("scenario", "").strip()
    agent_ids = data.get("agent_ids", [])
    rounds = max(1, min(4, int(data.get("rounds", 2))))
    if not scenario or len(agent_ids) < 2:
        return jsonify({"error": "scenario and at least two agent_ids are required"}), 400

    agents = storage.load_agents()
    selected = [a for a in agents if a["id"] in agent_ids]
    transcript = []
    turns = []
    for r in range(rounds):
        for a in selected:
            try:
                reaction = agent_lib.react_in_group_turn(a, scenario, transcript)
                turn = {"agent_id": a["id"], "name": a["name"], "round": r + 1, **reaction}
            except Exception as e:  # noqa: BLE001
                turn = {"agent_id": a["id"], "name": a["name"], "round": r + 1,
                        "reasoning": "", "stance": f"[error: {e}]"}
            transcript.append({"name": turn["name"], "stance": turn["stance"]})
            turns.append(turn)
    storage.save_agents(agents)  # persist updated memory streams
    return jsonify(turns)


# ---------- Chat ----------

@app.route("/api/chat/<agent_id>", methods=["GET"])
def get_chat(agent_id):
    return jsonify(storage.load_chat(agent_id))


@app.route("/api/chat/<agent_id>", methods=["POST"])
def post_chat(agent_id):
    message = request.get_json(force=True).get("message", "").strip()
    if not message:
        return jsonify({"error": "empty message"}), 400

    agents = storage.load_agents()
    agent = next((a for a in agents if a["id"] == agent_id), None)
    if not agent:
        return jsonify({"error": "agent not found"}), 404

    history = storage.load_chat(agent_id)
    history.append({"role": "user", "content": message})
    system = agent_lib.build_system_prompt(agent, include_memory=False, json_output=False)
    try:
        reply = agent_lib.call_claude(system, history)
        history.append({"role": "assistant", "content": reply})
        storage.save_chat(agent_id, history)
        return jsonify({"reply": reply})
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat/<agent_id>/clear", methods=["POST"])
def clear_chat(agent_id):
    storage.save_chat(agent_id, [])
    return jsonify({"ok": True})


if __name__ == "__main__":
    require_api_key()
    app.run(debug=True, port=5000)
