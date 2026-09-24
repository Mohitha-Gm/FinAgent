"""
Validator Module
Validates generated predictions against all HackerRank Orchestrate contract rules.
"""

from datetime import datetime
from typing import Dict, List, Any, Tuple

VALID_AFFORDABILITY = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
VALID_METHODS = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}

class ContractValidator:
    @staticmethod
    def validate_row(row: Dict[str, Any], request: Dict[str, Any]) -> List[str]:
        """
        Validates a single prediction output row against problem constraints.
        Returns a list of error message strings (empty if valid).
        """
        errors = []
        req_id = row.get("request_id")
        req_amount = request.get("requested_amount", 0.0)
        req_date = request.get("request_date")
        allows_partial = request.get("allows_partial_payment", False)
        
        # 1. Check amount_safe_to_pay
        amount_safe = row.get("amount_safe_to_pay", -1.0)
        if amount_safe < 0 or amount_safe > req_amount + 1e-4:
            errors.append(f"[{req_id}] amount_safe_to_pay ({amount_safe}) outside [0, {req_amount}]")

        # 2. Check enum fields
        affordability = row.get("affordability_status")
        if affordability not in VALID_AFFORDABILITY:
            errors.append(f"[{req_id}] Invalid affordability_status: {affordability}")

        method = row.get("recommended_payment_method")
        if method not in VALID_METHODS:
            errors.append(f"[{req_id}] Invalid recommended_payment_method: {method}")

        # 3. Check earliest_date_for_full_payment for affordable_now
        earliest_date = row.get("earliest_date_for_full_payment")
        if affordability == "affordable_now":
            req_d_str = req_date.strftime("%Y-%m-%d") if req_date else ""
            if earliest_date != req_d_str:
                errors.append(f"[{req_id}] affordable_now requires earliest_date_for_full_payment == request_date ({req_d_str}), got '{earliest_date}'")

        # 4. Check partial_payment rules
        plan_str = str(row.get("payment_plan", ""))
        if method == "partial_payment":
            if not allows_partial:
                errors.append(f"[{req_id}] recommended partial_payment but allows_partial_payment is False")
            if affordability != "affordable_with_plan":
                errors.append(f"[{req_id}] partial_payment requires affordability_status == 'affordable_with_plan', got '{affordability}'")
            
            parts = plan_str.split("|")
            if len(parts) != 2:
                errors.append(f"[{req_id}] partial_payment plan must have exactly 2 payments, got {len(parts)}: '{plan_str}'")
            else:
                try:
                    p1_d, p1_a = parts[0].split(":")
                    p2_d, p2_a = parts[1].split(":")
                    total_p = float(p1_a) + float(p2_a)
                    if abs(total_p - req_amount) > 0.05:
                        errors.append(f"[{req_id}] partial_payment sum ({total_p}) does not match requested_amount ({req_amount})")
                    if abs(float(p1_a) - amount_safe) > 0.05:
                        errors.append(f"[{req_id}] partial_payment first payment ({p1_a}) does not match amount_safe_to_pay ({amount_safe})")
                except Exception as e:
                    errors.append(f"[{req_id}] Malformed partial_payment plan: '{plan_str}' ({e})")

        # 5. Check spending_changes_needed
        sc_str = str(row.get("spending_changes_needed", ""))
        if sc_str != "none":
            changes = sc_str.split("|")
            if len(changes) > 3:
                errors.append(f"[{req_id}] Maximum 3 spending changes allowed, got {len(changes)}")
            stopped_eids = set()
            reduced_eids = set()
            for c in changes:
                c_parts = c.split(":")
                if c_parts[0] == "stop" and len(c_parts) == 2:
                    stopped_eids.add(c_parts[1])
                elif c_parts[0] == "reduce_to" and len(c_parts) == 3:
                    reduced_eids.add(c_parts[1])
                else:
                    errors.append(f"[{req_id}] Malformed spending change entry: '{c}'")
            if stopped_eids.intersection(reduced_eids):
                errors.append(f"[{req_id}] Cannot stop and reduce same event ID: {stopped_eids.intersection(reduced_eids)}")

        # 6. Check decision_explanation
        explanation = str(row.get("decision_explanation", ""))
        if not explanation or len(explanation.strip()) < 10:
            errors.append(f"[{req_id}] Missing or too short decision_explanation: '{explanation}'")

        return errors
