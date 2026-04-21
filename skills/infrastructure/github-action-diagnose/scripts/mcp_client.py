#!/usr/bin/env python3
"""
mcp_client.py - MCP 客户端，用于查询 LTS 集群日志

用法:
  from mcp_client import MCPClient
  client = MCPClient()
  pods = client.list_pods("vllm-project", "2026-03-27 21:00:00", "2026-03-27 22:00:00")
  export_id = client.export_logs("vllm-project", "runner-pod-name", "Error|Failed", ...)
  status = client.get_export_status(export_id)
"""

import json
import gzip
import time
import requests
from typing import Optional


class MCPClient:
    """MCP 客户端，封装 LTS 日志查询操作"""

    DEFAULT_URL = "http://150.158.143.223:30089/mcp"
    DEFAULT_SOURCE = "ascend-ci-log"

    def __init__(self, url: str = None):
        self.url = url or self.DEFAULT_URL
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
        )
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ci-diagnose", "version": "1.0"},
            },
        }
        r = self.session.post(self.url, json=init_req, timeout=10)
        session_id = r.headers.get("mcp-session-id", "")
        if session_id:
            self.session.headers["Mcp-Session-Id"] = session_id
        self._initialized = True

    def _call_tool(self, tool_name: str, args: dict, timeout: int = 30) -> dict:
        self._ensure_initialized()
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": args},
        }
        r = self.session.post(self.url, json=req, timeout=timeout)
        for line in r.text.split("\r\n"):
            if line.startswith("data:"):
                data = json.loads(line[5:])
                if data.get("isError"):
                    error_msg = data.get("content", [{}])[0].get(
                        "text", "Unknown error"
                    )
                    return {"error": error_msg}
                return data.get("result", {})
        return {"error": "No response from MCP server"}

    def list_sources(self) -> dict:
        return self._call_tool("lts_list_sources", {})

    def list_namespaces(
        self, source: str = None, start: str = None, end: str = None
    ) -> dict:
        args = {"source": source or self.DEFAULT_SOURCE}
        if start and end:
            args["time"] = {"start": start, "end": end}
        return self._call_tool("lts_list_namespaces", args)

    def list_pods(
        self, namespace: str, start: str = None, end: str = None, source: str = None
    ) -> dict:
        args = {"source": source or self.DEFAULT_SOURCE, "namespace": namespace}
        if start and end:
            args["time"] = {"start": start, "end": end}
        return self._call_tool("lts_list_pods", args, timeout=60)

    def export_logs(
        self,
        namespace: str,
        pod_name: str = "",
        keywords: str = "",
        start: str = None,
        end: str = None,
        source: str = None,
    ) -> dict:
        args = {
            "source": source or self.DEFAULT_SOURCE,
            "namespace": namespace,
            "pod_name": pod_name,
            "keywords": keywords,
        }
        if start and end:
            args["time"] = {"start": start, "end": end}
        return self._call_tool("lts_export_logs", args, timeout=60)

    def get_export_status(self, export_id: str) -> dict:
        return self._call_tool("lts_get_export_status", {"export_id": export_id})

    def download_export(self, export_result: dict) -> bytes:
        # 尝试多种路径获取 download_url
        download_url = ""
        # 路径 1: structuredContent.result.result.download_url
        download_url = (
            export_result.get("structuredContent", {})
            .get("result", {})
            .get("result", {})
            .get("download_url", "")
        )
        # 路径 2: result.result.download_url
        if not download_url:
            download_url = (
                export_result.get("result", {})
                .get("result", {})
                .get("download_url", "")
            )
        # 路径 3: 从 content[0].text 解析
        if not download_url:
            content = export_result.get("content", [{}])[0].get("text", "{}")
            try:
                parsed = json.loads(content)
                download_url = parsed.get("result", {}).get("download_url", "")
            except json.JSONDecodeError:
                pass
        if not download_url:
            raise ValueError(
                f"No download URL in export result: {str(export_result)[:200]}"
            )
        r = requests.get(download_url, timeout=60)
        r.raise_for_status()
        return r.content

    def find_runner_pod(
        self,
        runner_name: str,
        namespace: str = "vllm-project",
        start: str = None,
        end: str = None,
    ) -> Optional[str]:
        result = self.list_pods(namespace, start, end)
        if "error" in result:
            return None
        # 解析 structuredContent.result.pods
        pods = result.get("structuredContent", {}).get("result", {}).get("pods", [])
        if not pods:
            # 回退：从 content 字段解析
            content = result.get("content", [{}])[0].get("text", "{}")
            try:
                parsed = json.loads(content)
                pods = parsed.get("pods", [])
            except json.JSONDecodeError:
                pass
        for pod in pods:
            if runner_name in pod:
                return pod
        return None

    def get_runner_logs(
        self,
        runner_name: str,
        namespace: str = "vllm-project",
        start: str = None,
        end: str = None,
        keywords: str = None,
    ) -> Optional[str]:
        # 方案 B：默认 keywords 过滤，避免返回全量日志
        if keywords is None or keywords == "":
            keywords = "Error|Failed|Exception|exit code|Timeout|OOM|Killed|panic|fatal|WARNING"
        pod_name = self.find_runner_pod(runner_name, namespace, start, end)
        if not pod_name:
            return f"未找到匹配的 Pod (runner: {runner_name}, namespace: {namespace})"

        export_result = self.export_logs(namespace, pod_name, keywords, start, end)
        if "error" in export_result:
            return f"导出失败: {export_result['error']}"

        # 提取 export_id（可能在顶层或 structuredContent.result 中）
        export_id = export_result.get("export_id", "")
        if not export_id:
            export_id = (
                export_result.get("structuredContent", {})
                .get("result", {})
                .get("export_id", "")
            )
        if not export_id:
            # 回退：从 content 解析
            content = export_result.get("content", [{}])[0].get("text", "{}")
            try:
                export_id = json.loads(content).get("export_id", "")
            except json.JSONDecodeError:
                pass
        if not export_id:
            return "未返回 export_id"

        for _ in range(30):
            time.sleep(3)
            status = self.get_export_status(export_id)
            phase = status.get("progress", {}).get("phase", "")
            if phase == "completed":
                break
            if phase == "failed":
                return f"导出任务失败: {status.get('error', '')}"

        try:
            raw_data = self.download_export(status)
            data = gzip.decompress(raw_data)
            lines = data.decode("utf-8", errors="replace").strip().split("\n")
            log_lines = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    content = entry.get("content", "")
                    if content:
                        log_lines.append(content)
                except json.JSONDecodeError:
                    continue
            result = "\n".join(log_lines)
            if len(result) > 50000:
                return (
                    result[:50000] + f"\n... (内容过长，已截断，共 {len(log_lines)} 行)"
                )
            return result
        except Exception as e:
            return f"下载/解析失败: {e}"
