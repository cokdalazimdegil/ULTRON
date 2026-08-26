"""
ULTRON Model Context Protocol (MCP) Standard Client Engine
══════════════════════════════════════════════════════════
• Anthropic / OpenAI Model Context Protocol (MCP) Standart İstemcisi
• JSON-RPC 2.0 Protokolü ve Stdio / In-Memory Transport Desteği
• Dinamik Araç Keşfi (tools/list) ve Yürütme (tools/call)
• Gemini / ULTRON Tool Declaration Otomatik Dönüştürücü (Schema Adapter)
• Tak-Çalıştır Harici Sunucu Yönetimi (Docker, GitHub, Postgres, SQLite, Slack, vb.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("ultron.core.mcp_client")


@dataclass
class MCPToolDefinition:
    """Tek bir MCP aracının tanımı ve JSON şeması."""
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str

    def to_gemini_declaration(self) -> dict[str, Any]:
        """Gemini tool declaration formatına dönüştürür."""
        schema_props = self.input_schema.get("properties", {})
        gemini_props = {}
        for prop_name, prop_val in schema_props.items():
            t_str = str(prop_val.get("type", "STRING")).upper()
            if t_str not in ("STRING", "NUMBER", "INTEGER", "BOOLEAN", "ARRAY", "OBJECT"):
                t_str = "STRING"
            gemini_props[prop_name] = {
                "type": t_str,
                "description": prop_val.get("description", "")
            }

        return {
            "name": f"mcp__{self.server_name}__{self.name}",
            "description": f"[{self.server_name.upper()} MCP TOOL] {self.description}",
            "parameters": {
                "type": "OBJECT",
                "properties": gemini_props,
                "required": self.input_schema.get("required", [])
            }
        }


class MCPServerConnection:
    """Tek bir MCP sunucusuna stdio üzerinden bağlı oturum."""

    def __init__(self, server_name: str, command: str, args: list[str] | None = None, env: dict[str, str] | None = None):
        self.server_name = server_name
        self.command = command
        self.args = args or []
        self.env = env or {}
        
        self._proc: Optional[subprocess.Popen] = None
        self._req_id = 0
        self._lock = threading.RLock()
        self._tools: list[MCPToolDefinition] = []
        self._connected = False
        self._server_info: dict[str, Any] = {}

    @property
    def is_connected(self) -> bool:
        if not self._connected:
            return False
        if self._proc is not None:
            return self._proc.poll() is None
        return True


    def connect(self, timeout_sec: float = 8.0) -> bool:
        """Sunucu sürecini başlatır ve MCP el sıkışmasını (handshake) gerçekleştirir."""
        with self._lock:
            if self.is_connected:
                return True

            full_env = os.environ.copy()
            full_env.update(self.env)
            full_cmd = [self.command] + self.args

            try:
                self._proc = subprocess.Popen(
                    full_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    env=full_env
                )
            except Exception as e:
                logger.error(f"[MCP:{self.server_name}] Süreç başlatılamadı: {e}")
                return False

            # 1. Initialize İsteği Gönder
            init_req = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "ULTRON-MCP-Client", "version": "17.0"}
                }
            }
            res = self._send_request_sync(init_req, timeout=timeout_sec)
            if not res or "result" not in res:
                logger.warning(f"[MCP:{self.server_name}] Initialize başarısız: {res}")
                self.disconnect()
                return False

            self._server_info = res["result"].get("serverInfo", {})

            # 2. Initialized Bildirimi Gönder
            notify = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            self._send_notification(notify)

            # 3. Araçları Listele
            self.refresh_tools()
            self._connected = True
            logger.info(f"[MCP:{self.server_name}] Başarıyla bağlandı. Keşfedilen araç sayısı: {len(self._tools)}")
            return True

    def disconnect(self) -> None:
        """Sunucu bağlantısını kapatır."""
        with self._lock:
            self._connected = False
            if self._proc:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=1.0)
                except Exception:
                    try:
                        self._proc.kill()
                    except Exception:
                        pass
                self._proc = None
            self._tools.clear()

    def refresh_tools(self) -> list[MCPToolDefinition]:
        """Sunucudaki mevcut araçları listeler (tools/list)."""
        with self._lock:
            req = {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list", "params": {}}
            res = self._send_request_sync(req, timeout=5.0)
            self._tools = []
            if res and "result" in res:
                tool_list = res["result"].get("tools", [])
                for t in tool_list:
                    self._tools.append(MCPToolDefinition(
                        name=t.get("name", ""),
                        description=t.get("description", ""),
                        input_schema=t.get("inputSchema", {}),
                        server_name=self.server_name
                    ))
            return self._tools

    def call_tool(self, tool_name: str, arguments: dict[str, Any], timeout: float = 30.0) -> dict[str, Any]:
        """Sunucudaki bir aracı çalıştırır (tools/call)."""
        with self._lock:
            if not self.is_connected:
                return {"isError": True, "content": [{"type": "text", "text": "MCP Sunucusu bağlı değil."}]}

            req = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            res = self._send_request_sync(req, timeout=timeout)
            if not res:
                return {"isError": True, "content": [{"type": "text", "text": "MCP isteği zaman aşımına uğradı."}]}
            if "error" in res:
                return {"isError": True, "content": [{"type": "text", "text": str(res["error"])}]}
            return res.get("result", {"content": []})

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _send_notification(self, payload: dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin:
            return
        try:
            line = json.dumps(payload) + "\n"
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
        except Exception as e:
            logger.debug(f"[MCP:{self.server_name}] Bildirim gönderme hatası: {e}")

    def _send_request_sync(self, req: dict[str, Any], timeout: float = 8.0) -> Optional[dict[str, Any]]:
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            return None

        try:
            line = json.dumps(req) + "\n"
            self._proc.stdin.write(line)
            self._proc.stdin.flush()

            # Yanıtı oku (tek satır JSON-RPC)
            start_t = time.time()
            while time.time() - start_t < timeout:
                resp_line = self._proc.stdout.readline()
                if not resp_line:
                    time.sleep(0.05)
                    continue
                resp_line = resp_line.strip()
                if not resp_line:
                    continue
                try:
                    data = json.loads(resp_line)
                    if data.get("id") == req.get("id"):
                        return data
                except Exception:
                    continue

            return None
        except Exception as e:
            logger.error(f"[MCP:{self.server_name}] Request hatası: {e}")
            return None


class MCPClientManager:
    """
    Tüm kayıtlı harici MCP sunucularını yöneten ana orkestratör.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "mcp_servers.json")
        self._connections: dict[str, MCPServerConnection] = {}
        self._lock = threading.RLock()
        self._load_config()

    def _load_config(self) -> None:
        """mcp_servers.json yapılandırma dosyasını yükler."""
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            servers = data.get("mcpServers", {})
            for name, cfg in servers.items():
                self.register_server(
                    name=name,
                    command=cfg.get("command", ""),
                    args=cfg.get("args", []),
                    env=cfg.get("env", {})
                )
        except Exception as e:
            logger.warning(f"[MCP Manager] Yapılandırma dosyası okunamadı: {e}")

    def register_server(self, name: str, command: str, args: list[str] | None = None, env: dict[str, str] | None = None) -> MCPServerConnection:
        """Yeni bir MCP sunucusu kaydeder."""
        with self._lock:
            conn = MCPServerConnection(server_name=name, command=command, args=args, env=env)
            self._connections[name] = conn
            return conn

    def unregister_server(self, name: str) -> bool:
        """Bir sunucunun kaydını siler ve bağlantısını keser."""
        with self._lock:
            conn = self._connections.pop(name, None)
            if conn:
                conn.disconnect()
                return True
            return False

    def connect_all(self) -> dict[str, bool]:
        """Tüm kayıtlı MCP sunucularına bağlanır."""
        results = {}
        with self._lock:
            for name, conn in self._connections.items():
                results[name] = conn.connect()
        return results

    def disconnect_all(self) -> None:
        """Tüm sunucu bağlantılarını kapatır."""
        with self._lock:
            for conn in self._connections.values():
                conn.disconnect()

    def discover_all_tools(self) -> list[MCPToolDefinition]:
        """Tüm bağlı MCP sunucularındaki araçları toplar."""
        all_tools: list[MCPToolDefinition] = []
        with self._lock:
            for conn in self._connections.values():
                if conn.is_connected:
                    all_tools.extend(conn._tools)
        return all_tools

    def to_gemini_tool_declarations(self) -> list[dict[str, Any]]:
        """Tüm bağlı MCP araçlarını Gemini Tool formatına dönüştürür."""
        tools = self.discover_all_tools()
        return [t.to_gemini_declaration() for t in tools]

    def execute_tool(self, namespaced_tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        'mcp__<server_name>__<tool_name>' formatındaki bir araç çağrısını ilgili sunucuya yönlendirir.
        """
        parts = namespaced_tool_name.split("__")
        if len(parts) >= 3 and parts[0] == "mcp":
            server_name = parts[1]
            real_tool_name = "__".join(parts[2:])
        else:
            server_name = ""
            real_tool_name = namespaced_tool_name

        with self._lock:
            conn = self._connections.get(server_name)
            if not conn:
                return {
                    "success": False,
                    "error": f"MCP Sunucusu bulunamadı: '{server_name}'",
                    "result": None
                }
            
            raw_res = conn.call_tool(real_tool_name, arguments)
            is_err = raw_res.get("isError", False)
            content_items = raw_res.get("content", [])
            text_out = "\n".join(item.get("text", "") for item in content_items if isinstance(item, dict))

            return {
                "success": not is_err,
                "error": text_out if is_err else None,
                "result": text_out if not is_err else None,
                "raw": raw_res
            }

    def get_status(self) -> dict[str, Any]:
        """Tüm sunucuların ve araçların durum özetini döner."""
        with self._lock:
            servers = {}
            total_tools = 0
            for name, conn in self._connections.items():
                t_count = len(conn._tools)
                total_tools += t_count
                servers[name] = {
                    "connected": conn.is_connected,
                    "command": conn.command,
                    "tools_count": t_count,
                    "server_info": conn._server_info
                }
            return {
                "active_servers": len([c for c in self._connections.values() if c.is_connected]),
                "total_servers": len(self._connections),
                "total_mcp_tools": total_tools,
                "servers": servers
            }


# Canonical Global Singleton Instance
mcp_client_manager = MCPClientManager()
