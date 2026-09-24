"""
Data Loader Module
Loads CSV files from dataset/ directory into structured Python data objects.
"""

import os
import sys
import pandas as pd
from datetime import datetime, date
from typing import Dict, List, Any, Optional

try:
    from code.image_extractor import extract_amount_from_image
except ImportError:
    from image_extractor import extract_amount_from_image

def parse_date(d_str: Any) -> Optional[date]:
    """Parse date string YYYY-MM-DD or return None."""
    if not d_str or pd.isna(d_str) or str(d_str).strip() == "":
        return None
    d_str = str(d_str).strip()
    try:
        return datetime.strptime(d_str[:10], "%Y-%m-%d").date()
    except Exception:
        return None

def parse_bool(b_val: Any) -> bool:
    """Parse boolean value from string or bool."""
    if isinstance(b_val, bool):
        return b_val
    if not b_val or pd.isna(b_val):
        return False
    return str(b_val).strip().lower() in ["true", "1", "yes"]

def parse_list(l_str: Any, sep: str = "|") -> List[str]:
    """Parse pipe-separated list string into list of trimmed strings."""
    if not l_str or pd.isna(l_str) or str(l_str).strip() == "":
        return []
    return [x.strip() for x in str(l_str).split(sep) if x.strip()]

def parse_float(f_val: Any, default: float = 0.0) -> float:
    """Parse float safely."""
    if f_val is None or pd.isna(f_val) or str(f_val).strip() == "":
        return default
    try:
        return float(f_val)
    except Exception:
        return default

def parse_int(i_val: Any, default: Optional[int] = None) -> Optional[int]:
    """Parse int safely."""
    if i_val is None or pd.isna(i_val) or str(i_val).strip() == "":
        return default
    try:
        return int(float(i_val))
    except Exception:
        return default


