"""
Analyze Router — AI-driven data exploration and visualization API.

Two-stage design for responsiveness:
1. POST /analyze       → Planner + Executor (fast, no LLM report)
2. POST /analyze/report → Report Generator (async, delayed load)
3. POST /analyze/event-report → Enhanced Report (storyline + news + GKG)
4. POST /analyze/storyline → Storyline data only
"""

import time
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException

from backend.services.data_service import data_service
from backend.agents.planner import Planner, ReportGenerator, QueryPlan
from backend.agents.enhanced_reporter import get_enhanced_reporter
from backend.services.executor import run_plan
from backend.services.storyline_builder import build_full_storyline
from backend.services.gkg_client import gkg_client
from backend.schemas.responses import (
    AnalyzeRequest,
    AnalyzeResponse,
    ReportRequest,
    QueryPlanOutput,
    ReportOutput,
    EventReportRequest,
    EventReportResponse,
    EnhancedReportOutput,
    StorylineRequest,
    StorylineResponse,
    StorylineData,
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
        plan, planner_phases = await planner.plan(request.query)
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
                phases=[
                    *planner_phases,
                    {"name": "Response Ready", "status": "completed", "detail": "No database queries needed for off-topic input.", "elapsed_ms": 0},
                ],
            )

        # Step 2: Executor
        t0 = time.time()
        results = await run_plan(data_service, plan)
        t_exec = round((time.time() - t0) * 1000, 1)
        print(f"[Analyze] Executor: {t_exec}ms | Keys: {list(results.keys())}", flush=True)

        total_ms = round((time.time() - total_start) * 1000, 1)
        print(f"[Analyze] TOTAL: {total_ms}ms (plan={t_plan}ms, exec={t_exec}ms)", flush=True)

        step_keys = list(results.keys())
        step_count = len(step_keys)
        step_names = ' → '.join(step_keys) if step_keys else 'none'

        return AnalyzeResponse(
            query=request.query,
            plan=QueryPlanOutput(
                intent=plan.intent,
                thinking=plan.thinking,
                time_range=plan.time_range,
                steps=[{"type": s.type, "params": s.params} for s in plan.steps],
                visualizations=plan.visualizations,
                report_prompt=plan.report_prompt,
                notice=plan.notice,
            ),
            data=results,
            report=None,  # Report is loaded separately
            elapsed_ms=total_ms,
            phases=[
                *planner_phases,
                {
                    "name": "Database Query",
                    "status": "completed",
                    "detail": f"Executed {step_count} query{'ies' if step_count != 1 else 'y'}: {step_names}",
                    "elapsed_ms": t_exec,
                },
                {"name": "Response Ready", "status": "completed", "detail": f"Total pipeline: {total_ms}ms", "elapsed_ms": 0},
            ],
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


@router.post("/event-report", response_model=EventReportResponse)
async def generate_event_report(request: EventReportRequest):
    """
    Enhanced event report with storyline, news coverage, and GKG insights.
    Single-call endpoint that returns complete report data.
    """
    t0 = time.time()
    llm_config = request.llm_config.model_dump() if request.llm_config else None

    try:
        reporter = get_enhanced_reporter(llm_config)
        result = await reporter.generate_event_report(
            data=request.data,
            prompt=request.prompt,
            include_storyline=request.include_storyline,
            include_news=request.include_news,
            include_gkg=request.include_gkg,
        )

        t_report = round((time.time() - t0) * 1000, 1)
        print(f"[Analyze/EventReport] Generated in {t_report}ms", flush=True)

        return EventReportResponse(
            report=EnhancedReportOutput(
                summary=result.summary,
                key_findings=result.key_findings,
                storyline=result.storyline,
                news_coverage=result.news_coverage,
                gkg_insights=result.gkg_insights,
                generated_at=result.generated_at,
            ),
            elapsed_ms=t_report,
        )
    except Exception as e:
        print(f"[Analyze/EventReport] FAILED: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Event report generation failed: {e}")


@router.post("/storyline", response_model=StorylineResponse)
async def get_storyline(request: StorylineRequest):
    """
    Get event storyline data (timeline + entities + themes) without LLM report.
    Can be called independently for visualization.
    """
    t0 = time.time()

    try:
        # Fetch event and related events
        events = []
        if request.fingerprint:
            event = await data_service.get_event_detail(request.fingerprint)
            if event:
                events.append(event)
                # Get similar events
                ed = event.get("event_data") or event
                gid = ed.get("GlobalEventID")
                if gid:
                    similar = await data_service.get_similar_events(gid, limit=10)
                    events.extend(similar)

        if not events and request.event_id:
            similar = await data_service.get_similar_events(request.event_id, limit=10)
            events.extend(similar)

        if not events:
            return StorylineResponse(
                storyline=None,
                elapsed_ms=round((time.time() - t0) * 1000, 1),
            )

        # Optionally fetch GKG data
        gkg_themes = None
        if gkg_client.available and events:
            primary = events[0]
            ed = primary.get("event_data") or primary
            date = ed.get("SQLDATE")
            actor = ed.get("Actor1Name")
            if date and actor:
                try:
                    from datetime import datetime, timedelta
                    end_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=2)
                    end_date = end_dt.strftime("%Y-%m-%d")
                    gkg_result = await gkg_client.get_entity_themes(actor, (date, end_date), limit=50)
                    if not gkg_result.get("error"):
                        gkg_themes = gkg_result.get("parsed_themes")
                except Exception as e:
                    print(f"[Storyline] GKG fetch failed: {e}", flush=True)

        storyline = build_full_storyline(events, gkg_themes)

        t_total = round((time.time() - t0) * 1000, 1)
        print(f"[Analyze/Storyline] Built in {t_total}ms, {len(events)} events", flush=True)

        return StorylineResponse(
            storyline=StorylineData(
                timeline=storyline["timeline"],
                entity_evolution=storyline["entity_evolution"],
                theme_evolution=storyline["theme_evolution"],
                narrative_arc=storyline["narrative_arc"],
            ),
            elapsed_ms=t_total,
        )

    except Exception as e:
        print(f"[Analyze/Storyline] FAILED: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Storyline generation failed: {e}")
