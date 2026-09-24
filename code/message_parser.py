"""
Message Parser Module
Parses natural language and structured messages to detect payroll updates,
salary date shifts, expense adjustments, and conflict resolutions.
"""

import re
from datetime import date, datetime
from typing import Dict, List, Any, Optional

def parse_date_str(d_str: str) -> Optional[date]:
    try:
        return datetime.strptime(d_str, "%Y-%m-%d").date()
    except Exception:
        return None

class MessageParser:
    @staticmethod
    def parse_user_messages(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parses all messages for a user and returns an overrides dictionary.
        """
        overrides = {
            "salary_overrides": [],      # List of {amount, date, effective_date}
            "salary_date_shifts": {},     # original_date -> new_date
            "rent_multiplier": 1.0,
            "cancelled_events": set(),
            "unconfirmed_items": set(),   # Descriptions/ref numbers to ignore
        }

        # Sort messages by sent_at if available
        sorted_msgs = sorted(messages, key=lambda x: x.get("sent_at", ""))

        for msg in sorted_msgs:
            text = msg.get("message_text", "")
            source = msg.get("source_type", "")
            
            # Check for salary updates
            if source == "employer" or "salary" in text.lower() or "payroll" in text.lower() or "gaji" in text.lower():
                # Unconfirmed bonuses / commissions -> ignore
                if "pending" in text.lower() or "belum disetujui" in text.lower() or "temporary" in text.lower() and "unconfirmed" in text.lower():
                    pass # Rules: do not count pending/unconfirmed credits
                
                # Check salary amount changes
                # IDR / EUR / ZAR / USD / INR amount regex
                amt_match = re.search(r'(?:IDR|EUR|ZAR|USD|INR|\$|€|₹|Rs\.?)\s*([\d,]+(?:\.\d+)?)', text, re.IGNORECASE)
                if not amt_match:
                    amt_match = re.search(r'(?:gaji|salary|pay)(?:\s+\w+){0,3}\s+(?:naik menjadi|is|now|to|resumes on|cycles?)\s*(?:IDR|EUR|ZAR|USD|INR|\$|€|₹|Rs\.?)?\s*([\d,]+(?:\.\d+)?)', text, re.IGNORECASE)

                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
                
                # Check for explicit date replacement
                if "replaces the payroll date" in text.lower() or "expected on" in text.lower() or "berlaku mulai" in text.lower():
                    if date_match:
                        new_d = parse_date_str(date_match.group(1))
                        if new_d:
                            overrides["salary_date_override"] = new_d
                
                if amt_match:
                    try:
                        amt_str = amt_match.group(1).replace(",", "")
                        amt_val = float(amt_str)
                        eff_date = parse_date_str(date_match.group(1)) if date_match else None
                        
                        # Verify it's not a reference number (e.g., EMP-0001 or 42750000)
                        if amt_val > 0:
                            overrides["salary_overrides"].append({
                                "amount": amt_val,
                                "date": eff_date,
                                "raw_text": text
                            })
                    except Exception:
                        pass

            # Check rent price changes
            if "rent" in text.lower() or "lease" in text.lower():
                pct_match = re.search(r'increase[s]?\s+(?:monthly\s+)?rent\s+by\s+(\d+(?:\.\d+)?)%', text, re.IGNORECASE)
                if pct_match:
                    pct = float(pct_match.group(1))
                    overrides["rent_multiplier"] *= (1.0 + pct / 100.0)

            # Check refund initiation (unsettled -> ignore pending credit)
            if "refund" in text.lower() and ("initiated" in text.lower() or "has not reached" in text.lower()):
                # Explicitly do not add to available cash
                pass

        return overrides
