"""Quick smoke test: run every parser against the real police samples."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import detect
from backend.parsers.bank import parse_bank_pdf, parse_bank_xlsx, parse_bank_txt, parse_bank_csv
from backend.parsers.cdr import PARSERS as CDR_PARSERS
from backend.parsers.ipdr import PARSERS as IPDR_PARSERS

SAMPLES = r"F:\SCRATCH\AI-BANK-TRANSACTIONS-TELECOM-ANALYZER\data\surat_police_samples"


def run():
    summary = []
    for root, dirs, files in os.walk(SAMPLES):
        for fname in sorted(files):
            path = os.path.join(root, fname)
            cls = detect.classify(path)
            if cls["dataset"] == "CDR":
                try:
                    res = CDR_PARSERS[cls["format"]](path)
                    n = len(res["records"])
                    summary.append((fname, f"CDR/{cls['format']}", n, "ok", ""))
                except Exception as e:
                    summary.append((fname, f"CDR/{cls['format']}", 0, "ERR", str(e)[:120]))
            elif cls["dataset"] == "IPDR":
                try:
                    if cls["format"] == "ipdr_xlsx":
                        res = IPDR_PARSERS["ipdr_xlsx"](path)
                    else:
                        res = IPDR_PARSERS[cls["format"]](path)
                    summary.append((fname, f"IPDR/{cls['format']}", len(res["records"]), "ok", ""))
                except Exception as e:
                    summary.append((fname, f"IPDR/{cls['format']}", 0, "ERR", str(e)[:120]))
            elif cls["dataset"] == "BANK":
                try:
                    if fname.endswith(".xlsx"):
                        cls2 = detect.classify_xlsx(path)
                        if cls2["dataset"] == "IPDR":
                            res = IPDR_PARSERS["ipdr_xlsx"](path)
                            summary.append((fname, f"IPDR/{cls2['format']}", len(res["records"]), "ok", ""))
                            continue
                        res = parse_bank_xlsx(path)
                    elif fname.endswith(".pdf"):
                        res = parse_bank_pdf(path)
                    elif fname.endswith(".txt"):
                        res = parse_bank_txt(path)
                    else:
                        res = parse_bank_csv(path)
                    fam = res["meta"].get("family", "?")
                    summary.append((fname, f"BANK/{fam}", len(res["records"]), "ok", ""))
                except Exception as e:
                    summary.append((fname, "BANK/?", 0, "ERR", str(e)[:120]))
            else:
                summary.append((fname, cls["format"], 0, "SKIP", ""))

    print(f"{'file':42s} {'format':20s} {'rows':>6s}  status  detail")
    print("-" * 100)
    for fname, fmt, n, st, detail in summary:
        print(f"{fname[:40]:42s} {fmt:20s} {n:6d}  {st:6s}  {detail}")


if __name__ == "__main__":
    run()
