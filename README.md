
# WhatsApp AI CRM Benchmark

## Authors
Kazbek001 — Individual Research Project

## Overview
This project evaluates an AI-powered customer service assistant for WhatsApp with a planned CRM integration. The experiment compares a rule-based baseline with an LLM-powered assistant using a common set of test queries.

The current prototype implements the rule-based baseline. The AI comparison and CRM evaluation are planned implementation stages.

## Research Question
Does an LLM-powered assistant achieve higher intent-classification accuracy than a rule-based baseline on the same predefined customer-query dataset while meeting performance and reliability targets?

## Primary Metric
Intent-classification accuracy:

Accuracy (%) = correctly classified queries / total queries × 100.

## Planned Benchmarks

| Metric | Purpose | Target |
|---|---|---|
| Intent accuracy | Correct intent classification | AI improvement of at least 10 percentage points |
| Average latency | Measure response time | Report in milliseconds |
| P95 latency | Monitor slower responses | At most 5000 ms |
| API error rate | Monitor failed requests | At most 5% |
| CRM field completeness | Measure required fields captured | At least 90% |

These values are proposed targets, not experimental results.

## System Requirements
- Java 17
- Maven 3.9+
- Docker (optional)

## Repository Structure
```text
.
├── config.yaml
├── data/
│   └── sample/
│       └── questions.csv
├── src/
│   └── main/java/benchmark/Main.java
├── results/
├── Dockerfile
├── pom.xml
├── .gitignore
├── LICENSE
└── README.md
```

## Quickstart
Clone the repository and run the baseline:

```bash
git clone https://github.com/Kazbek001/whatsapp-ai-crm-benchmark.git
cd whatsapp-ai-crm-benchmark
mvn -q compile exec:java
```

The program reads `data/sample/questions.csv`, prints the metrics, and writes `results/benchmark_results.csv`.

## Docker
Build the container:

```bash
docker build -t whatsapp-ai-crm-benchmark .
```

Run it and save the output report to the local `results` folder (PowerShell):

```powershell
New-Item -ItemType Directory -Force results
docker run --rm -v "${PWD}/results:/app/results" whatsapp-ai-crm-benchmark
```

## Data Privacy
The sample dataset contains synthetic questions only. Do not commit real customer conversations, personal information, or API keys.

## Citation
Kazbek001. *WhatsApp AI CRM Benchmark*. GitHub repository.

## License
Distributed under the MIT License. See `LICENSE`.
