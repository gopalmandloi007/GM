# utils/file_manager.py
import os
import json
import pandas as pd
from typing import Optional, Any

def ensure_folder(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def ensure_dir(path: str):
    ensure_folder(path)

def read_json_safe(path: str) -> Optional[Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json_safe(path: str, data: Any):
    ensure_folder(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def read_csv_safe(path: str) -> Optional[pd.DataFrame]:
    try:
        if not os.path.exists(path):
            return None
        return pd.read_csv(path)
    except Exception:
        return None

def to_csv_atomic(df: pd.DataFrame, path: str, index=False):
    ensure_folder(os.path.dirname(path))
    tmp = path + ".tmp"
    df.to_csv(tmp, index=index)
    os.replace(tmp, path)

def save_dataframe(path: str, df: pd.DataFrame):
    to_csv_atomic(df, path, index=False)

def save_json_log(folder: str, name: str, data: Any):
    ensure_folder(folder)
    path = os.path.join(folder, f"{name}.json")
    write_json_safe(path, data)
