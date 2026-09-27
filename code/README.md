# FinAgent — Core Engine & Architecture

A modular AI financial decision agent that evaluates user financial requests, reconstructs available balances and recurring cashflows, handles foreign currency conversion, OCR receipt extraction, message updates, spending reduction/stop options, and produces verified payment plans.

---

## 1. Directory & Code Architecture

```text
code/
├── main.py                      # Main entrypoint: orchestrates loading, predicting, validating, and writing output.csv
├── data_loader.py               # Data parser for CSVs (profiles, events, options, rates, messages, images)
├── image_extractor.py           # OCR & fallback reader for blank financial event image receipts
├── message_parser.py            # Interprets natural language updates from messages.csv (salary changes, rent revisions)
├── financial_analyzer.py        # 90-day balance forecaster, cashflow engine, & safety checker
├── decision_engine.py           # Plan generator, spending change selector, preference ranker, & explanation synthesizer
├── validator.py                 # Contract validator checking output schema & financial constraints
├── evaluation/
│   ├── main.py                  # Evaluation benchmark testing pipeline against dataset/sample_requests.csv
│   └── usage_report.md          # Token usage and model cost summary
└── README.md                    # Setup and execution guide
```

---

## 2. Requirements & Setup

- Python 3.9+ (Tested on Python 3.13)
- Required Python libraries: `pandas`, `pillow`, `opencv-python`

Install dependencies:

```bash
pip install pandas pillow opencv-python
```

---

## 3. How to Run

To run the complete pipeline and generate `output.csv` in the repository root:

```bash
python code/main.py
```

To run evaluation benchmarks against `dataset/sample_requests.csv`:

```bash
python code/evaluation/main.py
```

---

## 4. Output Specification

The system generates `output.csv` in the repository root with the following 8 columns:

1. `request_id`
2. `amount_safe_to_pay`
3. `affordability_status` (`affordable_now`, `affordable_with_plan`, `affordable_later`, `not_affordable`)
4. `recommended_payment_method` (`full_payment`, `partial_payment`, `installments`, `wait`, `not_recommended`)
5. `payment_plan` (`YYYY-MM-DD:amount|...` or `none`)
6. `earliest_date_for_full_payment`
7. `spending_changes_needed` (`none` or `stop:<event_id>|reduce_to:<event_id>:<new_amount>`)
8. `decision_explanation` (1-3 grounded sentences)
