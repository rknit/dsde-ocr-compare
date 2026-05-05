import json
import glob
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent


def aggregate_candidates():
    totals = defaultdict(int)
    files = sorted(glob.glob(str(BASE / "**" / "*.json"), recursive=True))
    for filepath in files:
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        for num_str, votes in data.get("form_5_18", {}).get("candidates", {}).items():
            totals[int(num_str)] += votes
    return totals, len(files)


def aggregate_parties():
    totals = defaultdict(int)
    files = sorted(glob.glob(str(BASE / "**" / "*.json"), recursive=True))
    for filepath in files:
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        for num_str, votes in data.get("form_5_18_bch", {}).get("candidates", {}).items():
            totals[int(num_str)] += votes
    return totals, len(files)


def pct_error(ocr, ref):
    if ref == 0:
        return float("inf") if ocr != 0 else 0.0
    return abs(ocr - ref) / ref * 100


def write_json_outputs(ocr_candidates, ocr_parties, candidate_map):
    candidate_out = {
        str(num): {
            "ชื่อ_สกุล": candidate_map.get(str(num), {}).get("ชื่อ_สกุล", ""),
            "พรรค":      candidate_map.get(str(num), {}).get("พรรค", ""),
            "vote":      votes,
        }
        for num, votes in sorted(ocr_candidates.items())
    }
    (BASE / "ocr_candidate_result.json").write_text(
        json.dumps(candidate_out, ensure_ascii=False, indent="\t"), encoding="utf-8"
    )

    party_out = {str(num): votes for num, votes in sorted(ocr_parties.items())}
    (BASE / "ocr_party_result.json").write_text(
        json.dumps(party_out, ensure_ascii=False, indent="\t"), encoding="utf-8"
    )
    print("\nWrote ocr_candidate_result.json and ocr_party_result.json")


def print_candidate_report(ocr_totals, ref_data, candidate_map):
    print("=" * 80)
    print("CANDIDATE RESULTS")
    print("=" * 80)
    header = f"{'#':>2}  {'Name':<28} {'Party':<22} {'OCR':>8} {'Ref':>8} {'Diff':>7} {'Err%':>7}"
    print(header)
    print("-" * 80)

    abs_diffs = []
    for num_str, ref_info in sorted(ref_data.items(), key=lambda x: int(x[0])):
        num = int(num_str)
        ocr = ocr_totals.get(num, 0)
        ref = ref_info["vote"]
        diff = ocr - ref
        err = pct_error(ocr, ref)
        abs_diffs.append(abs(diff))
        name = candidate_map.get(num_str, {}).get("ชื่อ_สกุล", "")[:27]
        party = candidate_map.get(num_str, {}).get("พรรค", "")[:21]
        print(f"{num:>2}  {name:<28} {party:<22} {ocr:>8,} {ref:>8,} {diff:>+7,} {err:>6.2f}%")

    print("-" * 80)
    total_ocr = sum(ocr_totals.values())
    total_ref = sum(r["vote"] for r in ref_data.values())
    print(f"{'TOTAL':<54} {total_ocr:>8,} {total_ref:>8,} {total_ocr - total_ref:>+7,} {pct_error(total_ocr, total_ref):>6.2f}%")
    print(f"\nWeighted mean error per candidate: {sum(abs_diffs) / total_ref * 100:.2f}%")


def print_party_report(ocr_totals, ref_data, party_map):
    print()
    print("=" * 80)
    print("PARTY RESULTS")
    print("=" * 80)
    header = f"{'#':>3}  {'Party Name':<36} {'OCR':>8} {'Ref':>8} {'Diff':>7} {'Err%':>7}"
    print(header)
    print("-" * 80)

    abs_diffs = []
    for num_str, ref_votes in sorted(ref_data.items(), key=lambda x: int(x[0])):
        num = int(num_str)
        ocr = ocr_totals.get(num, 0)
        ref = ref_votes
        diff = ocr - ref
        err = pct_error(ocr, ref)
        abs_diffs.append(abs(diff))
        name = party_map.get(num_str, f"พรรค {num}")[:35]
        print(f"{num:>3}  {name:<36} {ocr:>8,} {ref:>8,} {diff:>+7,} {err:>6.2f}%")

    print("-" * 80)
    total_ocr = sum(ocr_totals.values())
    total_ref = sum(ref_data.values())
    print(f"{'TOTAL':<42} {total_ocr:>8,} {total_ref:>8,} {total_ocr - total_ref:>+7,} {pct_error(total_ocr, total_ref):>6.2f}%")
    print(f"\nWeighted mean error per party: {sum(abs_diffs) / total_ref * 100:.2f}%")


def main():
    ref_candidates = json.loads((BASE / "ref_candidate_result.json").read_text(encoding="utf-8"))
    ref_parties = json.loads((BASE / "ref_party_result.json").read_text(encoding="utf-8"))
    candidate_map = json.loads((BASE / "maps" / "candidate_map.json").read_text(encoding="utf-8"))
    party_map = json.loads((BASE / "maps" / "party_map.json").read_text(encoding="utf-8"))

    print("Aggregating candidate votes...")
    ocr_candidates, n_files = aggregate_candidates()
    print(f"  Processed {n_files} files.")

    print("Aggregating party votes...")
    ocr_parties, _ = aggregate_parties()

    write_json_outputs(ocr_candidates, ocr_parties, candidate_map)
    print_candidate_report(ocr_candidates, ref_candidates, candidate_map)
    print_party_report(ocr_parties, ref_parties, party_map)


if __name__ == "__main__":
    main()
