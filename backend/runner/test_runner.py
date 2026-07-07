from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.api.serializers import (
    serialize_hardware_profile,
    serialize_test_case,
    serialize_test_run,
    serialize_test_step,
    serialize_test_step_result,
)
from backend.db.models import HardwareProfile, TestCase, TestRun, TestStep, TestStepResult
from backend.runner.step_executor import execute_step


async def run_test_case_sync(
    *,
    hardware_profile_id: int,
    test_case_id: int,
    name: str | None = None,
) -> dict[str, Any]:
    profile = await HardwareProfile.get_or_none(id=hardware_profile_id)
    if profile is None:
        raise ValueError("hardware profile not found")

    test_case = await TestCase.get_or_none(id=test_case_id)
    if test_case is None:
        raise ValueError("test case not found")
    if not test_case.enabled:
        raise ValueError("test case is disabled")

    steps = await TestStep.filter(case_id=test_case_id).order_by("order_index", "id")
    if not steps:
        raise ValueError("test case has no steps")

    started_at = _now()
    profile_snapshot = serialize_hardware_profile(profile)
    case_snapshot = serialize_test_case(test_case)
    case_snapshot["steps"] = [serialize_test_step(step) for step in steps]

    run = await TestRun.create(
        hardware_profile=profile,
        test_case=test_case,
        name=name or f"{test_case.name} @ {started_at.isoformat()}",
        status="running",
        result=None,
        summary="测试运行中",
        error_message="",
        profile_snapshot_json=profile_snapshot,
        case_snapshot_json=case_snapshot,
        started_at=started_at,
    )

    final_status = "passed"
    summary = "测试通过"
    error_message = ""

    for step in steps:
        step_started_at = _now()
        execution = await execute_step(profile=profile, step=step)
        step_finished_at = _now()
        driver_result = execution.driver_result
        step_status = "passed" if driver_result.success else execution.failure_kind or "error"

        await TestStepResult.create(
            run=run,
            test_step=step,
            order_index=step.order_index,
            step_name=step.name,
            step_type=step.step_type,
            name=step.name,
            type=step.step_type,
            status=step_status,
            result="pass" if step_status == "passed" else step_status,
            message=driver_result.message,
            stdout=driver_result.stdout,
            stderr=driver_result.stderr,
            data_json=_json_safe(driver_result.data),
            log=driver_result.message,
            started_at=step_started_at,
            finished_at=step_finished_at,
            duration_ms=_duration_ms(step_started_at, step_finished_at),
            ended_at=step_finished_at,
        )

        if step_status != "passed":
            final_status = "failed" if step_status == "failed" else "error"
            summary = "测试失败" if final_status == "failed" else "测试异常"
            error_message = driver_result.message
            break

    finished_at = _now()
    run.status = final_status
    run.result = "pass" if final_status == "passed" else final_status
    run.summary = summary
    run.error_message = error_message
    run.finished_at = finished_at
    run.ended_at = finished_at
    run.duration_ms = _duration_ms(started_at, finished_at)
    await run.save()

    return await get_test_run_detail(run.id)


async def get_test_run_detail(run_id: int) -> dict[str, Any] | None:
    run = await TestRun.get_or_none(id=run_id)
    if run is None:
        return None
    results = await TestStepResult.filter(run_id=run_id).order_by("order_index", "id")
    payload = serialize_test_run(run)
    payload["run_id"] = run.id
    payload["steps"] = [serialize_test_step_result(result) for result in results]
    return payload


async def list_test_run_details() -> list[dict[str, Any]]:
    runs = await TestRun.all().order_by("-id")
    return [serialize_test_run(run) for run in runs]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return int((finished_at - started_at).total_seconds() * 1000)


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value
