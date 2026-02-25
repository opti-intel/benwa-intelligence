from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import numpy as np
from scipy.optimize import minimize


class SchedulingSolver:
    """Constraint-based scheduling using topological sort and earliest-start."""

    def solve(self, tasks: list[dict], constraints: dict[str, Any]) -> dict[str, Any]:
        """
        Schedule *tasks* respecting dependency ordering.

        Each task dict must contain:
            - id: str
            - duration: float
            - dependencies: list[str]  (ids of predecessor tasks)

        Returns a dict with per-task start/end times and overall makespan.
        """
        task_map: dict[str, dict] = {t["id"]: t for t in tasks}

        # --- topological sort (Kahn's algorithm) ---
        in_degree: dict[str, int] = {t["id"]: 0 for t in tasks}
        successors: dict[str, list[str]] = defaultdict(list)
        for t in tasks:
            for dep in t.get("dependencies", []):
                successors[dep].append(t["id"])
                in_degree[t["id"]] += 1

        queue: deque[str] = deque(tid for tid, d in in_degree.items() if d == 0)
        order: list[str] = []
        while queue:
            tid = queue.popleft()
            order.append(tid)
            for succ in successors[tid]:
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    queue.append(succ)

        if len(order) != len(tasks):
            return {"error": "Cyclic dependency detected", "schedule": {}, "makespan": None}

        # --- earliest-start scheduling ---
        schedule: dict[str, dict[str, float]] = {}
        for tid in order:
            task = task_map[tid]
            deps = task.get("dependencies", [])
            earliest = 0.0
            for dep in deps:
                if dep in schedule:
                    earliest = max(earliest, schedule[dep]["end"])
            start = earliest
            end = start + task["duration"]
            schedule[tid] = {"start": start, "end": end}

        makespan = max(s["end"] for s in schedule.values()) if schedule else 0.0
        return {"schedule": schedule, "makespan": makespan}


class ResourceAllocator:
    """Greedy resource allocation by priority."""

    def allocate(
        self,
        resources: list[dict[str, Any]],
        demands: list[dict[str, Any]],
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Allocate *resources* to *demands* greedily by demand priority.

        Each resource dict should have at least: id, capacity.
        Each demand dict should have at least: id, required_capacity, priority (higher = more urgent).

        Returns an allocation mapping and list of unmet demands.
        """
        # Sort demands by priority descending (highest priority first)
        sorted_demands = sorted(demands, key=lambda d: d.get("priority", 0), reverse=True)

        # Track remaining capacity per resource
        remaining: dict[str, float] = {r["id"]: r.get("capacity", 0) for r in resources}

        allocations: dict[str, str | None] = {}
        unmet: list[str] = []

        for demand in sorted_demands:
            demand_id = demand["id"]
            required = demand.get("required_capacity", 0)
            allocated = False
            for res_id, cap in remaining.items():
                if cap >= required:
                    allocations[demand_id] = res_id
                    remaining[res_id] -= required
                    allocated = True
                    break
            if not allocated:
                allocations[demand_id] = None
                unmet.append(demand_id)

        return {
            "allocations": allocations,
            "unmet_demands": unmet,
            "remaining_capacity": remaining,
        }


class OptimizationSolver:
    """Simple numeric optimization using scipy.optimize.minimize."""

    def optimize(
        self,
        plan_data: dict[str, Any],
        objective: str,
        constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Optimize plan parameters for a given *objective* ('cost' or 'time').

        plan_data should contain:
            - values: list[float] — initial parameter vector
            - weights: list[float] (optional) — per-parameter cost/time weights

        Returns optimised parameter values and the minimised objective value.
        """
        values = np.array(plan_data.get("values", [1.0]), dtype=float)
        weights = np.array(plan_data.get("weights", np.ones_like(values)), dtype=float)

        bounds_raw = constraints.get("bounds")
        bounds = [(b[0], b[1]) for b in bounds_raw] if bounds_raw else None

        if objective == "cost":
            def obj_fn(x: np.ndarray) -> float:
                return float(np.dot(weights, x ** 2))
        else:
            # Default: minimise weighted sum (time-like)
            def obj_fn(x: np.ndarray) -> float:
                return float(np.dot(weights, np.abs(x)))

        result = minimize(obj_fn, values, method="L-BFGS-B", bounds=bounds)
        return {
            "optimized_values": result.x.tolist(),
            "objective_value": float(result.fun),
            "success": bool(result.success),
            "message": result.message,
        }


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def solve_request(
    solver_type: str,
    plan_data: dict[str, Any],
    constraints: dict[str, Any],
    objective: str,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Route a solve request to the correct solver implementation."""
    if solver_type == "schedule":
        tasks = plan_data.get("tasks", [])
        solver = SchedulingSolver()
        return solver.solve(tasks, constraints)

    if solver_type == "allocate":
        resources = plan_data.get("resources", [])
        demands = plan_data.get("demands", [])
        allocator = ResourceAllocator()
        return allocator.allocate(resources, demands, constraints)

    if solver_type == "optimize":
        solver = OptimizationSolver()
        return solver.optimize(plan_data, objective, constraints)

    return {"error": f"Unknown solver_type: {solver_type}"}
