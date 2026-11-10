"""STRIX CLI entrypoint: load pipeline and API server."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("strix")


def run_load(data_dir: str) -> None:
    """Run ingestion -> parse -> detect -> geolocate malicious -> DB insert."""
    from ingestion.read import iter_log_lines
    from processing.detection import detect_bots
    from processing.extract_transform import AuthEvent, parse_line
    from processing.gelocation import geolocate
    from storage.database import init_db, insert_events, upsert_ip_intel

    year = int(os.getenv("LOG_YEAR", "2024"))

    log.info("Initializing database schema")
    init_db()

    log.info("Reading logs from %s", data_dir)
    events: List[AuthEvent] = []
    lines_read = 0
    for source_file, line in iter_log_lines(data_dir):
        lines_read += 1
        event = parse_line(line, year)
        if event is None:
            continue
        event.source_file = source_file
        events.append(event)

    log.info("Lines read: %s", lines_read)
    log.info("Events parsed: %s", len(events))

    log.info("Detecting bots / malicious IPs")
    scores = detect_bots(events)
    bots = sum(1 for info in scores.values() if info["is_bot"])
    malicious_ips = [ip for ip, info in scores.items() if info["is_malicious"]]
    log.info("IPs scored: %s", len(scores))
    log.info("Bots detected: %s", bots)
    log.info("Malicious IPs: %s", len(malicious_ips))

    log.info("Geolocating malicious IPs only (ipinfo quota)")
    intel_rows = []
    for ip in malicious_ips:
        info = scores[ip]
        geo = geolocate(ip)
        loc = geo.get("loc") or {}
        intel_rows.append(
            {
                "ip": ip,
                "country": geo.get("country"),
                "country_code": geo.get("country_code"),
                "city": geo.get("city"),
                "region": geo.get("region"),
                "lat": loc.get("lat") if isinstance(loc, dict) else None,
                "lon": loc.get("lon") if isinstance(loc, dict) else None,
                "org": geo.get("org"),
                "is_malicious": info["is_malicious"],
                "failed_count": info["failed_count"],
                "first_seen": info["first_seen"],
                "last_seen": info["last_seen"],
                "is_bot": info["is_bot"],
            }
        )
    log.info("Geolocation done: %s IPs", len(intel_rows))

    log.info("Inserting auth events (duplicates ignored)")
    inserted_events = insert_events(events)
    log.info("Auth events inserted (new rows): %s", inserted_events)

    log.info("Upserting IP intelligence")
    upserted = upsert_ip_intel(intel_rows)
    log.info("IP intel upserted: %s", upserted)

    log.info(
        "Load complete | lines=%s parsed=%s inserted=%s bots=%s malicious=%s",
        lines_read,
        len(events),
        inserted_events,
        bots,
        len(malicious_ips),
    )


def run_serve(host: str, port: int) -> None:
    """Start the FastAPI server (step 7)."""
    try:
        import uvicorn
        from serving.api import app
    except ImportError:
        log.error(
            "API not available yet (step 7). "
            "Create serving/api.py, then retry: python main.py serve"
        )
        sys.exit(1)

    log.info("Starting STRIX API on http://%s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="STRIX log analysis CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    load_parser = sub.add_parser("load", help="Run the full ingest pipeline")
    load_parser.add_argument(
        "--data-dir",
        default="./data",
        help="Directory containing rotated auth logs (default: ./data)",
    )

    serve_parser = sub.add_parser("serve", help="Start the HTTP API (step 7)")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: List[str] | None = None) -> None:
    """Parse CLI args and dispatch the chosen command."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "load":
        run_load(args.data_dir)
    elif args.command == "serve":
        run_serve(args.host, args.port)
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