class DataLoader:
    def __init__(self, dataset_dir: str = "dataset"):
        # Resolve dataset_dir relative to repo root if not absolute or missing
        if not os.path.isabs(dataset_dir):
            code_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.dirname(code_dir)
            cand = os.path.join(repo_root, dataset_dir)
            if os.path.exists(cand):
                dataset_dir = cand
            elif not os.path.exists(dataset_dir):
                dataset_dir = cand
                
        self.dataset_dir = dataset_dir
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.events: Dict[str, List[Dict[str, Any]]] = {}
        self.payment_options: Dict[str, List[Dict[str, Any]]] = {}
        self.exchange_rates: Dict[tuple, float] = {}
        self.messages: Dict[str, List[Dict[str, Any]]] = {}
        self.images: Dict[str, Dict[str, Any]] = {}
        self.image_by_event: Dict[str, str] = {}
        self.load_all()

    def load_all(self):
        self.load_images()
        self.load_profiles()
        self.load_events()
        self.load_payment_options()
        self.load_exchange_rates()
        self.load_messages()

    def load_images(self):
        path = os.path.join(self.dataset_dir, "images.csv")
        if not os.path.exists(path):
            return
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            img_id = str(row["image_id"]).strip()
            user_id = str(row["user_id"]).strip() if pd.notna(row["user_id"]) else ""
            req_id = str(row["request_id"]).strip() if pd.notna(row["request_id"]) else ""
            rel_event_id = str(row["related_event_id"]).strip() if pd.notna(row["related_event_id"]) else ""
            
            img_info = {
                "image_id": img_id,
                "user_id": user_id,
                "request_id": req_id,
                "related_event_id": rel_event_id,
                "file_path": os.path.join(self.dataset_dir, "media", "images", f"{img_id}.png")
            }
            self.images[img_id] = img_info
            if rel_event_id:
                self.image_by_event[rel_event_id] = img_id

    def load_profiles(self):
        path = os.path.join(self.dataset_dir, "financial_profiles.csv")
        if not os.path.exists(path):
            return
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            uid = str(row["user_id"]).strip()
            self.profiles[uid] = {
                "user_id": uid,
                "home_currency": str(row["home_currency"]).strip(),
                "current_available_balance": parse_float(row["current_available_balance"]),
                "minimum_balance_to_keep": parse_float(row["minimum_balance_to_keep"]),
                "financial_priorities": parse_list(row.get("financial_priorities")),
                "expense_categories_to_protect": parse_list(row.get("expense_categories_to_protect")),
                "expense_categories_user_is_willing_to_reduce": parse_list(row.get("expense_categories_user_is_willing_to_reduce")),
                "expense_categories_user_is_willing_to_stop": parse_list(row.get("expense_categories_user_is_willing_to_stop")),
                "payment_methods_user_will_consider": parse_list(row.get("payment_methods_user_will_consider")),
                "max_installment_months": parse_int(row.get("max_installment_months"))
            }

    def load_events(self):
        path = os.path.join(self.dataset_dir, "financial_events.csv")
        if not os.path.exists(path):
            return
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            uid = str(row["user_id"]).strip()
            eid = str(row["event_id"]).strip()
            amt_raw = row["amount"]
            
            if pd.isna(amt_raw) or str(amt_raw).strip() == "":
                img_id = self.image_by_event.get(eid)
                if img_id:
                    img_path = self.images[img_id]["file_path"] if img_id in self.images else None
                    amt = extract_amount_from_image(img_id, img_path)
                else:
                    amt = 0.0
            else:
                amt = parse_float(amt_raw)

            event = {
                "event_id": eid,
                "user_id": uid,
                "event_type": str(row["event_type"]).strip() if pd.notna(row["event_type"]) else "",
                "description": str(row["description"]).strip() if pd.notna(row["description"]) else "",
                "category": str(row["category"]).strip() if pd.notna(row["category"]) else "",
                "direction": str(row["direction"]).strip() if pd.notna(row["direction"]) else "",
                "amount": amt,
                "currency": str(row["currency"]).strip() if pd.notna(row["currency"]) else "",
                "event_date": parse_date(row["event_date"]),
                "settlement_date": parse_date(row["settlement_date"]),
                "status": str(row["status"]).strip() if pd.notna(row["status"]) else "",
                "linked_event_id": str(row["linked_event_id"]).strip() if pd.notna(row["linked_event_id"]) else "",
                "flexibility": str(row["flexibility"]).strip() if pd.notna(row["flexibility"]) else "",
                "minimum_allowed_amount": parse_float(row["minimum_allowed_amount"]) if pd.notna(row.get("minimum_allowed_amount")) else None
            }
            if uid not in self.events:
                self.events[uid] = []
            self.events[uid].append(event)

    def load_payment_options(self):
        path = os.path.join(self.dataset_dir, "request_payment_options.csv")
        if not os.path.exists(path):
            return
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            req_id = str(row["request_id"]).strip()
            opt = {
                "payment_option_id": str(row["payment_option_id"]).strip(),
                "request_id": req_id,
                "payment_method": str(row["payment_method"]).strip(),
                "payment_amount": parse_float(row["payment_amount"]),
                "number_of_payments": parse_int(row["number_of_payments"], 1),
                "first_payment_date": parse_date(row["first_payment_date"]),
                "payment_frequency_days": parse_int(row.get("payment_frequency_days"), 0),
                "financing_fee": parse_float(row.get("financing_fee"), 0.0),
                "total_payable_amount": parse_float(row["total_payable_amount"])
            }
            if req_id not in self.payment_options:
                self.payment_options[req_id] = []
            self.payment_options[req_id].append(opt)

    def load_exchange_rates(self):
        path = os.path.join(self.dataset_dir, "exchange_rates.csv")
        if not os.path.exists(path):
            return
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            r_date = parse_date(row["rate_date"])
            fc = str(row["from_currency"]).strip()
            tc = str(row["to_currency"]).strip()
            rate = parse_float(row["rate"], 1.0)
            if r_date:
                self.exchange_rates[(r_date, fc, tc)] = rate

    def convert_currency(self, amount: float, from_curr: str, to_curr: str, rate_date: date) -> float:
        if from_curr == to_curr or amount == 0:
            return amount
        
        if (rate_date, from_curr, to_curr) in self.exchange_rates:
            return amount * self.exchange_rates[(rate_date, from_curr, to_curr)]
        if (rate_date, to_curr, from_curr) in self.exchange_rates:
            return amount / self.exchange_rates[(rate_date, to_curr, from_curr)]
        
        available_dates = sorted(set(d for d, fc, tc in self.exchange_rates.keys() if (fc == from_curr and tc == to_curr) or (fc == to_curr and tc == from_curr)))
        if available_dates:
            closest_date = min(available_dates, key=lambda d: abs((d - rate_date).days))
            if (closest_date, from_curr, to_curr) in self.exchange_rates:
                return amount * self.exchange_rates[(closest_date, from_curr, to_curr)]
            if (closest_date, to_curr, from_curr) in self.exchange_rates:
                return amount / self.exchange_rates[(closest_date, to_curr, from_curr)]

        return amount

    def load_messages(self):
        path = os.path.join(self.dataset_dir, "messages.csv")
        if not os.path.exists(path):
            return
        df = pd.read_csv(path)
        for _, row in df.iterrows():
            uid = str(row["user_id"]).strip()
            msg = {
                "message_id": str(row["message_id"]).strip(),
                "user_id": uid,
                "request_id": str(row["request_id"]).strip() if pd.notna(row["request_id"]) else "",
                "related_event_id": str(row["related_event_id"]).strip() if pd.notna(row["related_event_id"]) else "",
                "sent_at": str(row["sent_at"]).strip() if pd.notna(row["sent_at"]) else "",
                "source_type": str(row["source_type"]).strip() if pd.notna(row["source_type"]) else "",
                "message_text": str(row["message_text"]).strip() if pd.notna(row["message_text"]) else ""
            }
            if uid not in self.messages:
                self.messages[uid] = []
            self.messages[uid].append(msg)

    def get_requests(self, csv_file: str = "requests.csv") -> List[Dict[str, Any]]:
        path = os.path.join(self.dataset_dir, csv_file)
        if not os.path.exists(path):
            code_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.dirname(code_dir)
            cand = os.path.join(repo_root, "dataset", csv_file)
            if os.path.exists(cand):
                path = cand
        if not os.path.exists(path):
            return []
        df = pd.read_csv(path)
        reqs = []
        for _, row in df.iterrows():
            reqs.append({
                "request_id": str(row["request_id"]).strip(),
                "user_id": str(row["user_id"]).strip(),
                "request_date": parse_date(row["request_date"]),
                "request_type": str(row["request_type"]).strip(),
                "requested_amount": parse_float(row["requested_amount"]),
                "desired_completion_date": parse_date(row["desired_completion_date"]),
                "allows_partial_payment": parse_bool(row["allows_partial_payment"]),
                "request_text": str(row["request_text"]).strip() if pd.notna(row["request_text"]) else ""
            })
        return reqs
