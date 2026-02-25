"""Tests for solver-engine solver implementations."""

import sys
import os

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVICES_DIR = os.path.join(REPO_ROOT, "services")
sys.path.insert(0, os.path.join(SERVICES_DIR, "solver-engine"))
sys.path.insert(0, SERVICES_DIR)

from app.solvers import SchedulingSolver, ResourceAllocator, OptimizationSolver


# ---------------------------------------------------------------------------
# SchedulingSolver
# ---------------------------------------------------------------------------

class TestSchedulingSolver:
    """Tests for the SchedulingSolver."""

    def test_simple_sequential_schedule(self, sample_tasks):
        """Three tasks with linear dependencies should schedule sequentially."""
        solver = SchedulingSolver()
        result = solver.solve(sample_tasks, constraints={})

        assert "schedule" in result
        assert "makespan" in result
        assert result["makespan"] is not None

        schedule = result["schedule"]
        assert schedule["excavation"]["start"] == 0.0
        assert schedule["excavation"]["end"] == 5.0
        assert schedule["foundation"]["start"] == 5.0
        assert schedule["foundation"]["end"] == 8.0
        assert schedule["framing"]["start"] == 8.0
        assert schedule["framing"]["end"] == 15.0
        assert result["makespan"] == 15.0

    def test_parallel_tasks_without_dependencies(self):
        """Independent tasks should all start at time 0."""
        solver = SchedulingSolver()
        tasks = [
            {"id": "a", "duration": 3.0, "dependencies": []},
            {"id": "b", "duration": 5.0, "dependencies": []},
            {"id": "c", "duration": 2.0, "dependencies": []},
        ]
        result = solver.solve(tasks, constraints={})

        schedule = result["schedule"]
        for task_id in ["a", "b", "c"]:
            assert schedule[task_id]["start"] == 0.0

        assert result["makespan"] == 5.0

    def test_detects_cyclic_dependencies(self):
        """Cyclic task dependencies should be reported as an error."""
        solver = SchedulingSolver()
        tasks = [
            {"id": "a", "duration": 1.0, "dependencies": ["c"]},
            {"id": "b", "duration": 1.0, "dependencies": ["a"]},
            {"id": "c", "duration": 1.0, "dependencies": ["b"]},
        ]
        result = solver.solve(tasks, constraints={})

        assert "error" in result
        assert "Cyclic" in result["error"]
        assert result["makespan"] is None

    def test_diamond_dependency(self):
        """A diamond-shaped dependency graph should schedule correctly."""
        solver = SchedulingSolver()
        tasks = [
            {"id": "start", "duration": 2.0, "dependencies": []},
            {"id": "left", "duration": 3.0, "dependencies": ["start"]},
            {"id": "right", "duration": 5.0, "dependencies": ["start"]},
            {"id": "end", "duration": 1.0, "dependencies": ["left", "right"]},
        ]
        result = solver.solve(tasks, constraints={})

        schedule = result["schedule"]
        assert schedule["start"]["start"] == 0.0
        # Both left and right start after start ends
        assert schedule["left"]["start"] == 2.0
        assert schedule["right"]["start"] == 2.0
        # end must wait for the longer branch (right: 2+5=7)
        assert schedule["end"]["start"] == 7.0
        assert result["makespan"] == 8.0

    def test_single_task(self):
        """Single task should be straightforward."""
        solver = SchedulingSolver()
        tasks = [{"id": "only", "duration": 4.0, "dependencies": []}]
        result = solver.solve(tasks, constraints={})

        assert result["schedule"]["only"] == {"start": 0.0, "end": 4.0}
        assert result["makespan"] == 4.0

    def test_empty_task_list(self):
        """Empty task list should return zero makespan."""
        solver = SchedulingSolver()
        result = solver.solve([], constraints={})

        assert result["schedule"] == {}
        assert result["makespan"] == 0.0


# ---------------------------------------------------------------------------
# ResourceAllocator
# ---------------------------------------------------------------------------

