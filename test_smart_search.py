import sys
import os
import glob
from utils.analysis_engine import AnalysisEngine

# Find latest files
def get_latest_file(pattern):
    files = glob.glob(pattern) + glob.glob(os.path.join("Talepler", pattern))
    if not files: return None
    return max(files, key=os.path.getmtime)

rule_path = get_latest_file("*.xlsx")
control_path = get_latest_file("*.pdf")

print(f"Rule: {rule_path}")
print(f"Control: {control_path}")

if not rule_path or not control_path:
    print("Files not found.")
    sys.exit(1)

engine = AnalysisEngine()
result = engine.run_analysis(rule_path, control_path)

print(f"Status: {result['status']}")
found_count = 0
split_match_count = 0

for res in result["results"]:
    if res["found"]:
        found_count += 1
        term = res["term"]
        locations = res["locations"]
        
        # Check if matched_term exists
        has_matched_term = any("matched_term" in loc for loc in locations)
        if has_matched_term:
             # Check if it was a split match (i.e. term has hyphen and matched_term is shorter)
             if "-" in term:
                 split_match_count += 1
                 # Print first match
                 first_loc = locations[0]
                 matched = first_loc.get("matched_term", "N/A")
                 print(f"Row {res['row_index']}: Term '{term}' -> Matched '{matched}'")

print(f"Total Found: {found_count}")
print(f"Split Matches: {split_match_count}")
