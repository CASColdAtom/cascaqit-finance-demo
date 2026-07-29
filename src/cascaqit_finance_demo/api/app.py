"""为行业量子实验台提供领域目录、量子执行和静态资源。"""

from __future__ import annotations

import logging
import os
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Literal, Optional
from uuid import uuid4

from cascaqit.exceptions import CapabilityError
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cascaqit_biomedicine_demo.catalog import (
    BIOMEDICINE_SCENARIO_SPECS,
    preview_analysis,
)
from cascaqit_biomedicine_demo.docking import (
    analyze_docking_match,
    docking_values,
    run_docking_match,
)
from cascaqit_biomedicine_demo.electronic_structure import (
    analyze_electronic_structure,
    run_electronic_structure,
)
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
DATA_DIR = Path(
    os.environ.get(
        "CASCAQIT_INDUSTRY_DATA_DIR",
        os.environ.get("CASCAQIT_FINANCE_DATA_DIR", Path.cwd()),
    )
).resolve()
REPORT_DIR = DATA_DIR / "artifacts" / "reports"
HOST = "127.0.0.1"
PORT = int(
    os.environ.get(
        "CASCAQIT_INDUSTRY_PORT",
        os.environ.get("CASCAQIT_FINANCE_PORT", "8000"),
    )
)
LOGGER = logging.getLogger(__name__)


class ScenarioRequest(BaseModel):
    """分析和执行请求共用的业务预设及可编辑控件值。"""

    # Pydantic 在 Python 3.9 中会运行时求值类型标注，无法回移植 ``str | None``，
    # 因此这里保留 Optional 写法以兼容项目支持的最低 Python 版本。
    preset: Optional[str] = None  # noqa: UP045
    values: dict[str, Any] = Field(default_factory=dict)


class RunRequest(ScenarioRequest):
    """与业务输入分离的可选执行参数；省略项使用场景推荐配置。"""

    mode: Literal["recommended", "digital", "hybrid", "analog"] = "recommended"
    algorithm: Optional[  # noqa: UP045
        Literal["recommended", "qaoa", "vqe", "qaa"]
    ] = None
    layer_policy: Optional[Literal["fixed", "adaptive"]] = None  # noqa: UP045
    shots: Optional[int] = Field(default=None, ge=1, le=1024)  # noqa: UP045
    seed: Optional[int] = Field(default=None, ge=0)  # noqa: UP045
    layers: Optional[int] = Field(default=None, ge=1, le=3)  # noqa: UP045
    max_layers: Optional[int] = Field(default=None, ge=1, le=3)  # noqa: UP045
    min_improvement: Optional[float] = Field(default=None, ge=0.0)  # noqa: UP045
    search_strategy: Optional[  # noqa: UP045
        Literal["preset", "grid", "seeded_sample", "continuous"]
    ] = None
    parameter_budget: Optional[int] = Field(  # noqa: UP045
        default=None, ge=1, le=80
    )
    optimizer_starts: Optional[int] = Field(default=None, ge=1, le=3)  # noqa: UP045
    repeats: Optional[int] = Field(default=None, ge=1, le=5)  # noqa: UP045


