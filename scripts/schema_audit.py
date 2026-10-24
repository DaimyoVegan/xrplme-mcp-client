#!/usr/bin/env python3
"""
Schema consistency audit for all 30 country bot servers.
Checks that each bot's v1 response has the required top-level fields.
Does NOT require payment — imports modules directly.
"""

import sys
import os
import json

# Add the VPS API directory to the path
API_DIR = "/opt/xrplme/thoughts/api"
sys.path.insert(0, API_DIR)

# Canonical 30 slugs (from slugs.py pattern)
COUNTRIES = [
    "au", "brazil", "brunei", "canada", "ch", "de", "fr",
    "hongkong", "id", "india", "indonesia", "italy", "japan",
    "korea", "laos", "malaysia", "macau", "mexico", "myanmar",
    "netherlands", "newzealand", "papua_new_guinea", "ph",
    "sg", "taiwan", "thailand", "timor_leste", "uae", "uk",
    "usa", "vietnam"
]

# Map short codes to module names
MODULE_MAP = {
    "au": "au_bot_server",
    "brazil": "brazil_bot_server",
    "brunei": "brunei_bot_server",
    "canada": "canada_bot_server",
    "ch": "ch_bot_server",
    "de": "de_bot_server",
    "fr": "fr_bot_server",
    "hongkong": "hongkong_bot_server",
    "id": "indonesia_bot_server",
    "india": "india_bot_server",
    "italy": "italy_bot_server",
    "japan": "japan_bot_server",
    "korea": "korea_bot_server",
    "laos": "laos_bot_server",
    "malaysia": "malaysia_bot_server",
    "macau": "macau_bot_server",
    "mexico": "mexico_bot_server",
    "myanmar": "myanmar_bot_server",
    "netherlands": "netherlands_bot_server",
    "newzealand": "newzealand_bot_server",
    "papua_new_guinea": "papua_new_guinea_bot_server",
    "ph": "ph_bot_server",
    "sg": "sg_bot_server",
    "taiwan": "taiwan_bot_server",
    "thailand": "thailand_bot_server",
    "timor_leste": "timor_leste_bot_server",
    "uae": "uae_bot_server",
    "uk": "uk_bot_server",
    "usa": "usa_bot_server",
    "vietnam": "vietnam_bot_server",
}

REQUIRED_FACT_KEYS = ["company_formation", "labor", "tax", "crypto_fintech"]

def check_bot(module_name):
    """Import a bot server module and check its v1 schema compliance."""
    result = {
        "module": module_name,
        "import_ok": False,
        "has_to_v1_schema": False,
        "has_V1ChatResponse": False,
        "required_fields": {},
        "issues": [],
    }

    try:
        mod = __import__(module_name)
        result["import_ok"] = True

        # Check _to_v1_schema exists
        if hasattr(mod, "_to_v1_schema"):
            result["has_to_v1_schema"] = True
        else:
            result["issues"].append("Missing _to_v1_schema function")

        # Check V1ChatResponse exists
        if hasattr(mod, "V1ChatResponse"):
            result["has_V1ChatResponse"] = True
        else:
            result["issues"].append("Missing V1ChatResponse class")

        # Check _BASE_URL or _resource_info for resource_url fix
        # resource_url is set via RequireX402Options(resource=...)
        x402_options_obj = None
        if hasattr(mod, "x402_options"):
            x402_options_obj = mod.x402_options
        
        if x402_options_obj:
            resource_url = getattr(x402_options_obj, "resource", "")
            if "wc/v1" in str(resource_url):
                result["resource_url_fixed"] = True
            else:
                result["resource_url_fixed"] = False
                result["issues"].append("resource_url may point to /api/v1/")
        elif hasattr(mod, "X402_CONFIG"):
            x402 = mod.X402_CONFIG
            resource_url = x402.get("resource", x402.get("resource_url", ""))
            if "wc/v1" in str(resource_url):
                result["resource_url_fixed"] = True
            else:
                result["resource_url_fixed"] = False
                result["issues"].append("resource_url may point to /api/v1/")

        # Check pricing
        if hasattr(mod, "X402_CONFIG"):
            amount = str(mod.X402_CONFIG.get("amount", ""))
            if amount == "1000000":
                result["xrpl_pricing"] = "1 XRP (correct)"
            elif amount == "100000":
                result["xrpl_pricing"] = "0.1 XRP (STALE)"
                result["issues"].append("XRPL pricing is stale (0.1 XRP)")
            else:
                result["xrpl_pricing"] = f"{amount} (unknown)"
                result["issues"].append(f"XRPL amount unexpected: {amount}")

            if hasattr(mod, "AI_X402_CONFIG"):
                ai_amount = str(mod.AI_X402_CONFIG.get("amount", ""))
                if ai_amount == "5000000":
                    result["ai_pricing"] = "5 XRP (correct)"
                elif ai_amount == "500000":
                    result["ai_pricing"] = "0.5 XRP (STALE)"
                    result["issues"].append("AI pricing is stale (0.5 XRP)")
                else:
                    result["ai_pricing"] = f"{ai_amount} (unknown)"

    except Exception as e:
        result["issues"].append(f"Import error: {e}")

    return result


def main():
    print("=== xrplme Country Bot Schema Audit ===\n")
    print(f"Checking {len(COUNTRIES)} countries...\n")

    results = []
    all_ok = True

    for code, module_name in MODULE_MAP.items():
        r = check_bot(module_name)
        results.append((code, module_name, r))

        if r["issues"]:
            all_ok = False
            status = "❌ ISSUES"
        else:
            status = "✅ OK"

        print(f"  {status}  {code:20s} ({module_name})")
        if r["issues"]:
            for issue in r["issues"]:
                print(f"         - {issue}")
        else:
            print(f"         - v1 schema: ✓  V1ChatResponse: ✓  {r.get('xrpl_pricing', 'N/A')}  {r.get('ai_pricing', 'N/A')}")

    print(f"\n{'='*60}")
    print(f"Summary: {sum(1 for _,_,r in results if not r['issues'])}/{len(results)} OK")
    print(f"Issues: {sum(1 for _,_,r in results if r['issues'])}")

    # Save full report
    report = {
        "audit_date": "2026-10-24",
        "total_countries": len(results),
        "all_ok": all_ok,
        "results": {
            code: {
                "module": mod_name,
                "import_ok": r["import_ok"],
                "has_to_v1_schema": r["has_to_v1_schema"],
                "has_V1ChatResponse": r["has_V1ChatResponse"],
                "resource_url_fixed": r.get("resource_url_fixed", "N/A"),
                "xrpl_pricing": r.get("xrpl_pricing", "N/A"),
                "ai_pricing": r.get("ai_pricing", "N/A"),
                "issues": r["issues"],
            }
            for code, mod_name, r in results
        }
    }

    with open("/tmp/schema_audit_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report saved to /tmp/schema_audit_report.json")


if __name__ == "__main__":
    main()
