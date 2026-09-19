#!/usr/bin/env python3
"""List the POA&Ms the pipeline has already produced, and check each one against the evidence store.

Read-only. For every POA&M JSON in the WORM `reports` container it shows when the file was created,
which collection run it was cut from, whether that run came from the timer or a manual call (from the
`runs` ledger), how many findings it lists, and whether that count equals the store's count for the run.

Usage:
    python3 scripts/poam_history.py                      # newest 24
    python3 scripts/poam_history.py --limit 100
    python3 scripts/poam_history.py --json > history.json
    python3 scripts/poam_history.py --account stgrcevidqst3u6 \\
        --cosmos https://cosmos-grc-evidence-qst3u6.documents.azure.com:443/

Needs `az login` as someone with Storage Blob Data Reader and Cosmos data-read access.
The account and endpoint default to the COSMOS_ENDPOINT and REPORTS_ACCOUNT environment variables.
"""

import argparse
import collections
import json
import os
import sys

# A scheduled report is created by the :10 timer. Anything else was requested by hand.
TIMER_MINUTES = range(10, 15)


def summarise(report: dict) -> dict:
    """Counts a POA&M reports about itself. Pure, so it can be unit-tested without Azure."""
    items = report.get("items") or []
    by_severity = collections.Counter(item.get("severity") for item in items)
    return {
        "runId": report.get("runId"),
        "collectedAt": report.get("collectedAt"),
        "items": len(items),
        "high": by_severity.get("High", 0),
        "medium": by_severity.get("Medium", 0),
        "low": by_severity.get("Low", 0),
    }


def shape(created, trigger: str | None) -> str:
    """timer = the ledger says timer AND the file was created at the timer's minute; anything else is manual."""
    if trigger == "timer" and created.minute in TIMER_MINUTES:
        return "timer"
    return "manual" if trigger else "no ledger entry"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--account", default=os.environ.get("REPORTS_ACCOUNT", "stgrcevidqst3u6"), help="evidence storage account name")
    parser.add_argument("--container", default="reports")
    parser.add_argument("--cosmos", default=os.environ.get("COSMOS_ENDPOINT"), help="Cosmos endpoint; needed to read the run ledger")
    parser.add_argument("--limit", type=int, default=24, help="how many of the newest POA&Ms to show (default 24)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args()

    from azure.identity import AzureCliCredential
    from azure.storage.blob import BlobServiceClient

    credential = AzureCliCredential()
    blobs = BlobServiceClient(f"https://{args.account}.blob.core.windows.net", credential=credential).get_container_client(args.container)
    poams = sorted(
        (b for b in blobs.list_blobs(name_starts_with="poam/") if b.name.endswith(".json")),
        key=lambda b: b.creation_time,
        reverse=True,
    )[: args.limit]

    db = None
    if args.cosmos:
        from azure.cosmos import CosmosClient

        db = CosmosClient(args.cosmos, credential).get_database_client("grc")

    def ledger(run_id):
        if not (db and run_id):
            return {}
        rows = list(db.get_container_client("runs").query_items(
            "SELECT c.trigger, c.documents, c.unhealthy FROM c WHERE c.runId = @r",
            parameters=[{"name": "@r", "value": run_id}], enable_cross_partition_query=True))
        return rows[0] if rows else {}

    rows = []
    for blob in poams:
        summary = summarise(json.loads(blobs.download_blob(blob.name).readall()))
        entry = ledger(summary["runId"])
        rows.append({
            "created": blob.creation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "blob": blob.name,
            **summary,
            "trigger": shape(blob.creation_time, entry.get("trigger")),
            "matchesStore": (summary["items"] == entry["unhealthy"]) if "unhealthy" in entry else None,
        })

    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        print()
        return 0

    print(f"{'created (UTC)':<20} {'origin':<15} {'items':>5} {'H':>3} {'M':>3} {'L':>3}  {'= store':<8} blob")
    for r in rows:
        match = {True: "yes", False: "NO", None: "n/a"}[r["matchesStore"]]
        print(f"{r['created']:<20} {r['trigger']:<15} {r['items']:>5} {r['high']:>3} {r['medium']:>3} {r['low']:>3}  {match:<8} {r['blob']}")
    scheduled = sum(1 for r in rows if r["trigger"] == "timer")
    print(f"\n{len(rows)} POA&Ms shown, {scheduled} created by the timer, "
          f"{sum(1 for r in rows if r['matchesStore'] is False)} with a count that differs from the store.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
