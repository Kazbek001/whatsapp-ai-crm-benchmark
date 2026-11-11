# C4 container view

The boundary is the Task 3 experimental benchmark. The benchmark uses synthetic WhatsApp-style messages and evaluates routing and ticket-reference extraction. The local model server is a separate runtime dependency.

```mermaid
flowchart TB
    researcher["Researcher"]
    dataset["Synthetic queries and expected labels · CSV"]
    model["llama.cpp HTTP server · Qwen model"]
    subgraph benchmark["WhatsApp assistant benchmark"]
        collector["Benchmark runner · Python<br/>M1: elapsed time, M2: request status"]
        baseline["Baseline process · Java keyword rules"]
        log["Raw measurements · JSONL"]
        analysis["Notebook and Python analysis<br/>M3: accuracy, M4: CRM field match"]
        figures["Processed CSV and publication figures"]
    end
    researcher -->|starts capture and analysis| collector
    dataset -->|loads questions and ground truth| collector
    collector -->|UTF-8 questions via stdin| baseline
    baseline -->|intent and template reply| collector
    collector -->|HTTP POST with prompt and question| model
    model -->|intent and case reference| collector
    collector -->|writes phase, timing, status and predictions| log
    log -->|evaluation rows only| analysis
    analysis -->|exports summaries and plots| figures
```

| Point | Metric | Collection boundary |
|---|---|---|
| M1 | Response latency, ms | Python monotonic clock around each request, including the relevant IPC or localhost HTTP path. |
| M2 | Request error rate, % | Runner records success or an exception for every attempt. |
| M3 | Intent accuracy, % | Analysis matches the predicted intent against the frozen label. A request failure is incorrect. |
| M4 | Case-reference completeness, % | Analysis checks exact matches on requests annotated with a required reference. |

The experiment covers one CRM field, `case_ref`, from synthetic messages. The WhatsApp gateway, reply quality, and live CRM storage are outside this benchmark boundary.
