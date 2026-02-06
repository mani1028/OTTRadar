"""
Run the full import -> export -> enrich loop workflow.
Usage: python -m scripts.run_full_pipeline
"""

import subprocess
import sys


def run_checked(args):
    result = subprocess.run(args, text=True)
    if result.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(args)}")


def run_enrich_until_zero(max_passes=60):
    for i in range(1, max_passes + 1):
        print(f"=== Enrichment pass {i} ===")
        result = subprocess.run(
            [sys.executable, "-m", "scripts.enrich_existing"],
            text=True,
            capture_output=True,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            raise SystemExit(f"Enrichment pass {i} failed")
        if "Found 0 candidates. Processing 0" in result.stdout:
            print("No candidates left. Stopping enrichment loop.")
            break


def main():
    run_checked([sys.executable, "-m", "scripts.production_bulk_import", "--language", "en", "--region", "IN", "--pages", "500"])
    run_checked([sys.executable, "-m", "scripts.production_bulk_import", "--language", "ml", "--region", "IN", "--pages", "200"])
    run_checked([sys.executable, "-m", "scripts.production_bulk_import", "--language", "kn", "--region", "IN", "--pages", "200"])
    run_checked([sys.executable, "-m", "scripts.export_db"])
    run_enrich_until_zero()


if __name__ == "__main__":
    main()
