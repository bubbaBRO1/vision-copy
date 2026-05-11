"""Stage 14: Blockchain / Wallet Detection — find crypto addresses in image text and look them up."""
import re
from typing import Any

try:
    import requests as _requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

# Regex patterns for common wallet formats
_PATTERNS = {
    "bitcoin": re.compile(r"\b(bc1[a-zA-HJ-NP-Z0-9]{25,39}|[13][a-zA-HJ-NP-Z0-9]{25,34})\b"),
    "ethereum": re.compile(r"\b0x[a-fA-F0-9]{40}\b"),
    "monero": re.compile(r"\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b"),
    "litecoin": re.compile(r"\b[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}\b"),
    "dogecoin": re.compile(r"\bD[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}\b"),
}


def _lookup_bitcoin(address: str, session) -> dict:
    try:
        r = session.get(f"https://blockchain.info/rawaddr/{address}?limit=0", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return {
                "balance_btc": d.get("final_balance", 0) / 1e8,
                "total_received_btc": d.get("total_received", 0) / 1e8,
                "tx_count": d.get("n_tx", 0),
            }
    except Exception:
        pass
    return {}


def _lookup_ethereum(address: str, session) -> dict:
    try:
        r = session.get(
            f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest",
            timeout=10,
        )
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "1":
                balance_eth = int(d["result"]) / 1e18
                return {"balance_eth": round(balance_eth, 6)}
    except Exception:
        pass
    return {}


def analyze(image_path: str) -> dict[str, Any]:
    result: dict = {"stage": "blockchain", "wallets": [], "summary": {}}

    if not REQUESTS_OK:
        result["skipped"] = "requests not installed"
        return result

    import os
    sidecar = image_path + ".ocr.txt"
    raw_text = ""
    if os.path.exists(sidecar):
        with open(sidecar) as f:
            raw_text = f.read()

    if not raw_text:
        result["skipped"] = "No OCR text available"
        return result

    session = _requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 VisionOSINT/1.0"

    wallets = []
    for chain, pattern in _PATTERNS.items():
        for match in pattern.finditer(raw_text):
            address = match.group(0)
            entry: dict = {"chain": chain, "address": address}
            if chain == "bitcoin":
                entry.update(_lookup_bitcoin(address, session))
            elif chain == "ethereum":
                entry.update(_lookup_ethereum(address, session))
            wallets.append(entry)

    result["wallets"] = wallets
    result["summary"] = {
        "total_found": len(wallets),
        "chains": list({w["chain"] for w in wallets}),
    }
    return result
