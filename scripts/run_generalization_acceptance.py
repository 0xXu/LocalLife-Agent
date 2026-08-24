from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.mcp import load_capability_catalog
from tests.acceptance.generalization_cases import CASES


RETRIEVAL_TOOL_CAPABILITIES = {
    tool: capability.id
    for capability in load_capability_catalog().capabilities
    for tool in capability.retrieval.entry_tools
}
ACTIVE_PHASES = {"understanding", "retrieving", "composing"}


async def await_decision(
    client: httpx.AsyncClient,
    base_url: str,
    task_id: str,
    *,
    timeout_seconds: float = 300,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = await client.get(f"{base_url}/api/tasks/{task_id}", timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get("phase") not in ACTIVE_PHASES:
            return payload
        await asyncio.sleep(0.5)
    raise TimeoutError(f"task {task_id} did not finish its decision turn")


def evaluate(case: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    phase = payload.get("phase")
    traces = payload.get("tool_traces") or []
    capabilities = sorted({
        RETRIEVAL_TOOL_CAPABILITIES[item.get("tool")]
        for item in traces
        if item.get("tool") in RETRIEVAL_TOOL_CAPABILITIES
    })
    mode = case["mode"]
    if mode != "clarify":
        expected_routes = [
            sorted(route)
            for route in case.get("capability_routes", [case["capabilities"]])
        ]
        if capabilities not in expected_routes:
            failures.append(f"供给能力 {capabilities}，预期其一 {expected_routes}")
    if mode == "propose":
        if phase != "awaiting_mandate":
            failures.append(f"阶段为 {phase}，预期 awaiting_mandate")
        plan = payload.get("plan") or (payload.get("policy") or {}).get("primary_plan")
        if not plan:
            failures.append("缺少 PlanGraph")
        else:
            actual_verticals = {item["vertical"] for item in plan.get("nodes", [])}
            missing = set(case["verticals"]) - actual_verticals
            if missing:
                failures.append(f"计划缺少供给域 {sorted(missing)}")
    elif mode in {"clarify", "clarify_after_supply"}:
        if phase != "clarifying":
            failures.append(f"阶段为 {phase}，预期 clarifying")
        question = payload.get("question") or {}
        option_count = len(question.get("options") or [])
        if option_count < 2 or option_count > 4:
            failures.append(f"追问选项数为 {option_count}，预期 2-4")
    elif mode == "unsupported" and phase != "unsupported":
        failures.append(f"阶段为 {phase}，预期 unsupported")
    return failures


async def run_case(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    base_url: str,
    case: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    async with semaphore:
        started = time.perf_counter()
        try:
            response = await client.post(
                f"{base_url}/api/tasks",
                json={
                    "user_id": f"acceptance-{run_id}-{case['id']}",
                    "goal": case["goal"],
                },
                timeout=300,
            )
            if response.status_code != 202:
                latency = round(time.perf_counter() - started, 2)
                detail = response.json().get("detail", response.text[:300])
                result = {**case, "passed": False, "latency_seconds": latency, "failures": [f"HTTP {response.status_code}: {detail}"]}
            else:
                started_task = response.json()
                payload = await await_decision(
                    client,
                    base_url,
                    started_task["id"],
                )
                latency = round(time.perf_counter() - started, 2)
                failures = evaluate(case, payload)
                result = {
                    **case,
                    "passed": not failures,
                    "latency_seconds": latency,
                    "actual_phase": payload.get("phase"),
                    "actual_capabilities": sorted({
                        RETRIEVAL_TOOL_CAPABILITIES[item.get("tool")]
                        for item in payload.get("tool_traces") or []
                        if item.get("tool") in RETRIEVAL_TOOL_CAPABILITIES
                    }),
                    "task_id": payload.get("id"),
                    "failures": failures,
                }
        except Exception as exc:
            result = {
                **case,
                "passed": False,
                "latency_seconds": round(time.perf_counter() - started, 2),
                "failures": [f"{type(exc).__name__}: {exc}"],
            }
        status = "PASS" if result["passed"] else "FAIL"
        print(f"{status} {case['id']} {result['latency_seconds']}s", flush=True)
        return result


def write_report(results: list[dict[str, Any]], output: Path) -> None:
    passed = sum(item["passed"] for item in results)
    average = sum(item["latency_seconds"] for item in results) / len(results)
    lines = [
        "# 泛化验收结果",
        "",
        f"- 时间：{datetime.now(timezone.utc).isoformat()}",
        f"- 通过：{passed}/{len(results)}",
        f"- 平均首轮决策延迟：{average:.2f}s",
        "- 接口：`POST /api/tasks` 立即返回，随后轮询任务状态（真实 DeepSeek + ADK + MCP）",
        "",
        "| 案例 | 结果 | 阶段 | 供给能力 | 延迟 | 失败原因 |",
        "|---|---|---|---|---:|---|",
    ]
    for item in results:
        failures = "；".join(item.get("failures") or [])
        lines.append(
            f"| {item['id']} | {'通过' if item['passed'] else '失败'} | "
            f"{item.get('actual_phase', '-')} | {', '.join(item.get('actual_capabilities', [])) or '-'} | "
            f"{item['latency_seconds']:.2f}s | {failures or '-'} |"
        )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--output", default="research/generalization-acceptance.md")
    parser.add_argument("--case", action="append", dest="case_ids")
    args = parser.parse_args()
    known_case_ids = {case["id"] for case in CASES}
    unknown_case_ids = sorted(set(args.case_ids or []) - known_case_ids)
    if unknown_case_ids:
        parser.error(f"unknown case id(s): {', '.join(unknown_case_ids)}")
    selected = [case for case in CASES if not args.case_ids or case["id"] in args.case_ids]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    semaphore = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[
            run_case(client, semaphore, args.base_url.rstrip("/"), case, run_id)
            for case in selected
        ])
    write_report(results, Path(args.output))
    passed = sum(item["passed"] for item in results)
    print(json.dumps({"passed": passed, "total": len(results), "output": args.output}, ensure_ascii=False))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
