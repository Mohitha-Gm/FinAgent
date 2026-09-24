"""
Evaluation Module
Runs comparison of output predictions against dataset/sample_requests.csv (25 solved examples).
Produces comparison table and breakdown of matches and mismatches.
"""

import os
import sys
import pandas as pd

# Add repo root and code dir to sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
code_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

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


def run_evaluation():
    print("=== HackerRank Orchestrate: Evaluation against dataset/sample_requests.csv ===")
    
    dataset_dir = os.path.join(repo_root, "dataset")
    dl = DataLoader(dataset_dir=dataset_dir)
    fa = FinancialAnalyzer(dl)
    de = DecisionEngine(dl, fa)

    sample_reqs = dl.get_requests(csv_file="sample_requests.csv")
    sample_df = pd.read_csv(os.path.join(dataset_dir, "sample_requests.csv"))

    if not sample_reqs:
        print("ERROR: Could not load sample_requests.csv!")
        return

    print(f"Loaded {len(sample_reqs)} sample requests for comparison.\n")

    results = []
    all_3_matches = 0

    for req in sample_reqs:
        req_id = req["request_id"]
        pred = de.evaluate_request(req)
        target = sample_df[sample_df["request_id"] == req_id].iloc[0]

        p_amt = float(pred["amount_safe_to_pay"])
        e_amt = float(target["amount_safe_to_pay"])
        amt_match = abs(p_amt - e_amt) < 0.05

        p_stat = str(pred["affordability_status"]).strip()
        e_stat = str(target["affordability_status"]).strip()
        stat_match = (p_stat == e_stat)

        p_meth = str(pred["recommended_payment_method"]).strip()
        e_meth = str(target["recommended_payment_method"]).strip()
        meth_match = (p_meth == e_meth)

        is_all_3 = amt_match and stat_match and meth_match
        if is_all_3:
            all_3_matches += 1

        results.append({
            "request_id": req_id,
            "your_amount": p_amt,
            "expected_amount": e_amt,
            "amt_match": "YES" if amt_match else "NO",
            "your_status": p_stat,
            "expected_status": e_stat,
            "stat_match": "YES" if stat_match else "NO",
            "your_method": p_meth,
            "expected_method": e_meth,
            "meth_match": "YES" if meth_match else "NO",
            "all_3_match": "YES" if is_all_3 else "NO"
        })

    # Print Table
    header = f"{'request_id':<12} | {'your_amount':<12} | {'exp_amount':<12} | {'amt':<3} | {'your_status':<20} | {'exp_status':<20} | {'stat':<3} | {'your_method':<15} | {'exp_method':<15} | {'meth':<3} | {'all_3':<5}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(f"{r['request_id']:<12} | {r['your_amount']:<12.2f} | {r['expected_amount']:<12.2f} | {r['amt_match']:<3} | {r['your_status']:<20} | {r['expected_status']:<20} | {r['stat_match']:<3} | {r['your_method']:<15} | {r['expected_method']:<15} | {r['meth_match']:<3} | {r['all_3_match']:<5}")

    print("\n================ SUMMARY ================")
    print(f"Total Sample Requests Compared  : {len(sample_reqs)}")
    print(f"Match on Recommended Payment Method: {sum(1 for r in results if r['meth_match']=='YES')}/25 ({sum(1 for r in results if r['meth_match']=='YES')/25*100:.1f}%)")
    print(f"Match on Affordability Status      : {sum(1 for r in results if r['stat_match']=='YES')}/25 ({sum(1 for r in results if r['stat_match']=='YES')/25*100:.1f}%)")
    print(f"Match on Amount Safe to Pay        : {sum(1 for r in results if r['amt_match']=='YES')}/25 ({sum(1 for r in results if r['amt_match']=='YES')/25*100:.1f}%)")
    print(f"Match on ALL 3 Fields              : {all_3_matches}/25 ({all_3_matches/25*100:.1f}%)")


if __name__ == "__main__":
    run_evaluation()
