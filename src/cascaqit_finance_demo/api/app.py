"""为金融 Demo 前端提供业务分析、量子执行和静态资源的 FastAPI 应用。"""

from __future__ import annotations

import logging
import os
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

from cascaqit.exceptions import CapabilityError
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cascaqit_finance_demo.api.catalog import (
    SCENARIO_SPECS,
    build_case_input,
    control_values,
    preset_input,
)
from cascaqit_finance_demo.api.presenters import analysis_payload, execution_payload
from cascaqit_finance_demo.cases.problem_scenarios import PROBLEM_SCENARIOS
from cascaqit_finance_demo.quantum.problem_executor import (
    ScenarioExecutor,
)

# 前端构建产物随 Python wheel 一起安装，不能依赖源码仓库中的 frontend/dist。
# 这样复制到离线机器后，仅安装 wheel 就能提供完整页面。
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PACKAGE_ROOT / "static"

# 报告属于运行数据，不应写入只读的 site-packages。启动脚本会把数据目录指向
# 离线包根目录；其他调用方式默认写入当前工作目录，环境变量可显式覆盖。
DATA_DIR = Path(os.environ.get("CASCAQIT_FINANCE_DATA_DIR", Path.cwd())).resolve()
REPORT_DIR = DATA_DIR / "artifacts" / "reports"
HOST = "127.0.0.1"
PORT = int(os.environ.get("CASCAQIT_FINANCE_PORT", "8000"))
LOGGER = logging.getLogger(__name__)


class ScenarioRequest(BaseModel):
    """分析和执行请求共用的业务预设及可编辑控件值。"""

    # Pydantic 在 Python 3.9 中会运行时求值类型标注，无法回移植 ``str | None``，
    # 因此这里保留 Optional 写法以兼容项目支持的最低 Python 版本。
    preset: Optional[str] = None  # noqa: UP007
    values: dict[str, Any] = Field(default_factory=dict)


class RunRequest(ScenarioRequest):
    """与业务输入分离的可选执行参数；省略项使用场景推荐配置。"""

    mode: Literal["recommended", "digital", "hybrid", "analog"] = "recommended"
    shots: Optional[int] = Field(default=None, ge=1, le=1024)  # noqa: UP007
    seed: Optional[int] = Field(default=None, ge=0)  # noqa: UP007
    layers: Optional[int] = Field(default=None, ge=1, le=3)  # noqa: UP007
    search_strategy: Optional[  # noqa: UP007
        Literal["preset", "grid", "seeded_sample"]
    ] = None
    parameter_budget: Optional[int] = Field(  # noqa: UP007
        default=None, ge=1, le=24
    )


app = FastAPI(
    title="CASCAQit Finance API",
    version="1.0",
    description="Offline finance experiments backed by CASCAQit Problem API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _scenario(case_id: str) -> Any:
    """按稳定场景 ID 取领域实现，并把未知 ID 转换为 HTTP 404。"""
    try:
        return PROBLEM_SCENARIOS[case_id]
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"unknown scenario: {case_id}"
        ) from exc


def _request_input(case_id: str, request: ScenarioRequest) -> tuple[str, Any]:
    """校验预设并把松散 JSON 控件值还原为强类型场景输入。"""
    spec = SCENARIO_SPECS.get(case_id)
    if spec is None:
        _scenario(case_id)
        raise AssertionError("unreachable")
    preset = request.preset or spec.presets[0][0]
    if preset not in {value for value, _label in spec.presets}:
        raise HTTPException(status_code=422, detail=f"unknown preset: {preset}")
    try:
        return preset, build_case_input(case_id, preset, request.values)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict[str, Any]:
    """返回服务边界和执行环境事实，供前端启动检查。"""
    return {
        "status": "ok",
        "service": "cascaqit-finance-api",
        "execution": "local_simulation",
        "hardware": False,
        "cloud": False,
    }


@app.get("/api/scenarios")
def scenarios() -> dict[str, Any]:
    """分析七个默认场景并返回导航、控件和推荐模式目录。"""
    executor = ScenarioExecutor()
    items = []
    for case_id, spec in SCENARIO_SPECS.items():
        case_input = preset_input(case_id, spec.presets[0][0])
        analysis = executor.analyze(_scenario(case_id), case_input)
        items.append(
            spec.to_dict(
                values=control_values(case_id, case_input),
                recommended_mode=analysis.mode_decision.recommended_mode,
            )
        )
    return {"scenarios": items}


