"""
Main Entrypoint for Buy or Wait? Financial Decision Agent
Reads dataset/requests.csv, runs financial reconstruction and plan selection,
validates output constraints, and writes output.csv to repository root.
"""

import os
import sys
import pandas as pd
from datetime import datetime

# Ensure sys.path includes code directory
code_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(code_dir)
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from code.data_loader import DataLoader
    from code.financial_analyzer import FinancialAnalyzer
    from code.decision_engine import DecisionEngine
    from code.validator import ContractValidator
except ImportError:
    from data_loader import DataLoader
    from financial_analyzer import FinancialAnalyzer
    from decision_engine import DecisionEngine
    from validator import ContractValidator


def main():
    print("=== HackerRank Orchestrate: Buy or Wait? Financial Decision Agent ===")
    
    # 1. Initialize data pipeline
    dataset_dir = os.path.join(repo_root, "dataset")
    dl = DataLoader(dataset_dir=dataset_dir)
    fa = FinancialAnalyzer(dl)
    de = DecisionEngine(dl, fa)

    # 2. Load requests to evaluate (250 requests)
    requests = dl.get_requests(csv_file="requests.csv")
    print(f"Loaded {len(requests)} evaluation requests from {os.path.join(dataset_dir, 'requests.csv')}.")

    output_rows = []
    validation_failures = 0

    # 3. Process each request
    for i, req in enumerate(requests):
        req_id = req["request_id"]
        pred = de.evaluate_request(req)
        
        # Validate prediction against contract constraints
        errs = ContractValidator.validate_row(pred, req)
        if errs:
            validation_failures += len(errs)
            print(f"WARNING: Validation errors for {req_id}: {errs}")

        output_rows.append({
            "request_id": pred["request_id"],
            "amount_safe_to_pay": pred["amount_safe_to_pay"],
            "affordability_status": pred["affordability_status"],
            "recommended_payment_method": pred["recommended_payment_method"],
            "payment_plan": pred["payment_plan"],
            "earliest_date_for_full_payment": pred["earliest_date_for_full_payment"],
            "spending_changes_needed": pred["spending_changes_needed"],
            "decision_explanation": pred["decision_explanation"]
        })

    # 4. Convert to DataFrame and write output.csv to repo root
    output_df = pd.DataFrame(output_rows, columns=[
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation"
    ])

    output_path = os.path.join(repo_root, "output.csv")
    output_df.to_csv(output_path, index=False)
    
    print(f"\nSuccessfully generated {output_path} with {len(output_df)} rows.")
    print(f"Validation failures: {validation_failures}")
    
    # Verify file row count
    with open(output_path, "r", encoding="utf-8") as f:
        line_count = len(f.readlines())
    print(f"Verified output.csv line count: {line_count} (1 header + 250 data rows).")

if __name__ == "__main__":
    main()
