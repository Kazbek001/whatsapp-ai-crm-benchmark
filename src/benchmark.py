"""Collect real paired request timings for the Java baseline and local LLM."""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "benchmark_config.json").read_text(encoding="utf-8"))
INTENTS = ("pricing", "business_hours", "sales", "information", "support", "fallback")
PROMPT = (ROOT / "docs/prompt.txt").read_text(encoding="utf-8").strip()
SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"enum": INTENTS},
        "case_ref": {"type": "string"},
    },
    "required": ["intent", "case_ref"],
    "additionalProperties": False,
}


class Baseline:
    def __enter__(self):
        self.process = subprocess.Popen(
            ["java", "src/main/java/benchmark/Main.java", "--stream"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.predict("Initialize Java source launcher.")
        return self.predict

    def __exit__(self, *_):
        self.process.stdin.close()
        self.process.wait(timeout=30)
        self.process.stdout.close()

    def predict(self, question):
        encoded = base64.b64encode(question.encode("utf-8")).decode("ascii")
        self.process.stdin.write(encoded + "\n")
        self.process.stdin.flush()
        intent, answer = self.process.stdout.readline().rstrip("\n").split("\t", 1)
        # The original Java bot has no CRM extraction.
        return {"intent": intent, "case_ref": ""}


def llm_predictor(endpoint):
    def predict(question):
        payload = {
            "model": "qwen",
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": question},
            ],
            "response_format": {"type": "json_object", "schema": SCHEMA},
            "temperature": CONFIG["temperature"],
            "seed": CONFIG["seed"],
            "max_tokens": 40,
            "cache_prompt": True,
        }
        request = Request(
            endpoint, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=CONFIG["timeout_seconds"]) as response:
            reply = json.load(response)["choices"][0]["message"]["content"]
        result = json.loads(reply)
        if result["intent"] not in INTENTS:
            raise ValueError("Invalid intent")
        if result["case_ref"] and not re.fullmatch(r"REF[0-9]{4}", result["case_ref"]):
            raise ValueError("Invalid CRM reference")
        return result
    return predict


def measure(predict, query, system, phase, concurrency, repetition):
    started = time.perf_counter_ns()
    try:
        result = predict(query["question"])
        error = None
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        result = {"intent": None, "case_ref": None}
        error = type(exc).__name__
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    return {
        "query_id": query["query_id"],
        "expected_intent": query["expected_intent"],
        "expected_case_ref": query["expected_case_ref"],
        "system": system,
        "phase": phase,
        "concurrency": concurrency,
        "repetition": repetition,
        "predicted_intent": result["intent"],
        "predicted_case_ref": result["case_ref"],
        "latency_ms": elapsed_ms,
        "status": "error" if error else "ok",
        "error_type": error,
    }


def run_system(pool, predictors, queries, system, phase, level, repetition, output):
    for start in range(0, len(queries), level):
        batch = queries[start:start + level]
        futures = [
            pool.submit(measure, predictors[worker], query, system, phase, level, repetition)
            for worker, query in enumerate(batch)
        ]
        for future in futures:
            output.write(json.dumps(future.result(), ensure_ascii=False) + "\n")
        output.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--output", type=Path, default=ROOT / "data/raw/test_run.jsonl")
    args = parser.parse_args()

    model = llm_predictor(args.endpoint)
    model("Is your office open today?")  # Connectivity/schema preflight, outside the log.
    with (ROOT / CONFIG["dataset"]).open(encoding="utf-8", newline="") as file:
        queries = list(csv.DictReader(file))
    # Four fixed queries per intent for the supplemental load test.
    load_queries = [
        query for intent in INTENTS
        for query in [row for row in queries if row["expected_intent"] == intent][:4]
    ]
    warmup = [
        {"query_id": f"W{i}", "question": f"Please tell me your opening hours on day {i}.",
         "expected_intent": "business_hours", "expected_case_ref": ""}
        for i in range(1, CONFIG["warmup_requests_per_level"] + 1)
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    partial = args.output.with_suffix(".partial")
    with partial.open("w", encoding="utf-8") as output:
        with Baseline() as baseline_a, Baseline() as baseline_b:
            predictors = {"rule_based": [baseline_a, baseline_b], "llm": [model, model]}
            for level in CONFIG["concurrency_levels"]:
                evaluation = queries if level == 1 else load_queries
                with ThreadPoolExecutor(max_workers=level) as pool:
                    for system, workers in predictors.items():
                        run_system(pool, workers, warmup, system, "warmup", level, 0, output)
                    for repetition in range(1, CONFIG["repetitions"] + 1):
                        order = list(predictors) if repetition % 2 else list(reversed(predictors))
                        for system in order:
                            run_system(pool, predictors[system], evaluation, system,
                                       "evaluation", level, repetition, output)
                        print(f"Concurrency {level}, repetition {repetition} complete", flush=True)
    partial.replace(args.output)
    cpu = platform.processor() or platform.machine()
    if Path("/proc/cpuinfo").exists():
        cpu = next(
            (line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
             if line.startswith("model name")),
            cpu,
        )
    metadata = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "cpu": cpu,
        "visible_cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "java": subprocess.run(["java", "-version"], capture_output=True,
                               text=True, check=True).stderr.splitlines()[0],
        "model": CONFIG["model"],
        "runner": CONFIG["runner"],
    }
    args.output.with_suffix(".metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