@app.post("/api/scenarios/{case_id}/analyze")
def analyze(case_id: str, request: ScenarioRequest) -> dict[str, Any]:
    """只执行输入验证与编译器分析，不触发量子模拟。"""
    preset, case_input = _request_input(case_id, request)
    executor = ScenarioExecutor()
    try:
        analysis = executor.analyze(_scenario(case_id), case_input)
    except CapabilityError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "message": str(exc),
                "stage": exc.stage,
                "error_id": exc.error_id,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        error_id = uuid4().hex
        LOGGER.exception("场景执行失败，error_id=%s", error_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "internal_execution_error",
                "message": "量子实验执行失败，请保留错误编号并联系技术支持。",
                "error_id": error_id,
            },
        ) from exc
    spec = SCENARIO_SPECS[case_id]
    return {
        "scenario": spec.to_dict(
            values=control_values(case_id, case_input),
            recommended_mode=analysis.mode_decision.recommended_mode,
        ),
        "preset": preset,
        "analysis": analysis_payload(case_id, case_input, analysis),
    }


@app.post("/api/scenarios/{case_id}/run")
async def run_scenario(case_id: str, request: RunRequest) -> dict[str, Any]:
    """在线程池运行同步模拟器，避免阻塞 FastAPI 事件循环。"""
    preset, case_input = _request_input(case_id, request)
    # 推荐配置由场景目录统一维护。API 调用方可以只覆盖关心的字段，其余字段
    # 继续沿用已验收值，避免 Web UI 与脚本调用产生两套隐式默认值。
    profile = SCENARIO_SPECS[case_id].recommended_execution
    shots = request.shots if request.shots is not None else profile.shots
    seed = request.seed if request.seed is not None else profile.seed
    layers = request.layers if request.layers is not None else profile.layers
    search_strategy = request.search_strategy or profile.search_strategy
    parameter_budget = (
        request.parameter_budget
        if request.parameter_budget is not None
        else profile.parameter_budget
    )
    executor = ScenarioExecutor()
    scenario = _scenario(case_id)
    try:
        preflight = executor.analyze(scenario, case_input)
        selected_mode = (
            preflight.mode_decision.recommended_mode
            if request.mode == "recommended"
            else request.mode
        )
        result = await run_in_threadpool(
            executor.run,
            scenario,
            case_input,
            mode=selected_mode,
            layers=layers,
            search_strategy=search_strategy,
            parameter_budget=parameter_budget,
            shots=shots,
            seed=seed,
            report_path=REPORT_DIR / f"{case_id}-{selected_mode}.html",
        )
    except CapabilityError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": exc.code,
                "message": str(exc),
                "stage": exc.stage,
                "error_id": exc.error_id,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        error_id = uuid4().hex
        LOGGER.exception("场景执行失败，error_id=%s", error_id)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "internal_execution_error",
                "message": "量子实验执行失败，请保留错误编号并联系技术支持。",
                "error_id": error_id,
            },
        ) from exc
    return {
        "scenario": SCENARIO_SPECS[case_id].to_dict(
            values=control_values(case_id, case_input),
            recommended_mode=result.analysis.mode_decision.recommended_mode,
        ),
        "preset": preset,
        "run": execution_payload(case_id, case_input, result),
    }


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


def run() -> None:
    """以固定本地地址启动 API 和已构建前端，关闭热重载保持演示稳定。"""
    import uvicorn

    uvicorn.run(
        "cascaqit_finance_demo.api.app:app",
        host=HOST,
        port=PORT,
        reload=False,
    )


def _open_browser_when_ready(url: str) -> None:
    """等待健康接口可访问后再打开浏览器，避免用户先看到连接失败页面。"""

    health_url = f"{url}/api/health"
    # 企业 Windows 常配置全局 HTTP 代理；本机健康检查必须绕过代理，否则可能
    # 出现服务已就绪但轮询请求被代理拦截、浏览器迟迟不打开的假故障。
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _attempt in range(100):
        try:
            with opener.open(health_url, timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except (OSError, urllib.error.URLError):
            # 服务通常在一秒内就绪；短轮询同时兼容性能较慢的离线演示机器。
            time.sleep(0.1)


def launch() -> None:
    """启动本地服务，并在服务就绪后用系统默认浏览器打开实验台。"""

    url = f"http://{HOST}:{PORT}"
    browser_thread = threading.Thread(
        target=_open_browser_when_ready,
        args=(url,),
        daemon=True,
        name="cascaqit-finance-browser",
    )
    browser_thread.start()
    run()
