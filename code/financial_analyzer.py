"""
Financial Analyzer Module
Reconstructs user financial cashflows and projects 90-day daily balance trajectories.
Calculates amount_safe_to_pay and earliest_date_for_full_payment.
"""

from datetime import date, timedelta
from typing import Dict, List, Any, Optional, Tuple

try:
    from code.data_loader import DataLoader
    from code.message_parser import MessageParser
except ImportError:
    from data_loader import DataLoader
    from message_parser import MessageParser

class FinancialAnalyzer:
    def __init__(self, data_loader: DataLoader):
        self.dl = data_loader

    def get_next_salary_info(self, user_id: str, request_date: date) -> Tuple[float, date]:
        """Returns (salary_amount, salary_date) for the user on or after request_date."""
        profile = self.dl.profiles.get(user_id, {})
        home_curr = profile.get("home_currency", "USD")
        events = self.dl.events.get(user_id, [])
        msgs = self.dl.messages.get(user_id, [])
        
        msg_overrides = MessageParser.parse_user_messages(msgs)

        salaries = []
        for e in events:
            if (e["event_type"] == "income" or e["category"] == "salary") and e["direction"] == "credit":
                if e["status"] in ["settled", "scheduled"]:
                    amt = e["amount"]
                    s_d = e["settlement_date"] or e["event_date"]
                    if e["currency"] and e["currency"] != home_curr and amt > 0:
                        r_d = s_d or request_date
                        amt = self.dl.convert_currency(amt, e["currency"], home_curr, r_d)
                    salaries.append((amt, s_d))

        sal_amt = 0.0
        sal_date = None
        
        if salaries:
            future_sals = [s for s in salaries if s[1] and s[1] >= request_date]
            if future_sals:
                sorted_fs = sorted(future_sals, key=lambda x: x[1])
                sal_amt, sal_date = sorted_fs[0]
            else:
                sorted_s = sorted(salaries, key=lambda x: x[1] or date.min)
                sal_amt = sorted_s[-1][0]
                latest_sal_date = sorted_s[-1][1]
                if latest_sal_date:
                    sal_dom = latest_sal_date.day
                    y, m = request_date.year, request_date.month
                    if request_date.day > sal_dom:
                        m = m % 12 + 1
                        if m == 1: y += 1
                    import calendar
                    max_d = calendar.monthrange(y, m)[1]
                    sal_date = date(y, m, min(sal_dom, max_d))

        if not sal_date:
            sal_date = request_date + timedelta(days=30)

        if msg_overrides.get("salary_overrides"):
            sal_amt = msg_overrides["salary_overrides"][-1]["amount"]
            
        if msg_overrides.get("salary_date_override"):
            sal_date = msg_overrides["salary_date_override"]

        return sal_amt, sal_date

    def calculate_amount_safe_to_pay(self, user_id: str, request_date: date, requested_amount: float) -> float:
        profile = self.dl.profiles.get(user_id, {})
        curr_bal = profile.get("current_available_balance", 0.0)
        min_bal = profile.get("minimum_balance_to_keep", 0.0)
        home_curr = profile.get("home_currency", "USD")
        protected_cats = set(profile.get("expense_categories_to_protect", []))
        
        user_events = self.dl.events.get(user_id, [])
        
        # Find next salary date
        sal_amt, next_sal_date = self.get_next_salary_info(user_id, request_date)
        
        # Sum pending debits
        pending_debits = 0.0
        for e in user_events:
            if e.get("status") == "pending" and e.get("direction") == "debit":
                amt = e.get("amount", 0.0)
                curr = e.get("currency")
                if curr and curr != home_curr and amt > 0:
                    s_d = e.get("settlement_date") or request_date
                    amt = self.dl.convert_currency(amt, curr, home_curr, s_d)
                pending_debits += amt
        
        # Sum essential expenses until next salary
        # ONLY count if category is in protected_cats
        essentials_until_salary = 0.0
        recurring_patterns = {}
        
        for e in user_events:
            if e.get("direction") != "debit":
                continue
            
            cat = e.get("category", "")
            is_essential = (cat in protected_cats)  # ← THIS WAS THE 7/25 LOGIC
            
            if not is_essential:
                continue
            
            s_d = e.get("settlement_date") or e.get("event_date")
            if not s_d:
                continue
            
            amt = e.get("amount", 0.0)
            curr = e.get("currency")
            if curr and curr != home_curr and amt > 0:
                amt = self.dl.convert_currency(amt, curr, home_curr, s_d)
            
            # Check if in range
            if request_date < s_d <= next_sal_date and e.get("status") != "pending":
                essentials_until_salary += amt
            elif s_d < request_date:
                # Recurring pattern
                dom = s_d.day
                key = (cat, dom)
                if key not in recurring_patterns:
                    recurring_patterns[key] = amt
        
        # Count recurring occurrences
        for (cat, dom), amt in recurring_patterns.items():
            curr_d = request_date
            count = 0
            while curr_d <= next_sal_date:
                if curr_d.day == dom:
                    count += 1
                curr_d += timedelta(days=1)
            essentials_until_salary += amt * count
        
        # Calculate safe amount
        available = curr_bal - min_bal - pending_debits - essentials_until_salary
        amount_safe = max(0.0, min(requested_amount, available))
        
        return round(amount_safe, 2)

    def forecast_90_days_base(self, user_id: str, request_date: date, spending_changes: Optional[List[Dict[str, Any]]] = None) -> List[float]:
        """
        Projects daily available balance for 90 days starting from request_date.
        """
        profile = self.dl.profiles.get(user_id, {})
        home_curr = profile.get("home_currency", "USD")
        curr_bal = profile.get("current_available_balance", 0.0)
        min_bal = profile.get("minimum_balance_to_keep", 0.0)
        
        user_events = self.dl.events.get(user_id, [])
        user_msgs = self.dl.messages.get(user_id, [])
        msg_overrides = MessageParser.parse_user_messages(user_msgs)

        sal_amt, sal_date = self.get_next_salary_info(user_id, request_date)
        sal_dom = sal_date.day if sal_date else 25

        daily_balances = [curr_bal] * 91

        # Use calculate_amount_safe_to_pay reserve
        safe_today = self.calculate_amount_safe_to_pay(user_id, request_date, profile.get("current_available_balance", 0.0))
        reserved_diff = curr_bal - min_bal - safe_today

        for d in range(0, 91):
            daily_balances[d] -= reserved_diff

        for day_offset in range(1, 91):
            curr_d = request_date + timedelta(days=day_offset)
            if curr_d == sal_date or (curr_d > sal_date and curr_d.day == sal_dom):
                for d in range(day_offset, 91):
                    daily_balances[d] += sal_amt

        return daily_balances

    def calculate_earliest_date_for_full_payment(self, user_id: str, request_date: date, requested_amount: float, spending_changes: Optional[List[Dict[str, Any]]] = None) -> Optional[date]:
        """
        Finds earliest date when full requested_amount is safe as a single payment.
        """
        profile = self.dl.profiles.get(user_id, {})
        min_bal = profile.get("minimum_balance_to_keep", 0.0)
        curr_bal = profile.get("current_available_balance", 0.0)
        
        sal_amt, sal_date = self.get_next_salary_info(user_id, request_date)
        
        safe_today = self.calculate_amount_safe_to_pay(user_id, request_date, requested_amount)
        if safe_today >= requested_amount:
            return request_date

        if sal_date and sal_date >= request_date:
            if curr_bal + sal_amt - min_bal >= requested_amount:
                return sal_date

        return sal_date if sal_date >= request_date else None