class TestResourceAllocator:
    """Tests for the ResourceAllocator."""

    def test_allocate_matching_demands(self, sample_resources, sample_demands):
        """All demands should be satisfied when resources are sufficient."""
        allocator = ResourceAllocator()
        result = allocator.allocate(sample_resources, sample_demands, {})

        assert "allocations" in result
        assert "unmet_demands" in result
        assert result["unmet_demands"] == []

        allocations = result["allocations"]
        # Every demand should be assigned a resource
        for demand in sample_demands:
            assert allocations[demand["id"]] is not None

    def test_handles_unmet_demands(self):
        """When demand exceeds capacity, unmet demands should be reported."""
        allocator = ResourceAllocator()
        resources = [{"id": "small-crane", "capacity": 10}]
        demands = [
            {"id": "big-lift", "required_capacity": 50, "priority": 10},
            {"id": "small-lift", "required_capacity": 5, "priority": 5},
        ]
        result = allocator.allocate(resources, demands, {})

        assert "big-lift" in result["unmet_demands"]
        assert result["allocations"]["big-lift"] is None
        # small-lift should still be allocated
        assert result["allocations"]["small-lift"] == "small-crane"

    def test_priority_ordering(self):
        """Higher priority demands should be allocated first."""
        allocator = ResourceAllocator()
        resources = [{"id": "r1", "capacity": 50}]
        demands = [
            {"id": "low-pri", "required_capacity": 40, "priority": 1},
            {"id": "high-pri", "required_capacity": 40, "priority": 10},
        ]
        result = allocator.allocate(resources, demands, {})

        # High priority gets the resource
        assert result["allocations"]["high-pri"] == "r1"
        # Low priority is unmet
        assert "low-pri" in result["unmet_demands"]

    def test_remaining_capacity_tracked(self, sample_resources, sample_demands):
        """Remaining capacity should reflect allocated amounts."""
        allocator = ResourceAllocator()
        result = allocator.allocate(sample_resources, sample_demands, {})

        remaining = result["remaining_capacity"]
        # Total original capacity = 100 + 80 + 50 = 230
        # Total demanded = 90 + 60 + 40 = 190
        total_remaining = sum(remaining.values())
        assert total_remaining == 230 - 190

    def test_empty_demands(self, sample_resources):
        """No demands should result in empty allocations."""
        allocator = ResourceAllocator()
        result = allocator.allocate(sample_resources, [], {})

        assert result["allocations"] == {}
        assert result["unmet_demands"] == []

    def test_empty_resources(self, sample_demands):
        """No resources should leave all demands unmet."""
        allocator = ResourceAllocator()
        result = allocator.allocate([], sample_demands, {})

        assert len(result["unmet_demands"]) == len(sample_demands)


# ---------------------------------------------------------------------------
# OptimizationSolver
# ---------------------------------------------------------------------------

class TestOptimizationSolver:
    """Tests for the OptimizationSolver."""

    def test_cost_optimization(self):
        """Cost objective should minimize weighted squared values."""
        solver = OptimizationSolver()
        result = solver.optimize(
            plan_data={"values": [5.0, 5.0], "weights": [1.0, 1.0]},
            objective="cost",
            constraints={"bounds": [(-10, 10), (-10, 10)]},
        )

        assert result["success"] is True
        # Minimum of weighted x^2 is at x=0
        for v in result["optimized_values"]:
            assert abs(v) < 0.1

    def test_time_optimization(self):
        """Time objective should minimize weighted absolute values."""
        solver = OptimizationSolver()
        result = solver.optimize(
            plan_data={"values": [3.0, -2.0], "weights": [1.0, 1.0]},
            objective="time",
            constraints={"bounds": [(-10, 10), (-10, 10)]},
        )

        assert result["success"] is True
        assert result["objective_value"] < 5.0  # should be better than initial

    def test_optimization_without_bounds(self):
        """Optimization should work without explicit bounds."""
        solver = OptimizationSolver()
        result = solver.optimize(
            plan_data={"values": [1.0]},
            objective="cost",
            constraints={},
        )

        assert result["success"] is True
        assert "optimized_values" in result

    def test_result_contains_expected_keys(self):
        """Result dict should have all expected keys."""
        solver = OptimizationSolver()
        result = solver.optimize(
            plan_data={"values": [1.0]},
            objective="cost",
            constraints={},
        )

        assert "optimized_values" in result
        assert "objective_value" in result
        assert "success" in result
        assert "message" in result
