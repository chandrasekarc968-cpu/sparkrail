"""
SparkRail Day-One Plugin Shell & CLI Entrypoint.

Provides operator commands for:
- Initializing synthetic corridor fixtures from seed
- Launching the advisory planning API in synthetic, shadow, or live mode
- Verifying the SHA-256 cryptographic audit chain
- Running corridor performance benchmarks
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime, timezone

from src.config import PluginConfig, SparkRailMode
from src.data_pipeline.synthetic_data import (
    generate_synthetic_data,
    save_synthetic_data,
    generate_network_geometry,
    generate_synthetic_assets,
    generate_synthetic_events
)
from src.data_pipeline.topology import CanonicalRailwayTopology

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SparkRail.Plugin")

def cmd_generate_seed(args):
    seed = args.seed
    output_dir = args.output_dir or "data/synthetic"
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Generating deterministic synthetic corridor from seed={seed}...")
    scenario = generate_synthetic_data(seed=seed, num_blocks=8, num_jobs=20, num_trains=10)
    save_synthetic_data(path=output_dir, seed=seed, num_blocks=8, num_jobs=20, num_trains=10)

    geom = generate_network_geometry(scenario)
    geom_file = os.path.join(output_dir, "network_geometry.json")
    with open(geom_file, "w") as f:
        json.dump(geom.model_dump(), f, indent=2)

    events = generate_synthetic_events()
    events_file = os.path.join(output_dir, "replay_events.json")
    with open(events_file, "w") as f:
        json.dump([e.model_dump() for e in events], f, indent=2)

    # Data quality report
    quality_report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "mode": "SYNTHETIC",
        "corridor": "Subedarganj (SFG) - Mirzapur (MZP)",
        "corridor_length_km": 80.0,
        "blocks_count": len(scenario.blocks),
        "maintenance_jobs_count": len(scenario.jobs),
        "trains_count": len(scenario.trains),
        "track_sections_count": len(geom.track_sections),
        "signals_count": len(geom.signals),
        "ohe_masts_count": len(geom.ohe_masts),
        "replay_events_count": len(events),
        "schema_version": "1.0.0",
        "advisory_notice": "ADVISORY ONLY: HUMAN APPROVAL REQUIRED. SYNTHETIC BENCHMARK DATA."
    }
    report_file = os.path.join(output_dir, "data_quality_report.json")
    with open(report_file, "w") as f:
        json.dump(quality_report, f, indent=2)

    logger.info(f"Synthetic dataset saved to {output_dir}:")
    logger.info(f"  - scenario.json ({len(scenario.jobs)} jobs, {len(scenario.trains)} trains)")
    logger.info(f"  - network_geometry.json ({len(geom.track_sections)} track sections)")
    logger.info(f"  - replay_events.json ({len(events)} events)")
    logger.info(f"  - data_quality_report.json")

def cmd_verify_audit(args):
    from src.api.advisory import AUDIT_REPO
    is_valid, error = AUDIT_REPO.verify_integrity()
    events = AUDIT_REPO.get_events(limit=1000)
    print(f"=== SPARKRAIL CRYPTOGRAPHIC AUDIT VERIFICATION ===")
    print(f"Chain Length: {len(events)} events")
    print(f"Integrity Status: {'VALID (INTACT)' if is_valid else 'COMPROMISED'}")
    if error:
        print(f"Violation: {error}")
    print(f"==================================================")
    if not is_valid:
        sys.exit(1)

def cmd_run_api(args):
    import uvicorn
    mode = PluginConfig.get_mode()
    logger.info(f"Starting SparkRail API Gateway in {mode.value.upper()} mode on {args.host}:{args.port}")
    if mode == SparkRailMode.LIVE and not PluginConfig.is_live_permitted():
        logger.error("Live mode requested but not permitted. Halting.")
        sys.exit(1)
    uvicorn.run("src.api.main:app", host=args.host, port=args.port, reload=args.reload)

def main():
    parser = argparse.ArgumentParser(description="SparkRail Railway Planning Plugin CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # generate-seed
    gen_parser = subparsers.add_parser("generate-seed", help="Generate reproducible synthetic corridor data")
    gen_parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
    gen_parser.add_argument("--output-dir", type=str, default="data/synthetic", help="Output directory")

    # verify-audit
    subparsers.add_parser("verify-audit", help="Verify SHA-256 tamper-evident audit chain")

    # run-api
    api_parser = subparsers.add_parser("run-api", help="Launch FastAPI server")
    api_parser.add_argument("--host", type=str, default="0.0.0.0", help="Bind host")
    api_parser.add_argument("--port", type=int, default=8000, help="Bind port")
    api_parser.add_argument("--reload", action="store_true", help="Enable hot reload")

    args = parser.parse_args()
    if args.command == "generate-seed":
        cmd_generate_seed(args)
    elif args.command == "verify-audit":
        cmd_verify_audit(args)
    elif args.command == "run-api":
        cmd_run_api(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
