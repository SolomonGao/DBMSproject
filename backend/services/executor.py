"""
Planner Executor — Parallel query execution engine.

Receives a QueryPlan from the Planner, executes all steps in parallel
via DataService, and returns structured JSON results.
"""

import asyncio
from typing import Dict, Any, List

from backend.services.data_service import DataService
from backend.agents.planner import QueryPlan, QueryStep


class Executor:
    """Executes query plans by parallel DataService calls."""

    def __init__(self, data_service: DataService):
        self.ds = data_service

    async def execute(self, plan: QueryPlan) -> Dict[str, Any]:
        """
        Execute all steps in a query plan concurrently.

        Returns:
            dict mapping step index to result data
        """
        if not plan.steps:
            return {}

        # Build coroutines for each step
        tasks = []
        for i, step in enumerate(plan.steps):
            tasks.append(self._execute_step(i, step))

        # Run all queries in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Package results
        output = {}
        for i, (step, result) in enumerate(zip(plan.steps, results)):
            key = f"{step.type}_{i}"
            if isinstance(result, Exception):
                print(f"[Executor] Step {i} ({step.type}) failed: {result}", flush=True)
                output[key] = {"error": str(result), "type": step.type}
            else:
                output[key] = {"type": step.type, "data": result}

        return output

    async def _execute_step(self, index: int, step: QueryStep) -> Any:
        """Execute a single query step via DataService."""
        p = step.params
        step_type = step.type

        if step_type == "dashboard":
            return await self.ds.get_dashboard(
                p.get("start_date"), p.get("end_date")
            )

        if step_type == "overview":
            return await self.ds.get_regional_overview(
                p.get("region", "USA"),
                p.get("time_range", "month"),
                p.get("start_date"),
                p.get("end_date")
            )

        if step_type == "top_events":
            return await self.ds.get_top_events(
                p.get("start_date"), p.get("end_date"),
                p.get("region_filter"),
                p.get("event_type"),
                p.get("top_n", 10)
            )

        if step_type == "hot_events":
            return await self.ds.get_hot_events(
                p.get("date"),
                p.get("region_filter"),
                p.get("top_n", 5)
            )

        if step_type == "events":
            return await self.ds.search_events(
                p.get("query", ""),
                p.get("time_hint"),
                p.get("location_hint"),
                p.get("event_type"),
                p.get("limit", 20)
            )

        if step_type == "timeseries":
            return await self.ds.get_time_series(
                p.get("start_date"), p.get("end_date"),
                p.get("granularity", "day")
            )

        if step_type == "geo":
            precision = p.get("precision", 2)
            try:
                precision = int(precision)
            except (ValueError, TypeError):
                print(f"[Executor] Invalid geo precision '{precision}', defaulting to 2", flush=True)
                precision = 2
            return await self.ds.get_geo_heatmap(
                p.get("start_date"), p.get("end_date"), precision
            )

        if step_type == "daily_brief":
            return await self.ds.get_daily_brief(p.get("date"))

        if step_type == "news_context":
            return await self.ds.search_news_context(
                p.get("query", ""),
                p.get("n_results", 5)
            )

        if step_type == "event_detail":
            return await self.ds.get_event_detail(p.get("fingerprint", ""))

        raise ValueError(f"Unknown step type: {step_type}")


async def run_plan(data_service: DataService, plan: QueryPlan) -> Dict[str, Any]:
    """Convenience function: execute a plan and return results."""
    executor = Executor(data_service)
    return await executor.execute(plan)
