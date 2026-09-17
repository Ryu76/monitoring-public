import json
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import psutil

from config import settings
from .base import BaseCollector


class SystemResourceCollector(BaseCollector):
    """Collect common system resource metrics with psutil."""

    def collect(self) -> List[Dict[str, Any]]:
        now_str = datetime.now(timezone.utc).isoformat()
        metrics: List[Dict[str, Any]] = []

        # Total CPU
        cpu_usage = psutil.cpu_percent(interval=None)
        metrics.append(self._make_metric("CPU_USAGE_PCT", cpu_usage, now_str))

        # CPU Core
        per_cpu = psutil.cpu_percent(interval=None, percpu=True)
        for i, core_usage in enumerate(per_cpu):
            metrics.append(self._make_metric("CPU_CORE_PCT", core_usage, now_str, "core", str(i)))

        # Load average (not on Windows)
        if hasattr(psutil, "getloadavg"):
            try:
                load1, load5, load15 = psutil.getloadavg()
                metrics.append(self._make_metric("CPU_LOAD_1M", load1, now_str))
                metrics.append(self._make_metric("CPU_LOAD_5M", load5, now_str))
                metrics.append(self._make_metric("CPU_LOAD_15M", load15, now_str))
            except Exception:
                pass

        # Memory
        mem = psutil.virtual_memory()
        metrics.append(self._make_metric("MEM_USAGE_PCT", mem.percent, now_str))
        metrics.append(self._make_metric("MEM_AVAILABLE_BYTES", float(mem.available), now_str))

        # Swap
        try:
            swap = psutil.swap_memory()
            metrics.append(self._make_metric("SWAP_USAGE_PCT", swap.percent, now_str))
            metrics.append(self._make_metric("SWAP_AVAILABLE_BYTES", float(swap.free), now_str))
        except Exception:
            pass

        metrics.extend(self._collect_disks(now_str))
        metrics.extend(self._collect_network(now_str))
        metrics.extend(self._collect_top_processes(now_str))
        metrics.extend(self._collect_process_checks(now_str))
        metrics.extend(self._collect_ports(now_str))
        metrics.extend(self._collect_services(now_str))

        return metrics

    def _collect_process_checks(self, collected_at: str) -> List[Dict[str, Any]]:
        metrics: List[Dict[str, Any]] = []
        targets = self._parse_csv(settings.CHECK_PROCESSES)
        if not targets:
            return metrics

        running_names = set()
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name") or ""
                if name:
                    running_names.add(name.lower())
                    if name.lower().endswith(".exe"):
                        running_names.add(name[:-4].lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        for process_name in targets:
            key = process_name.lower()
            alt_key = key[:-4] if key.endswith(".exe") else f"{key}.exe"
            is_running = key in running_names or alt_key in running_names
            metrics.append(self._make_metric(
                "PROCESS_STATUS",
                1.0 if is_running else 0.0,
                collected_at,
                "process",
                process_name,
                "RUNNING" if is_running else "STOPPED",
                "OK" if is_running else "WARN",
            ))

        return metrics

    def _collect_disks(self, collected_at: str) -> List[Dict[str, Any]]:
        metrics: List[Dict[str, Any]] = []
        seen_mounts = set()

        try:
            for part in psutil.disk_partitions(all=False):
                mount = part.mountpoint
                if not mount or mount in seen_mounts:
                    continue
                seen_mounts.add(mount)

                try:
                    disk = psutil.disk_usage(mount)
                except (PermissionError, OSError):
                    continue

                metrics.append(self._make_metric("DISK_USAGE_PCT", disk.percent, collected_at, "path", mount))
                metrics.append(self._make_metric("DISK_AVAILABLE_BYTES", float(disk.free), collected_at, "path", mount))
                
            io_counters = psutil.disk_io_counters(perdisk=True)
            if io_counters:
                for disk_name, io in io_counters.items():
                    metrics.append(self._make_metric("DISK_IO_READ_BYTES", float(io.read_bytes), collected_at, "disk", disk_name))
                    metrics.append(self._make_metric("DISK_IO_WRITE_BYTES", float(io.write_bytes), collected_at, "disk", disk_name))
                    metrics.append(self._make_metric("DISK_IO_READ_TIME", float(io.read_time), collected_at, "disk", disk_name))
                    metrics.append(self._make_metric("DISK_IO_WRITE_TIME", float(io.write_time), collected_at, "disk", disk_name))
        except Exception:
            pass

        return metrics

    def _collect_network(self, collected_at: str) -> List[Dict[str, Any]]:
        metrics: List[Dict[str, Any]] = []
        try:
            # Total
            net = psutil.net_io_counters()
            metrics.append(self._make_metric("NET_BYTES_SENT", float(net.bytes_sent), collected_at))
            metrics.append(self._make_metric("NET_BYTES_RECV", float(net.bytes_recv), collected_at))

            # Per interface
            net_if = psutil.net_io_counters(pernic=True)
            for nic, io in net_if.items():
                metrics.append(self._make_metric("NET_BYTES_SENT_RATE", float(io.bytes_sent), collected_at, "interface", nic))
                metrics.append(self._make_metric("NET_BYTES_RECV_RATE", float(io.bytes_recv), collected_at, "interface", nic))
        except Exception:
            pass
        return metrics

    def _collect_top_processes(self, collected_at: str) -> List[Dict[str, Any]]:
        metrics: List[Dict[str, Any]] = []
        process_rows = []

        try:
            primed = []
            for proc in psutil.process_iter(["pid", "name", "username"]):
                try:
                    proc.cpu_percent(interval=None)
                    primed.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            time.sleep(0.1)

            for proc in primed:
                try:
                    info = proc.as_dict(attrs=["pid", "name", "username", "memory_percent"])
                    process_rows.append({
                        "pid": info.get("pid"),
                        "name": info.get("name") or "unknown",
                        "username": info.get("username"),
                        "cpu_percent": float(proc.cpu_percent(interval=None) or 0),
                        "memory_percent": float(info.get("memory_percent") or 0),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            top_n = max(1, settings.PROCESS_TOP_N)
            for proc in sorted(process_rows, key=lambda p: p["cpu_percent"], reverse=True)[:top_n]:
                label = f'{proc["pid"]}:{proc["name"]}'
                metrics.append(self._make_metric(
                    "PROCESS_CPU_PCT",
                    proc["cpu_percent"],
                    collected_at,
                    "process",
                    label,
                    json.dumps(proc, ensure_ascii=False),
                ))

            for proc in sorted(process_rows, key=lambda p: p["memory_percent"], reverse=True)[:top_n]:
                label = f'{proc["pid"]}:{proc["name"]}'
                metrics.append(self._make_metric(
                    "PROCESS_MEM_PCT",
                    proc["memory_percent"],
                    collected_at,
                    "process",
                    label,
                    json.dumps(proc, ensure_ascii=False),
                ))
        except Exception:
            pass

        return metrics

    def _collect_ports(self, collected_at: str) -> List[Dict[str, Any]]:
        metrics: List[Dict[str, Any]] = []

        for port in self._parse_ports(settings.CHECK_PORTS):
            is_open = self._is_port_open("127.0.0.1", port)
            metrics.append(self._make_metric(
                "PORT_LISTEN",
                1.0 if is_open else 0.0,
                collected_at,
                "port",
                str(port),
                "LISTENING" if is_open else "CLOSED",
                "OK" if is_open else "WARN",
            ))

        return metrics

    def _collect_services(self, collected_at: str) -> List[Dict[str, Any]]:
        metrics: List[Dict[str, Any]] = []

        for service_name in self._parse_csv(settings.CHECK_SERVICES):
            is_running, service_state = self._service_status(service_name)
            metrics.append(self._make_metric(
                "SERVICE_STATUS",
                1.0 if is_running else 0.0,
                collected_at,
                "service",
                service_name,
                service_state,
                "OK" if is_running else "WARN",
            ))

        return metrics

    def _make_metric(
        self,
        code: str,
        val: float,
        collected_at: str,
        dim_key: str = "-",
        dim_val: str = "-",
        string_value: str | None = None,
        status_code: str = "OK",
    ) -> Dict[str, Any]:
        return {
            "metric_code": code,
            "dimension_key": dim_key,
            "dimension_value": dim_val,
            "metric_value": val,
            "string_value": string_value,
            "status_code": status_code,
            "quality_code": "GOOD",
            "collected_at": collected_at,
        }

    def _parse_csv(self, raw: str) -> List[str]:
        return [item.strip() for item in (raw or "").split(",") if item.strip()]

    def _parse_ports(self, raw: str) -> List[int]:
        ports: List[int] = []
        for item in self._parse_csv(raw):
            try:
                port = int(item)
            except ValueError:
                continue
            if 1 <= port <= 65535:
                ports.append(port)
        return ports

    def _is_port_open(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            return False

    def _service_status(self, service_name: str) -> tuple[bool, str]:
        try:
            if psutil.WINDOWS:
                service = psutil.win_service_get(service_name)
                state = service.status()
                return state.lower() == "running", state

            result = subprocess.run(
                ["systemctl", "is-active", service_name],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            state = (result.stdout or result.stderr or "unknown").strip()
            return state == "active", state
        except Exception as exc:
            return False, f"UNKNOWN: {exc}"
