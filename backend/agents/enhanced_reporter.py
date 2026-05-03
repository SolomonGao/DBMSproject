"""
Enhanced Report Generator — Comprehensive event reporting with storyline, news, and GKG.

Extends the base ReportGenerator to produce structured reports containing:
- Executive summary and key findings
- Storyline (timeline + entity evolution + theme evolution)
- News coverage (SOURCEURL + ChromaDB)
- GKG insights (entities, themes, tone)
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from backend.agents.planner import ReportGenerator, ReportResult, build_llm
from backend.services.news_scraper import news_scraper
from backend.services.storyline_builder import build_full_storyline
from backend.services.gkg_client import gkg_client


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

ENHANCED_REPORT_SYSTEM_PROMPT = """You are an expert geopolitical event analyst and narrative journalist.
Your task is to produce a comprehensive, well-structured report on a specific event or event series.

You will receive:
1. Event metadata (dates, locations, actors, metrics)
2. News article content (from original sources)
3. Storyline data (timeline, entity evolution, theme evolution)
4. GKG insights (media entities, themes, tone trends)

Output rules:
- Write in clear, journalistic prose.
- Use specific dates, names, and numbers from the data.
- Cite source counts (NumArticles) as evidence of significance.
- Structure the output into clearly labeled sections.
- Do NOT use JSON. Use markdown-style plain text.
- If data is sparse, say so directly rather than inventing.
- No preamble like "Here is the report". Start immediately."""


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class NewsSourceData:
    """Structured news source data."""
    url: str
    title: Optional[str]
    content_snippet: str
    fetch_status: str


class EnhancedReportResult:
    """Comprehensive event report result."""

    def __init__(
        self,
        summary: str,
        key_findings: List[str],
        storyline: Optional[Dict[str, Any]] = None,
        news_coverage: Optional[Dict[str, Any]] = None,
        gkg_insights: Optional[Dict[str, Any]] = None,
        generated_at: Optional[str] = None,
    ):
        self.summary = summary
        self.key_findings = key_findings
        self.storyline = storyline
        self.news_coverage = news_coverage
        self.gkg_insights = gkg_insights
        self.generated_at = generated_at or __import__("datetime").datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "key_findings": self.key_findings,
            "storyline": self.storyline,
            "news_coverage": self.news_coverage,
            "gkg_insights": self.gkg_insights,
            "generated_at": self.generated_at,
        }


# ---------------------------------------------------------------------------
# Enhanced Report Generator
# ---------------------------------------------------------------------------

class EnhancedReportGenerator(ReportGenerator):
    """Extended report generator with storyline, news coverage, and GKG insights."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._news_scraper = news_scraper
        self._gkg = gkg_client

    # -- Helpers: find events from step results with suffixed keys --

    @staticmethod
    def _find_primary_event(event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find the primary event from step results.

        Step result keys are suffixed (e.g. event_detail_0, events_1) so we
        scan for both exact matches and prefix matches.
        """
        # Exact keys first
        for exact_key in ("event_detail", "events", "top_events", "hot_events"):
            if exact_key in event_data:
                item = event_data[exact_key]
                if isinstance(item, dict) and "data" in item:
                    return item["data"]
                elif isinstance(item, list) and item:
                    return item[0]
                return item

        # Prefixed keys (e.g. event_detail_0, events_1)
        for key, item in event_data.items():
            if key.startswith("event_detail"):
                if isinstance(item, dict) and "data" in item:
                    return item["data"]
                return item

        for key, item in event_data.items():
            if key.startswith(("events_", "top_events_", "hot_events_")):
                if isinstance(item, dict) and "data" in item:
                    item = item["data"]
                if isinstance(item, list) and item:
                    return item[0]
                return item

        return None

    @staticmethod
    def _find_related_events(event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find related events (similar_events or fallback to events list)."""
        related: List[Dict[str, Any]] = []

        # Exact key
        if "similar_events" in event_data:
            se = event_data["similar_events"]
            if isinstance(se, dict) and "data" in se:
                se = se["data"]
            if isinstance(se, list):
                related = se[:5]

        # Prefixed key
        if not related:
            for key, item in event_data.items():
                if key.startswith("similar_events"):
                    if isinstance(item, dict) and "data" in item:
                        item = item["data"]
                    if isinstance(item, list):
                        related = item[:5]
                        break

        # Fallback to any event list
        if not related:
            for key, item in event_data.items():
                if key.startswith(("events_", "top_events_", "hot_events_")):
                    if isinstance(item, dict) and "data" in item:
                        item = item["data"]
                    if isinstance(item, list) and item:
                        related = item[:5]
                        break

        return related

    # -- Data gathering --

    async def _gather_news_coverage(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch news coverage for the primary event."""
        primary_event = self._find_primary_event(event_data)

        if not primary_event:
            return {"sources": [], "primary_content": "", "has_content": False}

        return await self._news_scraper.fetch_for_event(primary_event)

    async def _gather_related_news(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch news for related events (similar_events, etc.)."""
        related_events = self._find_related_events(event_data)

        if not related_events:
            return []

        return await self._news_scraper.fetch_for_events(related_events)

    async def _gather_gkg_data(
        self,
        event_data: Dict[str, Any],
        tone_days: int = 14,
        themes_days: int = 1,
        cooccurring_limit: int = 30,
    ) -> Optional[Dict[str, Any]]:
        """Fetch GKG data for the primary event's actors/entities.
        
        Args:
            tone_days: Days of tone timeline (3-14, centered on event date)
            themes_days: Days of themes query (1-7)
            cooccurring_limit: Max co-occurring entities to fetch
        """
        if not self._gkg.available:
            return None

        primary_event = self._find_primary_event(event_data)

        if not primary_event:
            return None

        ed = primary_event.get("event_data") or primary_event
        date = ed.get("SQLDATE") or primary_event.get("SQLDATE")
        actor1 = ed.get("Actor1Name") or primary_event.get("Actor1Name")

        if not date or not actor1:
            return None

        gkg_results = {}
        dt = __import__("datetime").datetime
        td = __import__("datetime").timedelta

        try:
            cooccur = await self._gkg.get_cooccurring_entities(actor1, date, limit=cooccurring_limit)
            if not cooccur.get("error"):
                gkg_results["cooccurring"] = cooccur.get("cooccurring_entities", {})

            # Themes: configurable days (1-7)
            themes_end = dt.strptime(date, "%Y-%m-%d") + td(days=max(themes_days - 1, 0))
            themes = await self._gkg.get_entity_themes(
                actor1,
                (date, themes_end.strftime("%Y-%m-%d")),
                limit=50,
            )
            if not themes.get("error"):
                gkg_results["themes"] = themes.get("parsed_themes", {})
            else:
                print(f"[EnhancedReporter] GKG themes: {themes.get('message')}", flush=True)

            # Tone timeline: configurable days (3-14), centered on event date
            half_window = tone_days // 2
            tone_start = dt.strptime(date, "%Y-%m-%d") - td(days=half_window)
            tone_end = dt.strptime(date, "%Y-%m-%d") + td(days=tone_days - half_window - 1)
            tone = await self._gkg.get_tone_timeline(
                actor1,
                (tone_start.strftime("%Y-%m-%d"), tone_end.strftime("%Y-%m-%d"))
            )
            if not tone.get("error"):
                gkg_results["tone_timeline"] = tone.get("data", [])

        except Exception as e:
            print(f"[EnhancedReporter] GKG query failed: {e}", flush=True)
            return None

        return gkg_results

    # -- Storyline building --

    def _extract_events_for_storyline(self, event_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all events from step results for storyline building."""
        all_events = []

        # Exact keys
        if "event_detail" in event_data:
            detail = event_data["event_detail"]
            if isinstance(detail, dict) and "data" in detail:
                all_events.append(detail["data"])
            elif isinstance(detail, dict):
                all_events.append(detail)

        if "similar_events" in event_data:
            se = event_data["similar_events"]
            if isinstance(se, dict) and "data" in se:
                se = se["data"]
            if isinstance(se, list):
                all_events.extend(se)

        for key in ("events", "top_events", "hot_events"):
            if key in event_data:
                items = event_data[key]
                if isinstance(items, dict) and "data" in items:
                    items = items["data"]
                if isinstance(items, list):
                    all_events.extend(items)

        # Prefixed keys (e.g. event_detail_0, similar_events_1, events_0)
        for key, item in event_data.items():
            if key.startswith("event_detail") and key != "event_detail":
                if isinstance(item, dict) and "data" in item:
                    all_events.append(item["data"])
                elif isinstance(item, dict):
                    all_events.append(item)
            elif key.startswith("similar_events") and key != "similar_events":
                if isinstance(item, dict) and "data" in item:
                    item = item["data"]
                if isinstance(item, list):
                    all_events.extend(item)
            elif any(key.startswith(prefix) and key != prefix for prefix in ("events_", "top_events_", "hot_events_")):
                if isinstance(item, dict) and "data" in item:
                    item = item["data"]
                if isinstance(item, list):
                    all_events.extend(item)

        seen = set()
        unique = []
        for e in all_events:
            ed = e.get("event_data") or e
            eid = ed.get("GlobalEventID") or e.get("global_event_id")
            if eid and eid not in seen:
                seen.add(eid)
                unique.append(e)
            elif not eid:
                unique.append(e)

        return unique

    # -- Report generation --

    async def generate_event_report(
        self,
        data: Dict[str, Any],
        prompt: Optional[str] = None,
        include_storyline: bool = True,
        include_news: bool = False,
        include_gkg: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> EnhancedReportResult:
        """Generate comprehensive event report with all enrichments.
        
        Args:
            config: Optional dict with keys:
                - gkg_tone_days (3-14): Days of tone timeline
                - gkg_themes_days (1-7): Days of themes query
                - gkg_cooccurring_limit (10-100): Co-occurring entities limit
                - max_report_length (4000-16000): Max report chars
        """
        t0 = __import__("time").time()
        cfg = config or {}
        tone_days = min(max(cfg.get("gkg_tone_days", 14), 3), 14)
        themes_days = min(max(cfg.get("gkg_themes_days", 1), 1), 7)
        cooccur_limit = min(max(cfg.get("gkg_cooccurring_limit", 30), 10), 100)
        max_length = min(max(cfg.get("max_report_length", 12000), 4000), 16000)

        gather_tasks = []

        if include_news:
            gather_tasks.append(self._gather_news_coverage(data))
            gather_tasks.append(self._gather_related_news(data))
        else:
            gather_tasks.append(asyncio.sleep(0))
            gather_tasks.append(asyncio.sleep(0))

        if include_gkg:
            gather_tasks.append(self._gather_gkg_data(
                data,
                tone_days=tone_days,
                themes_days=themes_days,
                cooccurring_limit=cooccur_limit,
            ))
        else:
            gather_tasks.append(asyncio.sleep(0))

        news_coverage, related_news, gkg_data = await asyncio.gather(*gather_tasks)

        storyline = None
        if include_storyline:
            events = self._extract_events_for_storyline(data)
            gkg_themes = gkg_data.get("themes") if gkg_data else None
            storyline = build_full_storyline(events, gkg_themes)

        narrative_input = self._format_enhanced_data(
            data, news_coverage, related_news, storyline, gkg_data,
            max_length=max_length,
        )

        if not narrative_input.strip():
            return EnhancedReportResult(
                summary="No event data available for report generation.",
                key_findings=[],
            )

        user_prompt = prompt or (
            "Write a comprehensive event report covering: what happened, "
            "who was involved, the timeline of events, media coverage, and broader implications."
        )

        messages = [
            SystemMessage(content=ENHANCED_REPORT_SYSTEM_PROMPT),
            HumanMessage(content=f"{user_prompt}\n\n{narrative_input}\n\nWrite the report:"),
        ]

        try:
            response = await asyncio.wait_for(self.llm.ainvoke(messages), timeout=120.0)
            text = self._get_response_text(response)

            text = re.sub(r"^```.*?\n", "", text, flags=re.DOTALL)
            text = re.sub(r"\n```$", "", text)

            if not text:
                return EnhancedReportResult(
                    summary="No report content was generated.",
                    key_findings=[],
                    storyline=storyline if isinstance(storyline, dict) else (storyline.to_dict() if storyline else None),
                    news_coverage=news_coverage if isinstance(news_coverage, dict) else None,
                    gkg_insights=gkg_data,
                )

            summary, findings = self._parse_report_text(text)

            elapsed = round((__import__("time").time() - t0) * 1000, 1)
            print(
                f"[EnhancedReportGenerator] Report generated in {elapsed}ms: "
                f"{len(summary)} chars, {len(findings)} findings",
                flush=True,
            )

            return EnhancedReportResult(
                summary=summary,
                key_findings=findings,
                storyline=storyline if isinstance(storyline, dict) else (storyline.to_dict() if storyline else None),
                news_coverage=news_coverage if isinstance(news_coverage, dict) else None,
                gkg_insights=gkg_data,
            )

        except asyncio.TimeoutError:
            return EnhancedReportResult(
                summary="AI report generation timed out. The event data is still available.",
                key_findings=[],
                storyline=storyline if isinstance(storyline, dict) else (storyline.to_dict() if storyline else None),
                news_coverage=news_coverage if isinstance(news_coverage, dict) else None,
                gkg_insights=gkg_data,
            )
        except Exception as e:
            print(f"[EnhancedReportGenerator] Failed: {e}", flush=True)
            return EnhancedReportResult(
                summary="Unable to generate AI report at this time.",
                key_findings=[],
                storyline=storyline if isinstance(storyline, dict) else (storyline.to_dict() if storyline else None),
                news_coverage=news_coverage if isinstance(news_coverage, dict) else None,
                gkg_insights=gkg_data,
            )

    def _format_enhanced_data(
        self,
        data: Dict[str, Any],
        news_coverage: Any,
        related_news: Any,
        storyline: Any,
        gkg_data: Optional[Dict[str, Any]],
        max_length: int = 12000,
    ) -> str:
        """Format all gathered data into a narrative input for the LLM."""
        sections = []

        base_formatted = self._format_data_for_report(data)
        if base_formatted:
            sections.append("=== EVENT DATA ===")
            sections.append(base_formatted)

        if isinstance(news_coverage, dict) and news_coverage.get("has_content"):
            sections.append("\n=== NEWS COVERAGE ===")
            sections.append(f"Primary Headline: {news_coverage.get('headline', '')}")
            sections.append(f"Sources: {news_coverage.get('source_count', 0)}")

            content = news_coverage.get("primary_content", "")
            if content:
                if len(content) > 4000:
                    content = content[:4000] + "\n...[content continues but truncated for brevity]"
                sections.append(f"Primary Article Content:\n{content}")

            if isinstance(related_news, list) and related_news:
                sections.append("\nRelated Event Coverage:")
                for i, rn in enumerate(related_news[:3]):
                    if rn.get("has_content"):
                        snippet = rn.get("primary_content", "")[:500]
                        sections.append(f"  [{i+1}] {rn.get('headline', '')}: {snippet}")

        if storyline:
            sections.append("\n=== STORYLINE ===")
            narrative_arc = storyline.get("narrative_arc") if isinstance(storyline, dict) else storyline.narrative_arc
            sections.append(narrative_arc)

            timeline = storyline.get("timeline") if isinstance(storyline, dict) else storyline.timeline
            if timeline.get("key_milestones"):
                sections.append("\nKey Milestones:")
                for m in timeline["key_milestones"]:
                    sections.append(f"  - {m['date']}: {m['title']}")

        if gkg_data:
            sections.append("\n=== MEDIA KNOWLEDGE GRAPH INSIGHTS ===")

            cooccur = gkg_data.get("cooccurring")
            if cooccur:
                persons = cooccur.get("top_persons", [])
                if persons:
                    sections.append("Related People in Media:")
                    for p in persons[:8]:
                        sections.append(f"  - {p['name']} ({p['count']} mentions)")

                orgs = cooccur.get("top_organizations", [])
                if orgs:
                    sections.append("Related Organizations:")
                    for o in orgs[:5]:
                        sections.append(f"  - {o['name']} ({o['count']} mentions)")

            themes = gkg_data.get("themes")
            if themes:
                top = themes.get("top_themes", [])
                if top:
                    sections.append("Media Themes:")
                    for t in top[:8]:
                        sections.append(f"  - {t['theme']} ({t['count']} mentions)")

            tone = gkg_data.get("tone_timeline")
            if tone and isinstance(tone, list):
                sections.append("Media Tone Trend:")
                for t in tone[:14]:
                    sections.append(f"  - {t.get('date', '')}: tone={t.get('avg_tone', 'N/A'):.2f}, mentions={t.get('mention_count', 0)}")

        result = "\n".join(sections)
        if len(result) > max_length:
            result = result[:max_length - 500] + "\n\n...[additional data truncated — core insights preserved above]"
        return result

    def _parse_report_text(self, text: str) -> tuple[str, List[str]]:
        """Parse LLM output into summary and key findings."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        summary_lines = []
        findings = []
        in_findings = False

        for line in lines:
            lower = line.lower()
            if any(k in lower for k in ("key finding", "findings", "highlights", "key points", "takeaways")):
                in_findings = True
                continue

            if in_findings:
                if line.startswith(("- ", "* ", "• ")):
                    findings.append(line[2:].strip())
                elif line[0].isdigit() and "." in line[:3]:
                    findings.append(line[line.find(".") + 1:].strip())
                elif len(line) < 100 and not line.endswith("."):
                    findings.append(line)
                else:
                    findings.append(line)
            else:
                summary_lines.append(line)

        summary = "\n".join(summary_lines) if summary_lines else text
        if len(summary) > 4000:
            summary = summary[:4000] + "..."

        return summary, findings


# Singleton (lazy init to avoid API key requirement at import time)
_enhanced_reporter_instance: Optional[EnhancedReportGenerator] = None

def get_enhanced_reporter(config: Optional[Dict[str, Any]] = None) -> EnhancedReportGenerator:
    global _enhanced_reporter_instance
    if _enhanced_reporter_instance is None:
        _enhanced_reporter_instance = EnhancedReportGenerator(config)
    return _enhanced_reporter_instance
