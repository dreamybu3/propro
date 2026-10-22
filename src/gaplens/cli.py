"""GapLens command line: historical CSV + incomplete CSV -> audited repair."""
from __future__ import annotations
import argparse
import sys
from . import __version__
from .pipeline import RepairConfig, repair


def parser():
    p = argparse.ArgumentParser(prog="gaplens", description="Offline time-series gap reconstruction with calibrated uncertainty and an auditable report.")
    p.add_argument("--version", action="version", version=f"GapLens {__version__}")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("repair", help="Repair missing values using separate earlier history")
    r.add_argument("--reference", required=True, help="Earlier regular timestamp,value CSV; suffix reserved for calibration")
    r.add_argument("--input", required=True, help="Later regular timestamp,value CSV; missing values are empty cells")
    r.add_argument("--output", required=True, help="Directory for repaired.csv, report.json and report.html")
    r.add_argument("--method", choices=("analog", "diverse", "linear", "extra-trees"), default="analog",
                   help="analog (default), diverse with non-overlapping historical windows, linear, or extra-trees")
    r.add_argument("--context", type=int, default=6, help="Observed samples required on each side (default: 6)")
    r.add_argument("--neighbors", type=int, default=12, help="Historical analog count (default: 12)")
    r.add_argument("--alpha", type=float, default=.1, help="Target gap miscoverage, not a guarantee (default: .1)")
    r.add_argument("--max-gap", type=int, default=48, help="Maximum repairable samples per gap (default: 48)")
    r.add_argument("--calibration-fraction", type=float, default=.25)
    r.add_argument("--calibration-gaps", type=int, default=32)
    r.add_argument("--seed", type=int, default=17)
    r.add_argument("--overwrite", action="store_true", help="Replace only GapLens artifacts in an existing output directory")
    r.add_argument("--require-complete", action="store_true", help="Exit 3 after export if any gaps remain unresolved")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    options = {k: getattr(args, k) for k in RepairConfig.__dataclass_fields__}
    try:
        result = repair(args.reference, args.input, args.output, RepairConfig(**options), args.overwrite)
    except (ValueError, OSError) as exc:
        print(f"gaplens: {exc}", file=sys.stderr)
        return 2
    summary = result["summary"]
    print(f"Reconstructed {summary['reconstructed_gaps']}/{summary['gaps']} gaps "
          f"({summary['reconstructed_samples']}/{summary['missing_samples']} missing samples).")
    print(f"Preserved {summary['unchanged_observations']} observed values; unresolved gaps: {summary['unresolved_gaps']}.")
    print(f"Saved {args.output}/repaired.csv, report.json and report.html")
    print("Intervals are empirical uncertainty estimates; nominal future coverage is not guaranteed.")
    return 3 if args.require_complete and summary["unresolved_gaps"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
