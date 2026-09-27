# FinAgent: AI-Powered Financial Decision & Purchase Affordability Engine

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/Architecture-Modular%20Decision%20Engine-purple.svg)](#system-architecture)

**FinAgent** is an intelligent, autonomous financial decision system that evaluates personal purchase affordability, forecasts future cash flows, and recommends optimal payment strategies. 

Rather than relying purely on static bank balances, FinAgent reconstructs a user's multi-currency financial position by combining confirmed income, recurring commitments, pending debits, user-defined safety reserves, and unstructured evidence (such as receipt images and contextual messages).

---

## Key Features

- **Multi-Horizon Cash Flow Forecasting (90-Day)**: Conservatively projects day-by-day account balances, incorporating confirmed salary dates, pending obligations, and scheduled recurring debits across global currencies (USD, EUR, INR, ZAR, IDR).
- **Personalized Safety Constraints**: Strictly prevents account balances from falling below the user's custom `minimum_balance_to_keep`, preserving essential liquidity reserves at all times.
- **Smart Payment Optimization**: Automatically explores and evaluates available payment structures:
  - **Full Payment**: Instant settlement if immediate funds are safely available.
  - **Installment Plans**: Feasibility screening of seller-provided installment options against monthly cash flow headroom.
  - **Partial Payments**: Structured two-stage payment plans (immediate down payment + balance on safe projected date).
  - **Wait Recommendation**: Identifies the earliest safe date for one-time full settlement.
- **Discretionary Spending Adjustments**: Suggests surgical, non-disruptive spending interventions (`stop` or `reduce_to`) on flexible categories to make critical purchases affordable without compromising essentials.
- **Multimodal & Contextual Evidence Ingestion**:
  - **OCR Receipt Extractor**: Recovers missing financial event figures from invoices, bills, and payment receipts.
  - **Natural Language Message Parser**: Handles real-time amendments such as salary raises, rent changes, or delayed payouts.
- **Auditable & Explainable AI**: Produces grounded, human-readable rationales citing concrete financial facts, dates, and balance projections.

---

## System Architecture

```
                                  ┌─────────────────────────────┐
                                  │   Raw Inputs & Profiles     │
                                  │ (CSV Data, OCR, Messages)   │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │         Data Loader         │
                                  │   (code/data_loader.py)     │
                                  └──────────────┬──────────────┘
                                                 │
                        ┌────────────────────────┴────────────────────────┐
                        ▼                                                 ▼
        ┌───────────────────────────────┐                 ┌───────────────────────────────┐
        │     Image Extractor (OCR)     │                 │        Message Parser         │
        │  (code/image_extractor.py)    │                 │   (code/message_parser.py)    │
        └───────────────┬───────────────┘                 └───────────────┬───────────────┘
                        │                                                 │
                        └────────────────────────┬────────────────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │     Financial Analyzer      │
                                  │ (code/financial_analyzer.py)│
                                  │  - 90-Day Cash Flow Proj.   │
                                  │  - Safe Today Amount Calc   │
                                  │  - FX Conversion (5 Currs)  │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │       Decision Engine       │
                                  │  (code/decision_engine.py)  │
                                  │  - Installment Evaluation   │
                                  │  - Spending Cut Optimizer   │
                                  │  - Grounded Explanations    │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │     Contract Validator      │
                                  │     (code/validator.py)     │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │         output.csv          │
                                  │    (Predictions & Plans)    │
                                  └─────────────────────────────┘
```

### Module Breakdown

| Module | Location | Purpose |
|---|---|---|
| **Pipeline Runner** | [`code/main.py`](code/main.py) | Primary entrypoint: orchestrates ingestion, analysis, decision logic, and output export. |
| **Data Loader** | [`code/data_loader.py`](code/data_loader.py) | Ingests structured profiles, financial events, exchange rates, and payment options. |
| **Image Extractor** | [`code/image_extractor.py`](code/image_extractor.py) | Extracts values from financial receipt/bill images using OCR and heuristic fallback rules. |
| **Message Parser** | [`code/message_parser.py`](code/message_parser.py) | Parses contextual natural-language messages to detect salary revisions, rent increases, or transaction status. |
| **Financial Analyzer** | [`code/financial_analyzer.py`](code/financial_analyzer.py) | Simulates liquidity timeline over a 90-day forecast window, accounting for minimum safety balances. |
| **Decision Engine** | [`code/decision_engine.py`](code/decision_engine.py) | Selects optimal payment routes (full, installment, partial, wait) and computes spending changes. |
| **Validator** | [`code/validator.py`](code/validator.py) | Validates all output fields against schema bounds, balance constraints, and financial invariants. |

---

## Decision Taxonomy

FinAgent classifies every purchase request into deterministic, explainable categories:

### 1. Affordability Status (`affordability_status`)
- `affordable_now`: The requested amount can be settled in full on the request date without violating minimum balances.
- `affordable_with_plan`: The purchase is feasible either via an approved installment option, a 2-stage partial payment schedule, or by cutting non-essential flexible spending.
- `affordable_later`: The user cannot safely proceed today, but confirmed future cash inflows (e.g. salary) make it affordable by a specific future date.
- `not_affordable`: The purchase cannot be safely serviced within the forecast horizon without breaching the user's safety balance.

### 2. Recommended Payment Method (`recommended_payment_method`)
- `full_payment`: Pay 100% of the purchase amount immediately.
- `installments`: Use a designated seller financing / EMI plan matching the user's installment preferences.
- `partial_payment`: Pay the safe amount today, followed by the remaining balance on the projected safe date.
- `wait`: Defer the purchase until the projected safe full-payment date.
- `not_recommended`: Reject the purchase due to financial shortfall or unacceptable liquidity risk.

---

## Repository Structure

```text
.
├── code/
│   ├── main.py                  # Main execution entrypoint
│   ├── data_loader.py           # Multi-table dataset parser
│   ├── financial_analyzer.py    # Cash flow engine & balance projector
│   ├── decision_engine.py       # Plan selector & explanation generator
│   ├── image_extractor.py       # OCR receipt extractor
│   ├── message_parser.py        # Natural language context parser
│   ├── validator.py             # Schema & invariant validator
│   ├── requirements.txt         # Project dependencies
│   ├── README.md                # Code package guide
│   └── evaluation/
│       ├── main.py              # Test benchmark script
│       └── usage_report.md      # Performance & cost audit
├── dataset/                     # Financial profiles, events, and request inputs
├── output.csv                   # Generated predictions and decision plans
└── README.md                    # Project documentation
```

---

## Getting Started

### Prerequisites

- Python 3.9 or higher (tested up to Python 3.13)
- `pip` package manager

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Mohitha-Gm/FinAgent.git
   cd FinAgent
   ```

2. **Create and activate a virtual environment (recommended):**
   ```bash
   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate

   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```bash
   pip install -r code/requirements.txt
   ```

---

## Usage

### Run the Decision Pipeline

To process all purchase requests, project cash flows, and generate the final `output.csv`:

```bash
python code/main.py
```

### Run the Evaluation Benchmark

To benchmark the decision pipeline against known reference samples:

```bash
python code/evaluation/main.py
```

---

## Output Data Contract

The pipeline outputs `output.csv` with the following schema:

| Column | Type | Description |
|---|---|---|
| `request_id` | String | Unique identifier of the evaluated purchase request. |
| `amount_safe_to_pay` | Float | Maximum amount safe to disburse today without breaching safety reserves. |
| `affordability_status` | Enum | `affordable_now`, `affordable_with_plan`, `affordable_later`, or `not_affordable`. |
| `recommended_payment_method` | Enum | `full_payment`, `partial_payment`, `installments`, `wait`, or `not_recommended`. |
| `payment_plan` | String | Chronological payment schedule (`YYYY-MM-DD:amount\|...`) or `none`. |
| `earliest_date_for_full_payment`| Date / String | Earliest conservative date a 100% lump-sum payment is safe (empty if unachievable). |
| `spending_changes_needed` | String | Up to 3 discretionary reductions (`stop:<id>` or `reduce_to:<id>:<amount>`), or `none`. |
| `decision_explanation` | String | Grounded natural language summary articulating the reasoning and financial facts. |

---

## Technical Highlights & Design Principles

1. **Conservative Financial Grounding**: Pending inflows, unrealized assets, or potential bonuses are strictly excluded until settled. Debits are reserved immediately.
2. **Deterministic Constraint Satisfaction**: Solves payment schedules under hard balance constraints ($Balance_t \ge MinimumBalance$) rather than unconstrained heuristics.
3. **Currency Agnostic**: Automatically standardizes foreign transactions against local account currencies using settlement-dated foreign exchange rates.
4. **Resilient Multimodal Handling**: Recovers missing transaction quantities from image receipts with OCR and robust statistical fallbacks.
