"""Runs the agent once for each sample brand and saves the results, so the Showcase tab loads instantly.

Run it from this folder with:  .venv\\Scripts\\python.exe make_showcase.py
It uses 3 free Gemini requests per brand.
"""

import json
import sys
import tomllib
from pathlib import Path

from agent import run_audit

SAMPLES = [
    ("Allbirds", "https://www.allbirds.com/", "sustainable sneakers", ["Veja", "Cariuma", "Rothy's"]),
    ("Oatly", "https://www.oatly.com/", "oat milk", ["Califia Farms", "Silk", "Planet Oat"]),
    ("HubSpot", "https://www.hubspot.com/", "CRM software for small businesses", ["Salesforce", "Zoho", "Pipedrive"]),
]

folder = Path(__file__).parent
api_key = tomllib.loads((folder / ".streamlit" / "secrets.toml").read_text())["GEMINI_API_KEY"]
only = sys.argv[1:]  # Optionally name brands to redo just those, e.g. make_showcase.py Oatly

for brand, url, category, competitors in SAMPLES:
    if only and brand not in only:
        continue
    print(f"\n{brand}")
    result = run_audit(api_key, brand, url, category, competitors, on_step=lambda text: print("  " + text))
    path = folder / "showcase" / f"{brand.lower()}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Saved {path.name}")
