"""
CLI + API Server for Deep Researcher.
"""
import json
import asyncio
import argparse
from pathlib import Path
from flask import Flask, request, jsonify, Response, stream_with_context
from config import REPORTS_DIR, BRIDGE_URL
from researcher import deep_research

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/research", methods=["POST"])
def start_research():
    data = request.get_json() or {}
    question = data.get("question") or data.get("query")
    if not question:
        return jsonify({"error": "question required"}), 400

    model_id = data.get("model_id")
    use_obscura = data.get("use_obscura", False)

    result = asyncio.run(deep_research(
        question=question,
        model_id=model_id,
        use_obscura=use_obscura,
    ))

    return jsonify({
        "question": result["question"],
        "report": result["report"],
        "stats": result["stats"],
    })


@app.route("/reports", methods=["GET"])
def list_reports():
    reports = []
    for f in sorted(REPORTS_DIR.glob("report_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            reports.append({
                "file": f.name,
                "question": data.get("question", "")[:100],
                "date": data.get("generated_at", ""),
                "findings": data.get("stats", {}).get("total_findings", 0),
            })
        except Exception:
            pass
    return jsonify({"reports": reports[:20]})


@app.route("/reports/<filename>", methods=["GET"])
def get_report(filename):
    path = REPORTS_DIR / filename
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    return jsonify(json.loads(path.read_text()))


def main():
    parser = argparse.ArgumentParser(description="Deep Researcher - MSDR Engine")
    parser.add_argument("question", nargs="?", help="Question to research")
    parser.add_argument("--model", type=int, default=None, help="Model ID")
    parser.add_argument("--obscura", action="store_true", help="Use Obscura")
    parser.add_argument("--serve", action="store_true", help="Start API server")
    parser.add_argument("--port", type=int, default=8766, help="Server port")
    args = parser.parse_args()

    if args.serve:
        print(f"Deep Researcher API on http://0.0.0.0:{args.port}")
        app.run(host="0.0.0.0", port=args.port)
    elif args.question:
        result = asyncio.run(deep_research(
            question=args.question,
            model_id=args.model,
            use_obscura=args.obscura,
        ))
        print("\n" + "=" * 60)
        print("FINAL REPORT:")
        print("=" * 60)
        print(result["report"])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
