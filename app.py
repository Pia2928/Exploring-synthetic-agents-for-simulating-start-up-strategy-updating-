"""
Founder Cognition Lab — local web server.

Serves a browser UI (templates/index.html + static/) and a small JSON API
backed by the same agents.py / storage.py used by the CLI version. The
Anthropic API key stays server-side — the browser never sees it.

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


# ---------- Agents ----------

@app.route("/api/agents", methods=["GET"])
def list_agents():
    return jsonify(storage.load_agents())


@app.route("/api/agents", methods=["POST"])
def create_agent():
    data = request.get_json(force=True)
    agents = storage.load_agents()
    agent = agent_lib.new_agent(
        name=data.get("name", "").strip(),
        background=data.get("background", ""),
        expertise=data.get("expertise", ""),
        outcomes=data.get("outcomes", ""),
        values=data.get("values", ""),
        risk=int(data.get("risk", 5)),
        bias=int(data.get("bias", 5)),
        dominance=int(data.get("dominance", 5)),
        optimism=int(data.get("optimism", 5)),
        note=data.get("note", ""),
    )
    if not agent["name"]:
        return jsonify({"error": "name is required"}), 400
    agents.append(agent)
    storage.save_agents(agents)
    return jsonify(agent), 201


@app.route("/api/agents/<agent_id>", methods=["PUT"])
def update_agent(agent_id):
    data = request.get_json(force=True)
    agents = storage.load_agents()
    for a in agents:
        if a["id"] == agent_id:
            a["name"] = data.get("name", a["name"]).strip() or a["name"]
            a["grounded"] = {
                "background": data.get("background", a["grounded"]["background"]),
                "expertise": data.get("expertise", a["grounded"]["expertise"]),
                "outcomes": data.get("outcomes", a["grounded"]["outcomes"]),
                "values": data.get("values", a["grounded"]["values"]),
            }
            a["assigned"] = {
                "risk": int(data.get("risk", a["assigned"]["risk"])),
                "bias": int(data.get("bias", a["assigned"]["bias"])),
                "dominance": int(data.get("dominance", a["assigned"]["dominance"])),
                "optimism": int(data.get("optimism", a["assigned"]["optimism"])),
                "note": data.get("note", a["assigned"]["note"]),
            }
            storage.save_agents(agents)
            return jsonify(a)
    return jsonify({"error": "agent not found"}), 404


@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id):
    agents = storage.load_agents()
    agents = [a for a in agents if a["id"] != agent_id]
    storage.save_agents(agents)
    storage.save_chat(agent_id, [])  # clear any associated chat history too
    return jsonify({"ok": True})


@app.route("/api/extract-bio", methods=["POST"])
def extract_bio():
    bio = request.get_json(force=True).get("bio", "").strip()
    if not bio:
        return jsonify({"error": "no bio text provided"}), 400
    try:
        fields = agent_lib.extract_bio_fields(bio)
        return jsonify(fields)
    except Exception as e:
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
            reply = agent_lib.react_individually(a, scenario)
            results.append({"agent_id": a["id"], "name": a["name"], "reply": reply})
        except Exception as e:
            results.append({"agent_id": a["id"], "name": a["name"], "error": str(e)})
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
                reply = agent_lib.react_in_group_turn(a, scenario, transcript)
                turn = {"agent_id": a["id"], "name": a["name"], "text": reply, "round": r + 1}
            except Exception as e:
                turn = {"agent_id": a["id"], "name": a["name"], "text": f"[error: {e}]", "round": r + 1}
            transcript.append({"name": turn["name"], "text": turn["text"]})
            turns.append(turn)
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
    system = agent_lib.build_system_prompt(agent)
    try:
        reply = agent_lib.call_claude(system, history)
        history.append({"role": "assistant", "content": reply})
        storage.save_chat(agent_id, history)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat/<agent_id>/clear", methods=["POST"])
def clear_chat(agent_id):
    storage.save_chat(agent_id, [])
    return jsonify({"ok": True})


if __name__ == "__main__":
    require_api_key()
    app.run(debug=True, port=5000)
