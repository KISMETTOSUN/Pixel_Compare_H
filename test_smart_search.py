import sys
sys.stdout.reconfigure(encoding='utf-8')
import glob
from utils.analysis_engine import AnalysisEngine

engine = AnalysisEngine()
pdfs = glob.glob("*.pdf")

print(f"Kural: Kural.xlsx")
print(f"PDF sayısı: {len(pdfs)}\n")

for pdf in sorted(pdfs):
    result = engine.run_analysis('Kural.xlsx', pdf)
    found = sum(1 for r in result["results"] if r["found"])
    total = len(result["results"])
    print(f"{'='*60}")
    print(f"📄 {pdf}")
    print(f"   Sonuç: {found}/{total} eşleşme")
    for res in result["results"]:
        status = "✅" if res["found"] else "❌"
        phase = res.get("search_phase", "")
        matched = res.get("matched_term", "")[:80]
        print(f"   {status} {res['ref_name']}: [{phase}] {matched}")
    print()
