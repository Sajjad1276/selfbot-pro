from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import Any, Awaitable, Callable

import aiohttp

from google import genai
from google.genai import types


MAX_TOOL_ROUNDS = 24
GITHUB_API = "https://api.github.com"
BLOCKED_PATH_PATTERNS = (
    ".env",
    ".session",
    ".sqlite",
    ".db",
    "secret",
    "credential",
    "token",
)
SECRET_PATTERNS = (
    r"ghp_[A-Za-z0-9_\-]{20,}",
    r"github_pat_[A-Za-z0-9_\-]{20,}",
    r"AIza[0-9A-Za-z_\-]{20,}",
    r"sk-[A-Za-z0-9_\-]{20,}",
    r"\b\d{8,12}:[A-Za-z0-9_-]{20,}\b",
)


class DeveloperAgent:
    """Owner-only Gemini coding agent for SelfBot Pro."""

    def __init__(
        self,
        api_key: str,
        model: str,
        github_token: str,
        repository: str = "Sajjad1276/selfbot-pro",
        branch: str = "main",
        railway_health_url: str | None = None,
        max_rounds: int = MAX_TOOL_ROUNDS,
    ) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY تنظیم نشده است.")
        if not github_token:
            raise ValueError("GITHUB_TOKEN تنظیم نشده است.")
        if "/" not in repository:
            raise ValueError("DEV_AGENT_REPOSITORY باید به شکل owner/repo باشد.")

        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.github_token = github_token
        self.repository = repository
        self.branch = branch
        self.railway_health_url = railway_health_url
        self.max_rounds = max(1, min(max_rounds, 50))
        self.logger = logging.getLogger("selfbot.dev_agent")

    async def execute(
        self,
        task: str,
        progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        if not task.strip():
            return "دستور Agent خالی است."

        system = (
            "تو Agent اجرایی و دستیار فنی شخصی مالک پروژه SelfBot Pro هستی.\\n"
            "اصل اول: وقتی مالک یک کار می‌خواهد، کار را واقعاً انجام بده. فقط توضیح، آموزش یا پیشنهاد نده مگر اینکه خودِ درخواست توضیح خواسته باشد.\\n"
            "هر درخواست را ابتدا به هدف عملی تبدیل کن، سپس خودت کد و معماری مرتبط را بررسی کن، علت را پیدا کن، تغییر لازم را اعمال کن و نتیجه را با ابزارها بررسی کن.\\n"
            "لازم نیست مالک برای هر مرحله به تو اجازه جداگانه بدهد. تصمیم‌های فنی لازم برای انجام کار را خودت بگیر. فقط وقتی یک ورودی حیاتی واقعاً وجود ندارد و بدون آن امکان اجرای کار نیست، صریح و کوتاه همان مورد را مطرح کن.\\n"
            "از ابزارهای GitHub برای خواندن و تغییر واقعی ریپو استفاده کن. تغییرات مرتبط را تا حد امکان در یک commit اتمیک انجام بده.\\n"
            "پس از هر تغییر، CI را بررسی کن. اگر شکست خورد، لاگ را بخوان، علت را پیدا کن، اصلاح کن و دوباره commit و بررسی کن.\\n"
            "پس از CI موفق، وضعیت Railway و health endpoint را بررسی کن. اگر deployment یا runtime مشکل دارد، تا حدی که ابزارهای موجود اجازه می‌دهند خودت علت را پیدا و اصلاح کن و دوباره تأیید بگیر.\\n"
            "برای کارهای چندمرحله‌ای خودت مراحل را مدیریت کن و کار را نیمه‌کاره رها نکن. اگر یک روش جواب نداد، از مسیر فنی دیگری که با ابزارهای موجود ممکن است استفاده کن.\\n"
            "اگر درخواست مربوط به بررسی، رفع باگ، قابلیت جدید، refactor، تست، CI، deployment، performance، database، API، handler یا هر بخش دیگری از همین پروژه است، مسئول اجرای کامل آن هستی.\\n"
            "در پاسخ با لحن انسانی، طبیعی، کوتاه و مستقیم حرف بزن. گزارش‌ها شبیه پیام یک مهندس واقعی باشند، نه متن رباتیک یا رسمیِ خشک. از جمله‌های تکراری مثل «امکانش نیست» یا «فقط می‌توانم راهنمایی کنم» استفاده نکن وقتی ابزار و دسترسی لازم برای انجام کار را داری.\\n"
            "قبل از اعلام موفقیت، حتماً مدرک فنی داشته باش. اگر کاری ناقص مانده یا ابزار محدودیتی ایجاد کرده، همان را دقیق و بدون وانمود کردن به موفقیت بگو.\\n"
            "secret، session، token، password و login code را نخوان، استخراج نکن و در پاسخ نمایش نده. از تغییرات غیرمرتبط و تخریبی خودداری کن.\\n"
            "هرگز صرفاً workaround پیشنهاد نده وقتی علت واقعی قابل اصلاح است. هدف، رفع واقعی مشکل و تحویل نتیجه قابل‌بررسی است.\\n"
            "در پایان، خیلی طبیعی بگو چه کار کردی، کدام commit ایجاد شد و نتیجه واقعی CI/Railway/health چه بود."
        )

        tools = self._tool_declarations()
        contents: list[Any] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"{system}\n\nدرخواست مالک:\n{task}")],
            )
        ]

        for round_number in range(self.max_rounds):
            await self._progress(progress, f"Agent: بررسی مرحله {round_number + 1}/{self.max_rounds}")
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(function_declarations=tools)],
                    max_output_tokens=1800,
                    temperature=0.1,
                ),
            )

            calls = self._extract_function_calls(response)
            if not calls:
                text = getattr(response, "text", None)
                return (text or "Agent پاسخ نهایی تولید نکرد.").strip()

            model_content = self._first_model_content(response)
            if model_content is not None:
                contents.append(model_content)

            for call in calls:
                await self._progress(progress, f"Agent: اجرای {call['name']}")
                result = await self._run_tool(call["name"], call.get("args") or {})
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(
                                name=call["name"],
                                response={"result": result},
                                id=call.get("id"),
                            )
                        ],
                    )
                )

        return "Agent به سقف مراحل رسید و بدون تأیید کامل متوقف شد. نتیجه را موفق اعلام نمی‌کنم."

    def _tool_declarations(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "repo_tree",
                "description": "لیست فایل‌های پروژه را برای شناخت معماری برمی‌گرداند.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prefix": {
                            "type": "string",
                            "description": "مسیر اختیاری مثل modules/ai",
                        }
                    },
                },
            },
            {
                "name": "read_file",
                "description": "محتوای یک فایل متنی امن از ریپو را می‌خواند.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "search_code",
                "description": "در کد ریپو برای عبارت یا الگوی مشخص جست‌وجو می‌کند.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "write_files",
                "description": "چند فایل را به صورت یک commit اتمیک روی branch اصلی می‌نویسد.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["path", "content"],
                            },
                        },
                    },
                    "required": ["message", "changes"],
                },
            },
            {
                "name": "ci_logs",
                "description": "متن لاگ job ناموفق GitHub Actions را برای پیدا کردن علت واقعی خطا برمی‌گرداند.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commit_sha": {"type": "string"},
                    },
                    "required": ["commit_sha"],
                },
            },
            {
                "name": "verify_ci_and_deploy",
                "description": "آخرین commit را در GitHub Actions و status مربوط به Railway بررسی و در صورت نیاز منتظر نتیجه می‌ماند.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commit_sha": {"type": "string"},
                        "wait_seconds": {"type": "integer"},
                    },
                    "required": ["commit_sha"],
                },
            },
            {
                "name": "verify_runtime",
                "description": "health endpoint عمومی SelfBot را بررسی می‌کند و باید status=ok و telegram=true باشد.",
                "parameters": {},
            },
        ]

    async def _run_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "repo_tree":
            return await self._repo_tree(str(args.get("prefix") or ""))
        if name == "read_file":
            return await self._read_file(str(args.get("path") or ""))
        if name == "search_code":
            return await self._search_code(str(args.get("query") or ""))
        if name == "write_files":
            return await self._write_files(
                str(args.get("message") or "chore: agent update"),
                args.get("changes") or [],
            )
        if name == "ci_logs":
            return await self._ci_logs(str(args.get("commit_sha") or ""))
        if name == "verify_ci_and_deploy":
            return await self._verify_ci_and_deploy(
                str(args.get("commit_sha") or ""),
                int(args.get("wait_seconds") or 120),
            )
        if name == "verify_runtime":
            return await self._verify_runtime()
        return {"ok": False, "error": f"ابزار ناشناخته: {name}"}

    async def _github_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{GITHUB_API}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.github_token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "SelfBot-Pro-Developer-Agent",
        }
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.request(method, url, params=params, json=payload) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    raise RuntimeError(
                        f"GitHub API {response.status}: "
                        f"{data.get('message', 'unknown error')}"
                    )
                return data

    async def _repo_tree(self, prefix: str) -> dict[str, Any]:
        path = prefix.strip("/")
        if path:
            data = await self._github_request(
                "GET",
                f"/repos/{self.repository}/contents/{path}",
                params={"ref": self.branch},
            )
        else:
            ref = await self._github_request(
                "GET",
                f"/repos/{self.repository}/git/ref/heads/{self.branch}",
            )
            tree_sha = ref["object"]["sha"]
            data = await self._github_request(
                "GET",
                f"/repos/{self.repository}/git/trees/{tree_sha}",
                params={"recursive": "1"},
            )
        if isinstance(data, dict) and "tree" in data:
            items = [
                {"path": x["path"], "type": x["type"]}
                for x in data.get("tree", [])
                if not self._blocked_path(x.get("path", ""))
            ]
            return {"ok": True, "items": items[:800]}
        if isinstance(data, list):
            items = [
                {"path": x["path"], "type": x["type"]}
                for x in data
                if not self._blocked_path(x.get("path", ""))
            ]
            return {"ok": True, "items": items[:300]}
        return {"ok": True, "items": []}

    async def _read_file(self, path: str) -> dict[str, Any]:
        if self._blocked_path(path):
            return {"ok": False, "error": "خواندن این مسیر برای Agent مجاز نیست."}
        data = await self._github_request(
            "GET",
            f"/repos/{self.repository}/contents/{path}",
            params={"ref": self.branch},
        )
        if data.get("type") != "file":
            return {"ok": False, "error": "مسیر یک فایل متنی نیست."}
        raw = base64.b64decode(data.get("content", "").replace("\n", ""))
        text = raw.decode("utf-8")
        if len(text) > 180_000:
            text = text[:180_000] + "\n[TRUNCATED]"
        return {"ok": True, "path": path, "sha": data.get("sha"), "content": text}

    async def _search_code(self, query: str) -> dict[str, Any]:
        if not query.strip():
            return {"ok": False, "error": "عبارت جست‌وجو خالی است."}
        data = await self._github_request(
            "GET",
            "/search/code",
            params={"q": f"{query} repo:{self.repository}", "per_page": "20"},
        )
        results = []
        for item in data.get("items", []):
            results.append(
                {
                    "path": item.get("path"),
                    "url": item.get("html_url"),
                    "sha": item.get("sha"),
                }
            )
        return {"ok": True, "results": results}

    async def _write_files(self, message: str, changes: list[Any]) -> dict[str, Any]:
        if not 1 <= len(changes) <= 12:
            return {"ok": False, "error": "تعداد تغییرات باید بین 1 تا 12 فایل باشد."}

        normalized: list[tuple[str, str]] = []
        for item in changes:
            if not isinstance(item, dict):
                return {"ok": False, "error": "ساختار change نامعتبر است."}
            path = str(item.get("path") or "").strip()
            content = str(item.get("content") or "")
            if not path:
                return {"ok": False, "error": "مسیر فایل خالی است."}
            if self._blocked_path(path):
                return {"ok": False, "error": f"نوشتن روی مسیر {path} مجاز نیست."}
            if len(content) > 220_000:
                return {"ok": False, "error": f"فایل {path} بیش از حد بزرگ است."}
            if self._looks_secret(content):
                return {"ok": False, "error": f"محتوای مشکوک به secret در {path} شناسایی شد."}
            normalized.append((path, content))

        ref = await self._github_request(
            "GET",
            f"/repos/{self.repository}/git/ref/heads/{self.branch}",
        )
        parent_sha = ref["object"]["sha"]
        parent_commit = await self._github_request(
            "GET",
            f"/repos/{self.repository}/git/commits/{parent_sha}",
        )
        base_tree = parent_commit["tree"]["sha"]

        tree_entries = []
        for path, content in normalized:
            blob = await self._github_request(
                "POST",
                f"/repos/{self.repository}/git/blobs",
                payload={
                    "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    "encoding": "base64",
                },
            )
            tree_entries.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob["sha"],
                }
            )

        tree = await self._github_request(
            "POST",
            f"/repos/{self.repository}/git/trees",
            payload={
                "base_tree": base_tree,
                "tree": tree_entries,
            },
        )
        commit = await self._github_request(
            "POST",
            f"/repos/{self.repository}/git/commits",
            payload={
                "message": message[:120],
                "tree": tree["sha"],
                "parents": [parent_sha],
            },
        )
        await self._github_request(
            "PATCH",
            f"/repos/{self.repository}/git/refs/heads/{self.branch}",
            payload={"sha": commit["sha"], "force": False},
        )
        return {
            "ok": True,
            "commit_sha": commit["sha"],
            "files": [path for path, _ in normalized],
        }

    async def _ci_logs(self, commit_sha: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            return {"ok": False, "error": "commit_sha نامعتبر است."}

        runs = await self._github_request(
            "GET",
            f"/repos/{self.repository}/actions/runs",
            params={"head_sha": commit_sha, "per_page": "10"},
        )
        runs_list = runs.get("workflow_runs", [])
        if not runs_list:
            return {"ok": False, "error": "برای این commit اجرای CI پیدا نشد."}

        failed_run = next(
            (
                run
                for run in runs_list
                if run.get("status") == "completed"
                and run.get("conclusion") != "success"
            ),
            None,
        )
        if not failed_run:
            return {"ok": True, "message": "اجرای ناموفق CI برای این commit پیدا نشد."}

        jobs = await self._github_request(
            "GET",
            f"/repos/{self.repository}/actions/runs/{failed_run['id']}/jobs",
            params={"per_page": "20"},
        )
        failed_jobs = [
            job for job in jobs.get("jobs", [])
            if job.get("conclusion") not in {None, "success"}
        ]
        if not failed_jobs:
            return {
                "ok": False,
                "error": "CI ناموفق است ولی job ناموفق قابل دسترسی نیست.",
            }

        collected = []
        timeout = aiohttp.ClientTimeout(total=40)
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.github_token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "SelfBot-Pro-Developer-Agent",
        }
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for job in failed_jobs[:3]:
                async with session.get(
                    f"{GITHUB_API}/repos/{self.repository}/actions/jobs/{job['id']}/logs"
                ) as response:
                    if response.status >= 400:
                        continue
                    log_text = await response.text()
                    if len(log_text) > 40_000:
                        log_text = log_text[-40_000:]
                    collected.append(
                        {
                            "job": job.get("name"),
                            "conclusion": job.get("conclusion"),
                            "logs": self._redact(log_text),
                        }
                    )

        return {
            "ok": bool(collected),
            "run_id": failed_run.get("id"),
            "run_name": failed_run.get("name"),
            "jobs": collected,
        }

    async def _verify_ci_and_deploy(
        self,
        commit_sha: str,
        wait_seconds: int = 120,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            return {"ok": False, "error": "commit_sha نامعتبر است."}

        deadline = asyncio.get_running_loop().time() + max(10, min(wait_seconds, 900))
        last: dict[str, Any] = {}

        while asyncio.get_running_loop().time() < deadline:
            runs = await self._github_request(
                "GET",
                f"/repos/{self.repository}/actions/runs",
                params={"head_sha": commit_sha, "per_page": "10"},
            )
            ci_runs = runs.get("workflow_runs", [])
            ci = ci_runs[0] if ci_runs else None

            status_data = await self._github_request(
                "GET",
                f"/repos/{self.repository}/commits/{commit_sha}/status",
            )
            statuses = status_data.get("statuses", [])
            railway = next(
                (
                    s for s in statuses
                    if s.get("context") == "selfbot-pro - selfbot-pro"
                ),
                None,
            )

            last = {
                "ok": True,
                "commit_sha": commit_sha,
                "ci": {
                    "status": ci.get("status") if ci else "missing",
                    "conclusion": ci.get("conclusion") if ci else None,
                },
                "railway": {
                    "state": railway.get("state") if railway else "missing",
                    "description": railway.get("description") if railway else None,
                },
            }

            ci_ok = bool(
                ci
                and ci.get("status") == "completed"
                and ci.get("conclusion") == "success"
            )
            railway_ok = bool(railway and railway.get("state") == "success")
            if ci_ok and railway_ok:
                return last | {"verified": True}

            ci_failed = bool(
                ci
                and ci.get("status") == "completed"
                and ci.get("conclusion") not in {None, "success"}
            )
            railway_failed = bool(
                railway and railway.get("state") in {"failure", "error"}
            )
            if ci_failed or railway_failed:
                return last | {"verified": False, "failure": True}

            await asyncio.sleep(5)

        return last | {"verified": False, "timeout": True}

    async def _verify_runtime(self) -> dict[str, Any]:
        if not self.railway_health_url:
            return {"ok": False, "error": "RAILWAY_HEALTH_URL تنظیم نشده است."}
        url = self.railway_health_url.rstrip("/") + "/health"
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url) as response:
                    data = await response.json(content_type=None)
                    return {
                        "ok": response.status == 200,
                        "http_status": response.status,
                        "health": data,
                        "verified": response.status == 200
                        and data.get("status") == "ok"
                        and data.get("telegram") is True,
                    }
            except Exception as exc:
                return {"ok": False, "verified": False, "error": str(exc)}

    @staticmethod
    def _blocked_path(path: str) -> bool:
        value = path.lower().replace("\\", "/")
        parts = value.split("/")
        return any(
            any(pattern in part for pattern in BLOCKED_PATH_PATTERNS)
            for part in parts
        )

    @staticmethod
    def _looks_secret(text: str) -> bool:
        return any(re.search(pattern, text) for pattern in SECRET_PATTERNS)

    @staticmethod
    def _redact(text: str) -> str:
        redacted = text
        for pattern in SECRET_PATTERNS:
            redacted = re.sub(pattern, "[REDACTED]", redacted)
        return redacted

    @staticmethod
    def _extract_function_calls(response: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                call = getattr(part, "function_call", None)
                if call is None:
                    continue
                calls.append(
                    {
                        "id": getattr(call, "id", None),
                        "name": getattr(call, "name", ""),
                        "args": dict(getattr(call, "args", {}) or {}),
                    }
                )
        return calls

    @staticmethod
    def _first_model_content(response: Any) -> Any | None:
        candidates = getattr(response, "candidates", []) or []
        if not candidates:
            return None
        return getattr(candidates[0], "content", None)

    @staticmethod
    async def _progress(
        callback: Callable[[str], Awaitable[None]] | None,
        text: str,
    ) -> None:
        if callback:
            try:
                await callback(text)
            except Exception:
                pass