app = FastAPI(
    title="CASColdAtom Industry Quantum Workbench API",
    version="1.0",
    description="Offline industry experiments backed by CASCAQit.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def prevent_stale_frontend_entry(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """禁止缓存前端入口，确保每次打开页面都引用当前构建产物。"""

    response = await call_next(request)
    if request.url.path in {"/", "/index.html"} and response.status_code == 200:
        # JavaScript 文件名包含内容哈希，可以由浏览器长期缓存；入口 HTML 不能长期
        # 缓存，否则升级后的页面仍会请求上一版 chunk，并继续执行已经修复的旧代码。
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


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
        "service": "cascaqit-industry-api",
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


@app.get("/api/domains")
def domains() -> dict[str, Any]:
    """Return the product-level domains without mixing their scenario catalogs."""
    return {
        "domains": [
            {
                "id": "finance",
                "label": "金融",
                "shortLabel": "金融",
                "description": "组合优化、资源编排与风险情景实验",
                "scenarioCount": len(SCENARIO_SPECS),
            },
            {
                "id": "biomedicine",
                "label": "生物医药",
                "shortLabel": "生物医药",
                "description": "电子结构、构象匹配、有效自旋与小肽能景实验",
                "scenarioCount": len(BIOMEDICINE_SCENARIO_SPECS),
            },
        ]
    }


@app.get("/api/domains/{domain_id}/scenarios")
def domain_scenarios(domain_id: str) -> dict[str, Any]:
    """Return only scenarios owned by the requested product domain."""
    if domain_id == "finance":
        return scenarios()
    if domain_id == "biomedicine":
        return {
            "scenarios": [
                spec.to_dict() for spec in BIOMEDICINE_SCENARIO_SPECS.values()
            ]
        }
    raise HTTPException(status_code=404, detail=f"unknown domain: {domain_id}")


def _biomedicine_request(
    case_id: str, request: ScenarioRequest
) -> tuple[str, dict[str, Any]]:
    try:
        spec = BIOMEDICINE_SCENARIO_SPECS[case_id]
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"unknown biomedicine scenario: {case_id}"
        ) from exc
    preset = request.preset or spec.presets[0][0]
    if preset not in {value for value, _label in spec.presets}:
        raise HTTPException(status_code=422, detail=f"unknown preset: {preset}")
    allowed = {control.key for control in spec.controls}
    unknown = set(request.values) - allowed
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown control values: {', '.join(sorted(unknown))}",
        )
    if case_id == "docking_match":
        try:
            values = docking_values(preset, request.values)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        values = {
            key: values[key]
            for key in ("match_weight", "collision_penalty", "coverage_weight")
        }
    else:
        values = {**spec.values, **request.values}
    return preset, values


@app.post("/api/domains/{domain_id}/scenarios/{case_id}/analyze")
def analyze_domain_scenario(
    domain_id: str, case_id: str, request: ScenarioRequest
) -> dict[str, Any]:
    """Analyze a domain scenario while preserving the legacy finance route."""
    if domain_id == "finance":
        return analyze(case_id, request)
    if domain_id != "biomedicine":
        raise HTTPException(status_code=404, detail=f"unknown domain: {domain_id}")
    preset, values = _biomedicine_request(case_id, request)
    if case_id == "electronic_structure":
        analysis = analyze_electronic_structure()
    elif case_id == "docking_match":
        analysis = analyze_docking_match(preset, values)
    else:
        analysis = preview_analysis(case_id)
    scenario = BIOMEDICINE_SCENARIO_SPECS[case_id].to_dict()
    scenario["values"] = values
    return {"scenario": scenario, "preset": preset, "analysis": analysis}


@app.post("/api/domains/{domain_id}/scenarios/{case_id}/run")
async def run_domain_scenario(
    domain_id: str, case_id: str, request: RunRequest
) -> dict[str, Any]:
    """Execute an available domain scenario through its native execution family."""
    if domain_id == "finance":
        return await run_scenario(case_id, request)
    if domain_id != "biomedicine":
        raise HTTPException(status_code=404, detail=f"unknown domain: {domain_id}")
    preset, values = _biomedicine_request(case_id, request)
    spec = BIOMEDICINE_SCENARIO_SPECS[case_id]
    if spec.implementation_status != "available":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "BIOMEDICINE_EXECUTOR_NOT_IMPLEMENTED",
                "message": "该场景当前只开放结构预览，量子执行链尚未接入。",
                "stage": "preflight",
            },
        )
    if case_id == "docking_match":
        if request.mode == "analog":
            raise HTTPException(
                status_code=422,
                detail=(
                    "构象匹配的覆盖与构象约束需要 Digital residual，"
                    "不支持纯 Analog。"
                ),
            )
        if request.algorithm not in {None, "recommended", "qaoa"}:
            raise HTTPException(status_code=422, detail="构象匹配只支持 QAOA。")
        profile = spec.recommended_execution
        shots = request.shots if request.shots is not None else int(profile["shots"])
        seed = request.seed if request.seed is not None else int(profile["seed"])
        layers = (
            request.layers if request.layers is not None else int(profile["layers"])
        )
        strategy = request.search_strategy or str(profile["searchStrategy"])
        budget = (
            request.parameter_budget
            if request.parameter_budget is not None
            else int(profile["parameterBudget"])
        )
        starts = (
            request.optimizer_starts
            if request.optimizer_starts is not None
            else int(profile["optimizerStarts"])
        )
        try:
            run = await run_in_threadpool(
                run_docking_match,
                preset=preset,
                values=values,
                mode=request.mode,
                shots=shots,
                seed=seed,
                layers=layers,
                search_strategy=strategy,
                parameter_budget=budget,
                optimizer_starts=starts,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        scenario = spec.to_dict()
        scenario["values"] = values
        return {"scenario": scenario, "preset": preset, "run": run}
    if request.mode not in {"recommended", "digital"}:
        raise HTTPException(
            status_code=422,
            detail="电子结构场景只支持 Digital VQE。",
        )
    if request.algorithm not in {None, "recommended", "vqe"}:
        raise HTTPException(
            status_code=422,
            detail="电子结构场景只支持 VQE。",
        )
    profile = spec.recommended_execution
    shots = request.shots if request.shots is not None else int(profile["shots"])
    seed = request.seed if request.seed is not None else int(profile["seed"])
    layers = request.layers if request.layers is not None else int(profile["layers"])
    budget = (
        request.parameter_budget
        if request.parameter_budget is not None
        else int(profile["parameterBudget"])
    )
    starts = (
        request.optimizer_starts
        if request.optimizer_starts is not None
        else int(profile["optimizerStarts"])
    )
    try:
        run = await run_in_threadpool(
            run_electronic_structure,
            shots=shots,
            seed=seed,
            layers=layers,
            parameter_budget=budget,
            optimizer_starts=starts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    scenario = spec.to_dict()
    scenario["values"] = values
    return {"scenario": scenario, "preset": preset, "run": run}


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
    spec = SCENARIO_SPECS[case_id]
    requested_algorithm = request.algorithm or spec.recommended_execution.algorithm
    profile = spec.execution_for(requested_algorithm)
    shots = request.shots if request.shots is not None else profile.shots
    seed = request.seed if request.seed is not None else profile.seed
    layers = request.layers if request.layers is not None else profile.layers
    algorithm = request.algorithm or profile.algorithm
    layer_policy = request.layer_policy or profile.layer_policy
    max_layers = (
        request.max_layers if request.max_layers is not None else profile.max_layers
    )
    min_improvement = (
        request.min_improvement
        if request.min_improvement is not None
        else profile.min_improvement
    )
    search_strategy = request.search_strategy or profile.search_strategy
    if request.parameter_budget is not None:
        parameter_budget = request.parameter_budget
    elif search_strategy == profile.search_strategy:
        parameter_budget = profile.parameter_budget
    elif search_strategy == "continuous":
        # 连续搜索至少需要四次目标评估。调用方只覆盖搜索方式时，补成最小
        # 合法预算；显式给出的过小预算仍由执行器拒绝，不能静默改写。
        parameter_budget = max(profile.parameter_budget, 4)
    elif search_strategy == "preset":
        # 预设策略当前只有两个已验收点，不能沿用连续优化的较大预算并在
        # metadata 中声称执行了更多评估。
        parameter_budget = min(profile.parameter_budget, 2)
    else:
        parameter_budget = profile.parameter_budget
    if request.optimizer_starts is not None:
        optimizer_starts = request.optimizer_starts
    elif search_strategy == "continuous":
        optimizer_starts = profile.optimizer_starts
    else:
        # 多起点只属于连续优化器。调用方切换到离散搜索时，不能继续继承场景
        # 推荐连续配置中的起点数，否则一组单独看都合法的覆盖参数会组合成 422。
        optimizer_starts = 1
    repeats = request.repeats if request.repeats is not None else profile.repeats
    executor = ScenarioExecutor()
    scenario = _scenario(case_id)
    try:
        preflight = executor.analyze(scenario, case_input)
        selected_mode = (
            preflight.mode_decision.recommended_mode
            if request.mode == "recommended"
            else request.mode
        )
        run_options = {
            "mode": selected_mode,
            "algorithm": algorithm,
            "layer_policy": layer_policy,
            "layers": layers,
            "max_layers": max_layers,
            "min_improvement": min_improvement,
            "search_strategy": search_strategy,
            "parameter_budget": parameter_budget,
            "optimizer_starts": optimizer_starts,
            "shots": shots,
            "seed": seed,
            "report_path": REPORT_DIR / f"{case_id}-{selected_mode}.html",
        }
        repeated = None
        if repeats == 1:
            result = await run_in_threadpool(
                executor.run,
                scenario,
                case_input,
                **run_options,
            )
        else:
            repeated = await run_in_threadpool(
                executor.run_repeated,
                scenario,
                case_input,
                repeats=repeats,
                **run_options,
            )
            result = repeated.representative
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
        "run": (
            execution_payload(case_id, case_input, result)
            if repeated is None
            else execution_payload(
                case_id,
                case_input,
                result,
                repeated=repeated,
            )
        ),
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
