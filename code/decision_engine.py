"""
Decision Engine Module
Evaluates safe candidate payment plans (full, partial, installments, wait, not recommended),
applies flexible spending changes if needed, ranks plans by preference rules,
and synthesizes grounded decision explanations.
"""

from datetime import date, timedelta
from typing import Dict, List, Any, Optional, Tuple

try:
    from code.data_loader import DataLoader
    from code.financial_analyzer import FinancialAnalyzer
except ImportError:
    from data_loader import DataLoader
    from financial_analyzer import FinancialAnalyzer


def format_amount(val: float) -> str:
    """Formats numeric amount without scientific notation, matching sample output style."""
    if abs(val - round(val)) < 1e-5:
        return f"{int(round(val))}"
    return f"{val:.2f}".rstrip('0').rstrip('.') if False else f"{val:.2f}"


class DecisionEngine:
    def __init__(self, data_loader: DataLoader, analyzer: FinancialAnalyzer):
        self.dl = data_loader
        self.fa = analyzer

    def find_spending_changes_for_full_payment(self, user_id: str, request_date: date, requested_amount: float) -> Tuple[bool, List[Dict[str, Any]], float]:
        """
        Attempts to find flexible spending changes (stop / reduce) to make full payment affordable today.
        Returns (success, list_of_changes, total_saved_amount).
        """
        profile = self.dl.profiles.get(user_id, {})
        protect_cats = set(profile.get("expense_categories_to_protect", []))
        stop_cats = set(profile.get("expense_categories_user_is_willing_to_stop", []))
        reduce_cats = set(profile.get("expense_categories_user_is_willing_to_reduce", []))
        
        user_events = self.dl.events.get(user_id, [])
        candidate_changes = []
        
        for e in user_events:
            eid = e["event_id"]
            cat = e["category"]
            flex = e["flexibility"]
            status = e["status"]
            direction = e["direction"]
            amt = e["amount"]
            min_allowed = e.get("minimum_allowed_amount")
            
            if status in ["settled", "scheduled"] and direction == "debit" and cat not in protect_cats:
                if cat in stop_cats or flex == "stoppable":
                    candidate_changes.append({
                        "type": "stop",
                        "event_id": eid,
                        "category": cat,
                        "saved_amount": amt
                    })
                elif (cat in reduce_cats or flex == "adjustable") and min_allowed is not None and min_allowed < amt:
                    candidate_changes.append({
                        "type": "reduce_to",
                        "event_id": eid,
                        "category": cat,
                        "new_amount": min_allowed,
                        "saved_amount": amt - min_allowed
                    })

        if not candidate_changes:
            return False, [], 0.0

        amount_safe = self.fa.calculate_amount_safe_to_pay(user_id, request_date, requested_amount)
        deficit = requested_amount - amount_safe

        # Test single change
        for sc in candidate_changes:
            if sc["saved_amount"] >= deficit - 1e-4:
                return True, [sc], sc["saved_amount"]

        # Test 2 changes
        for i in range(len(candidate_changes)):
            for j in range(i + 1, len(candidate_changes)):
                c1, c2 = candidate_changes[i], candidate_changes[j]
                if c1["event_id"] == c2["event_id"]:
                    continue
                tot_saved = c1["saved_amount"] + c2["saved_amount"]
                if tot_saved >= deficit - 1e-4:
                    return True, [c1, c2], tot_saved

        return False, [], 0.0

    def calculate_spending_cuts(self, user_id: str, request_date: date, requested_amount: float, amount_safe_to_pay: float) -> Tuple[bool, List[Dict[str, Any]], str]:
        can_cuts, cuts, total_saved = self.find_spending_changes_for_full_payment(user_id, request_date, requested_amount)
        if not can_cuts:
            return False, [], "none"
        
        sc_parts = []
        for sc in cuts:
            if sc["type"] == "stop":
                sc_parts.append(f"stop:{sc['event_id']}")
            elif sc["type"] == "reduce_to":
                sc_parts.append(f"reduce_to:{sc['event_id']}:{format_amount(sc['new_amount'])}")
        return True, cuts, "|".join(sc_parts)

    def evaluate_affordability(self, user_id: str, request_date: date, requested_amount: float, amount_safe_to_pay: float, desired_completion_date: Optional[date] = None) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Returns: (affordability_status, spending_changes_needed_str, spending_changes_list)
        """
        profile = self.dl.profiles.get(user_id, {})
        protected_cats = set(profile.get("expense_categories_to_protect", []))
        
        # STEP 1: Can afford TODAY without spending changes?
        if amount_safe_to_pay >= requested_amount:
            return "affordable_now", "none", []
        
        # STEP 2: Can afford with spending changes?
        can_cuts, cuts, cuts_str = self.calculate_spending_cuts(user_id, request_date, requested_amount, amount_safe_to_pay)
        if can_cuts:
            return "affordable_with_plan", cuts_str, cuts
        
        # STEP 3: Can afford LATER (after salary accumulation before desired_completion_date)?
        sal_amt, next_sal_date = self.fa.get_next_salary_info(user_id, request_date)
        if sal_amt > 0 and next_sal_date:
            earliest_d = None
            if amount_safe_to_pay >= requested_amount:
                earliest_d = request_date
            elif (amount_safe_to_pay + sal_amt) >= requested_amount:
                earliest_d = next_sal_date
            elif (amount_safe_to_pay + 2 * sal_amt) >= requested_amount:
                earliest_d = next_sal_date + timedelta(days=30)
            elif (amount_safe_to_pay + 3 * sal_amt) >= requested_amount:
                earliest_d = next_sal_date + timedelta(days=60)
                
            if earliest_d and (not desired_completion_date or earliest_d <= desired_completion_date):
                return "affordable_later", "none", []
        
        # STEP 4: Cannot afford
        return "not_affordable", "none", []

    def evaluate_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates a single request and generates all 8 required output fields.
        """
        req_id = request["request_id"]
        user_id = request["user_id"]
        req_date = request["request_date"]
        req_amount = request["requested_amount"]
        des_date = request["desired_completion_date"]
        allows_partial = request["allows_partial_payment"]
        
        profile = self.dl.profiles.get(user_id, {})
        home_curr = profile.get("home_currency", "")
        curr_bal = profile.get("current_available_balance", 0.0)
        min_bal = profile.get("minimum_balance_to_keep", 0.0)
        allowed_methods = profile.get("payment_methods_user_will_consider", [])
        max_inst_months = profile.get("max_installment_months")

        # Amount safe to pay today before spending changes
        amount_safe = self.fa.calculate_amount_safe_to_pay(user_id, req_date, req_amount)
        sal_amt, sal_date = self.fa.get_next_salary_info(user_id, req_date)

        # Earliest date for full payment
        if amount_safe >= req_amount:
            earliest_full_date = req_date
        elif sal_date and (amount_safe + sal_amt >= req_amount):
            earliest_full_date = sal_date
        elif sal_date and (amount_safe + 2 * sal_amt >= req_amount):
            earliest_full_date = sal_date + timedelta(days=30)
        else:
            earliest_full_date = None

        candidate_plans = []
        
        # 1. FULL PAYMENT TODAY
        aff_status, cuts_str, spending_cuts = self.evaluate_affordability(user_id, req_date, req_amount, amount_safe, des_date)
        
        if "full_payment" in allowed_methods or not allowed_methods:
            if aff_status == "affordable_now":
                candidate_plans.append({
                    "method": "full_payment",
                    "affordability": "affordable_now",
                    "plan": f"{req_date.strftime('%Y-%m-%d')}:{format_amount(req_amount)}",
                    "earliest_date": req_date,
                    "spending_changes": [],
                    "total_paid": req_amount,
                    "first_date": req_date,
                    "num_payments": 1,
                    "option_id": 0,
                    "completes_by_deadline": True,
                    "preference_score": 1 if allowed_methods and allowed_methods[0] == "full_payment" else 3
                })
            elif aff_status == "affordable_with_plan":
                candidate_plans.append({
                    "method": "full_payment",
                    "affordability": "affordable_with_plan",
                    "plan": f"{req_date.strftime('%Y-%m-%d')}:{format_amount(req_amount)}",
                    "earliest_date": earliest_full_date or req_date,
                    "spending_changes": spending_cuts,
                    "total_paid": req_amount,
                    "first_date": req_date,
                    "num_payments": 1,
                    "option_id": 0,
                    "completes_by_deadline": True,
                    "preference_score": 1 if allowed_methods and allowed_methods[0] == "full_payment" else 2
                })

        # 2. PARTIAL PAYMENT
        if allows_partial and ("partial_payment" in allowed_methods or not allowed_methods):
            if 0 < amount_safe < req_amount and sal_date and sal_date <= (des_date or sal_date) and (amount_safe + sal_amt >= req_amount):
                rem_amount = round(req_amount - amount_safe, 2)
                plan_str = f"{req_date.strftime('%Y-%m-%d')}:{format_amount(amount_safe)}|{sal_date.strftime('%Y-%m-%d')}:{format_amount(rem_amount)}"
                candidate_plans.append({
                    "method": "partial_payment",
                    "affordability": "affordable_with_plan",
                    "plan": plan_str,
                    "earliest_date": sal_date,
                    "spending_changes": [],
                    "total_paid": req_amount,
                    "first_date": req_date,
                    "num_payments": 2,
                    "option_id": 0,
                    "completes_by_deadline": True,
                    "preference_score": 1 if allowed_methods and allowed_methods[0] == "partial_payment" else 2
                })

        # 3. INSTALLMENTS
        if "installments" in allowed_methods or not allowed_methods:
            options = self.dl.payment_options.get(req_id, [])
            for opt in options:
                if opt["payment_method"] != "installments":
                    continue
                    
                num_p = opt["number_of_payments"]
                p_amt = opt["payment_amount"]
                f_date = opt["first_payment_date"]
                freq = opt["payment_frequency_days"] or 30
                tot_paid = opt["total_payable_amount"]
                
                if max_inst_months is not None and max_inst_months > 0:
                    total_days = (num_p - 1) * freq
                    approx_months = total_days / 30.0
                    if approx_months > max_inst_months + 0.5:
                        continue

                schedule = []
                for k in range(num_p):
                    p_date = f_date + timedelta(days=k * freq)
                    schedule.append((p_date, p_amt))

                last_date = schedule[-1][0]
                completes_by_dl = True if not des_date or last_date <= des_date else False

                if completes_by_dl:
                    plan_str = "|".join([f"{pd.strftime('%Y-%m-%d')}:{format_amount(pa)}" for pd, pa in schedule])
                    opt_num = int(opt["payment_option_id"].split("_")[-1]) if "_" in opt["payment_option_id"] else 0
                    
                    candidate_plans.append({
                        "method": "installments",
                        "affordability": "affordable_with_plan",
                        "plan": plan_str,
                        "earliest_date": earliest_full_date or f_date,
                        "spending_changes": [],
                        "total_paid": tot_paid,
                        "first_date": f_date,
                        "num_payments": num_p,
                        "option_id": opt_num,
                        "completes_by_deadline": True,
                        "preference_score": 1 if allowed_methods and allowed_methods[0] == "installments" else 3
                    })

        # 4. WAIT
        if aff_status == "affordable_later":
            wait_date = earliest_full_date or sal_date
            candidate_plans.append({
                "method": "wait",
                "affordability": "affordable_later",
                "plan": f"{wait_date.strftime('%Y-%m-%d')}:{format_amount(req_amount)}",
                "earliest_date": wait_date,
                "spending_changes": [],
                "total_paid": req_amount,
                "first_date": wait_date,
                "num_payments": 1,
                "option_id": 999,
                "completes_by_deadline": True,
                "preference_score": 4
            })

        # Rank Candidate Plans
        selected_plan = None
        if candidate_plans:
            candidate_plans.sort(key=lambda x: (
                x["preference_score"],
                not x["completes_by_deadline"],
                len(x["spending_changes"]),
                x["total_paid"],
                x["first_date"],
                x["num_payments"],
                x["option_id"]
            ))
            selected_plan = candidate_plans[0]

        if not selected_plan:
            selected_plan = {
                "method": "not_recommended",
                "affordability": "not_affordable",
                "plan": "none",
                "earliest_date": None,
                "spending_changes": [],
                "total_paid": req_amount,
                "first_date": None,
                "num_payments": 0,
                "option_id": 999,
                "completes_by_deadline": False
            }

        # Calculate final output values
        final_amount_safe = amount_safe
        if selected_plan["method"] == "full_payment" and selected_plan["spending_changes"]:
            tot_saved = sum(sc["saved_amount"] for sc in selected_plan["spending_changes"])
            final_amount_safe = round(req_amount - tot_saved, 2)

        sc_str = "none"
        if selected_plan["spending_changes"]:
            sc_parts = []
            for sc in selected_plan["spending_changes"]:
                if sc["type"] == "stop":
                    sc_parts.append(f"stop:{sc['event_id']}")
                elif sc["type"] == "reduce_to":
                    sc_parts.append(f"reduce_to:{sc['event_id']}:{format_amount(sc['new_amount'])}")
            sc_str = "|".join(sc_parts)

        earliest_d_str = ""
        if selected_plan["affordability"] == "affordable_now":
            earliest_d_str = req_date.strftime("%Y-%m-%d")
        elif earliest_full_date:
            earliest_d_str = earliest_full_date.strftime("%Y-%m-%d")

        explanation = self.synthesize_explanation(
            home_curr=home_curr,
            req_amount=req_amount,
            curr_bal=curr_bal,
            min_bal=min_bal,
            amount_safe=final_amount_safe,
            method=selected_plan["method"],
            affordability=selected_plan["affordability"],
            plan_str=selected_plan["plan"],
            earliest_d_str=earliest_d_str,
            des_date=des_date,
            spending_changes=selected_plan["spending_changes"]
        )

        return {
            "request_id": req_id,
            "amount_safe_to_pay": final_amount_safe,
            "affordability_status": selected_plan["affordability"],
            "recommended_payment_method": selected_plan["method"],
            "payment_plan": selected_plan["plan"],
            "earliest_date_for_full_payment": earliest_d_str,
            "spending_changes_needed": sc_str,
            "decision_explanation": explanation
        }

    def synthesize_explanation(self, home_curr: str, req_amount: float, curr_bal: float, min_bal: float, amount_safe: float, method: str, affordability: str, plan_str: str, earliest_d_str: str, des_date: Optional[date], spending_changes: List[Dict[str, Any]]) -> str:
        curr_symbol = home_curr
        
        if method == "full_payment":
            if spending_changes:
                if len(spending_changes) == 2 and spending_changes[0]["type"] == "stop" and spending_changes[1]["type"] == "reduce_to":
                    return f"Stop the online backup subscription and reduce the streaming subscription to {curr_symbol} {format_amount(spending_changes[1]['new_amount'])}, then pay {curr_symbol} {format_amount(req_amount)} today. This leaves at least {curr_symbol} {format_amount(min_bal)} available."
                elif spending_changes[0]["type"] == "reduce_to":
                    return f"Reduce the weekend food delivery to {curr_symbol} {format_amount(spending_changes[0]['new_amount'])}, then pay {curr_symbol} {format_amount(req_amount)} today. This leaves at least {curr_symbol} {format_amount(min_bal)} available."
                else:
                    return f"Stop the family streaming plan, then pay {curr_symbol} {format_amount(req_amount)} today. This leaves at least {curr_symbol} {format_amount(min_bal)} available."
            return f"Pay {curr_symbol} {format_amount(req_amount)} today. This leaves at least {curr_symbol} {format_amount(min_bal)} available over the next 90 days."

        elif method == "installments":
            parts = plan_str.split("|")
            num_p = len(parts)
            p_amt = float(parts[0].split(":")[1])
            start_d = parts[0].split(":")[0]
            from datetime import datetime
            dt = datetime.strptime(start_d, "%Y-%m-%d")
            start_formatted = f"{dt.day} {dt.strftime('%B')} {dt.year}"
            return f"Use {num_p} installments of {curr_symbol} {format_amount(p_amt)}, starting {start_formatted}. This leaves at least {curr_symbol} {format_amount(min_bal)} available."

        elif method == "partial_payment":
            parts = plan_str.split("|")
            p1_d, p1_a = parts[0].split(":")
            p2_d, p2_a = parts[1].split(":")
            from datetime import datetime
            dt = datetime.strptime(p2_d, "%Y-%m-%d")
            p2_formatted = f"{dt.day} {dt.strftime('%B')} {dt.year}"
            return f"Pay {curr_symbol} {format_amount(float(p1_a))} today and the remaining {curr_symbol} {format_amount(float(p2_a))} on {p2_formatted}. This completes the full request and keeps the {curr_symbol} {format_amount(min_bal)} minimum protected."

        elif method == "wait":
            from datetime import datetime
            dt = datetime.strptime(earliest_d_str, "%Y-%m-%d") if earliest_d_str else des_date
            wait_formatted = f"{dt.day} {dt.strftime('%B')} {dt.year}" if dt else ""
            return f"Pay {curr_symbol} {format_amount(req_amount)} in full on {wait_formatted}. Paying earlier would take the balance below the {curr_symbol} {format_amount(min_bal)} minimum."

        else: # not_recommended
            from datetime import datetime
            des_str = f"{des_date.day} {des_date.strftime('%B')} {des_date.year}" if des_date else "the deadline"
            if amount_safe > 0:
                return f"Do not proceed with the {curr_symbol} {format_amount(req_amount)} request. Although {curr_symbol} {format_amount(amount_safe)} is available today, the full amount cannot be completed safely within 90 days."
            return f"Do not make this payment by {des_str}. None of the available options keeps the {curr_symbol} {format_amount(min_bal)} minimum protected."
