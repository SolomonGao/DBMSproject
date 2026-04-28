"""
Analyze Router — AI-driven data exploration and visualization API.

Two-stage design for responsiveness:
1. POST /analyze       → Planner + Executor (fast, no LLM report)
2. POST /analyze/report → Report Generator (async, delayed load)
"""

import time
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException

from backend.services.data_service import data_service
from backend.agents.planner import Planner, ReportGenerator, QueryPlan
from backend.services.executor import run_plan
from backend.schemas.responses import (
    AnalyzeRequest,
    AnalyzeResponse,
    ReportRequest,
    QueryPlanOutput,
    ReportOutput,
)

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Stage 1: Planner + Executor only.
    Returns data + visualization plan immediately. NO report generation here.
    """
    total_start = time.time()
    llm_config = request.llm_config.model_dump() if request.llm_config else None

    try:
        # Step 1: Planner
        t0 = time.time()
        planner = Planner(config=llm_config)
        plan = await planner.plan(request.query)
        t_plan = round((time.time() - t0) * 1000, 1)
        print(f"[Analyze] Planner: {t_plan}ms | Intent: {plan.intent} | Steps: {len(plan.steps)}", flush=True)

        # Off-topic guard: skip database queries entirely
        if plan.intent == "off_topic":
            total_ms = round((time.time() - total_start) * 1000, 1)
            print(f"[Analyze] Off-topic detected, skipped execution in {total_ms}ms", flush=True)
            return AnalyzeResponse(
                query=request.query,
                plan=QueryPlanOutput(
                    intent=plan.intent,
                    time_range=None,
                    steps=[],
                    visualizations=[],
                ),
                data={},
                report=None,
                elapsed_ms=total_ms,
            )

        # Step 2: Executor
        t0 = time.time()
        results = await run_plan(data_service, plan)
        t_exec = round((time.time() - t0) * 1000, 1)
        print(f"[Analyze] Executor: {t_exec}ms | Keys: {list(results.keys())}", flush=True)

        total_ms = round((time.time() - total_start) * 1000, 1)
        print(f"[Analyze] TOTAL: {total_ms}ms (plan={t_plan}ms, exec={t_exec}ms)", flush=True)

        return AnalyzeResponse(
            query=request.query,
            plan=QueryPlanOutput(
                intent=plan.intent,
                thinking=plan.thinking,
                time_range=plan.time_range,
                steps=[{"type": s.type, "params": s.params} for s in plan.steps],
                visualizations=plan.visualizations,
                notice=plan.notice,
            ),
            data=results,
            report=None,  # Report is loaded separately
            elapsed_ms=total_ms,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Analyze] FAILED: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")


@router.post("/report", response_model=ReportOutput)
async def generate_report(request: ReportRequest):
    """
    Stage 2: Report Generator (async delayed load).
    Frontend calls this AFTER receiving visualization data.
    """
    t0 = time.time()
    llm_config = request.llm_config.model_dump() if request.llm_config else None

    try:
        reporter = ReportGenerator(config=llm_config)
        report = await reporter.generate(request.data, request.prompt)
        t_report = round((time.time() - t0) * 1000, 1)
        print(f"[Analyze/Report] Generated in {t_report}ms", flush=True)
        return ReportOutput(
            summary=report.summary,
            key_findings=report.key_findings,
        )
    except Exception as e:
        print(f"[Analyze/Report] FAILED: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")
