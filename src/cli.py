import argparse
import yaml
import json
import os
from pprint import pprint

from src.data_pipeline.synthetic_data import save_synthetic_data
from src.data_pipeline.ingestion import DataIngestor
from src.ai_ml.criticality_scorer import TaskCriticalityScorer
from src.optimization.milp_solver import MaintenanceSchedulerMILP
from src.optimization.rolling_horizon import RollingHorizonScheduler
from src.simulation.evaluator import KPIEvaluator

def load_config(path="config/settings.yaml"):
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f)

def generate_data(args):
    save_synthetic_data(args.output)
    print(f"Synthetic data generated at {args.output}")

def score(args):
    config = load_config(args.config)
    ingestor = DataIngestor(config)
    scenario = ingestor.load_scenario()
    
    scorer = TaskCriticalityScorer(config)
    
    print(f"Scoring {len(scenario.jobs)} jobs...")
    for job in scenario.jobs:
        tci, explanation = scorer.calculate_tci(job.tci_inputs)
        print(f"Job {job.id} ({job.department}) - TCI: {tci:.2f}")
        if args.verbose:
            pprint(explanation)
            print("-" * 40)

def optimize(args):
    config = load_config(args.config)
    ingestor = DataIngestor(config)
    scenario = ingestor.load_scenario()
    
    # 1. Score
    scorer = TaskCriticalityScorer(config)
    job_tcis = {}
    for job in scenario.jobs:
        tci, _ = scorer.calculate_tci(job.tci_inputs)
        job_tcis[job.id] = tci
        
    # 2. Rolling Horizon (Optional freeze step for demo)
    if args.freeze:
        # Load previous dummy schedule or mock one
        rh = RollingHorizonScheduler(freeze_duration_hours=12)
        scenario = rh.apply_freeze({"scheduled_jobs": [{"job_id": "J_ENG_1", "start_time": 5}]}, scenario)
        
    # 3. Optimize
    solver = MaintenanceSchedulerMILP(config)
    print("Running PySCIPOpt MILP Solver...")
    result = solver.solve(scenario, job_tcis)
    
    if result["status"] not in ("optimal", "feasible", "heuristic_feasible"):
        print(f"Optimization failed: {result.get('error', result['status'])}")
        return
        
    print(f"Status: {result['status']}")
    print(f"Scheduled Jobs: {len(result['scheduled_jobs'])} / {len(scenario.jobs)}")
    
    # Save schedule
    with open("data/schedule_output.json", "w") as f:
        json.dump(result, f, indent=4)
    print("Schedule saved to data/schedule_output.json")

def evaluate(args):
    config = load_config(args.config)
    ingestor = DataIngestor(config)
    scenario = ingestor.load_scenario()
    
    try:
        with open("data/schedule_output.json", "r") as f:
            schedule = json.load(f)
    except FileNotFoundError:
        print("Schedule file not found. Run 'optimize' first.")
        return
        
    scorer = TaskCriticalityScorer(config)
    job_tcis = {job.id: scorer.calculate_tci(job.tci_inputs)[0] for job in scenario.jobs}
        
    evaluator = KPIEvaluator(scenario)
    result = evaluator.evaluate(schedule, job_tcis)
    
    print("\n--- KPI Report ---")
    for k, v in result["kpi_metrics"].items():
        print(f"{k}: {v}")
        
    with open("data/kpi_report.json", "w") as f:
        json.dump(result["kpi_metrics"], f, indent=4)
    print("\nKPI Report saved to data/kpi_report.json")

def run_demo(args):
    """End-to-End full execution."""
    print("=== SparkRail MVP Demo ===")
    print("1. Generating Data...")
    generate_data(args)
    
    print("\n2. Scoring Jobs...")
    score(args)
    
    print("\n3. Optimizing Schedule...")
    optimize(args)
    
    print("\n4. Evaluating KPIs (Optimized vs Baseline)...")
    evaluate(args)
    
    print("\nDemo complete! All outputs saved to data/ directory.")

def main():
    parser = argparse.ArgumentParser(description="AI-Powered Railway Block Planning MVP CLI")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to config file")
    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate-data", help="Generate synthetic BDMS/COA data")
    gen_parser.add_argument("--output", default="data/synthetic", help="Output directory")

    score_parser = subparsers.add_parser("score", help="Calculate TCI for all jobs")
    score_parser.add_argument("-v", "--verbose", action="store_true", help="Show score explanation")

    opt_parser = subparsers.add_parser("optimize", help="Run MILP block scheduler")
    opt_parser.add_argument("--freeze", action="store_true", help="Apply rolling horizon freeze")

    eval_parser = subparsers.add_parser("evaluate", help="Evaluate schedule KPIs")

    demo_parser = subparsers.add_parser("demo", help="Run full end-to-end demo workflow")
    demo_parser.add_argument("--output", default="data/synthetic", help="Output directory for data")
    demo_parser.add_argument("-v", "--verbose", action="store_true", help="Show score explanation")
    demo_parser.add_argument("--freeze", action="store_true", help="Apply rolling horizon freeze")

    args = parser.parse_args()

    if args.command == "generate-data":
        generate_data(args)
    elif args.command == "score":
        score(args)
    elif args.command == "optimize":
        optimize(args)
    elif args.command == "evaluate":
        evaluate(args)
    elif args.command == "demo":
        run_demo(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
