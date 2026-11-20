"""
Background telemetry collection engine for CPU, memory, process stats, and power estimation.
"""

from __future__ import annotations

import glob
import logging
import time

import psutil

from hardware.topology import CPUTopology
from process.registry import ManagedProcess
from telemetry.schemas import ProcessMetricSnapshot, SystemHealthSnapshot

logger = logging.getLogger("aidax.telemetry.collector")


def compute_jain_fairness(allocations: list[float]) -> float:
    """
    Compute Jain's fairness index:
    J(x_1, ..., x_n) = (sum x_i)^2 / (n * sum x_i^2)
    Returns 1.0 for completely fair allocation or empty list.
    """
    if not allocations:
        return 1.0
    positive_allocations = [max(0.0, float(x)) for x in allocations]
    total = sum(positive_allocations)
    if total == 0.0:
        return 1.0
    n = len(positive_allocations)
    sum_sq = sum(x * x for x in positive_allocations)
    if sum_sq == 0.0:
        return 1.0
    return float((total * total) / (n * sum_sq))


class TelemetryCollector:
    """Collects system-level hardware metrics, core utilization, and managed process telemetry."""

    def __init__(self, topology: CPUTopology, base_idle_power_w: float = 15.0) -> None:
        self.topology = topology
        self.base_idle_power_w = base_idle_power_w
        self._rapl_energy_files = glob.glob("/sys/class/powercap/intel-rapl*/energy_uj")
        self._rapl_max_files = glob.glob("/sys/class/powercap/intel-rapl*/max_energy_range_uj")
        self._last_rapl_time: float = time.time()
        self._last_rapl_uj: int | None = None
        self._rapl_available = self._probe_rapl()

    def _probe_rapl(self) -> bool:
        """Check if Linux RAPL powercap energy files exist and are readable."""
        if not self._rapl_energy_files or not self._rapl_max_files:
            return False
        try:
            with open(self._rapl_energy_files[0], encoding="utf-8") as f:
                val = int(f.read().strip())
                return val > 0
        except Exception:
            return False

    def sample_rapl_energy(self) -> tuple[float | None, str]:
        """
        Sample delta energy in Joules using hardware RAPL counters.
        Handles counter wraparound via max_energy_range_uj.
        Returns (measured_joules, energy_mode).
        """
        if not self._rapl_available:
            return None, "ESTIMATED"

        now = time.time()
        dt = now - self._last_rapl_time
        if dt <= 0:
            return None, "ESTIMATED"

        try:
            total_uj = 0
            max_uj = 0
            for ef, mf in zip(self._rapl_energy_files, self._rapl_max_files, strict=False):
                with open(ef, encoding="utf-8") as f:
                    total_uj += int(f.read().strip())
                with open(mf, encoding="utf-8") as f:
                    max_uj += int(f.read().strip())

            if self._last_rapl_uj is not None:
                if total_uj >= self._last_rapl_uj:
                    delta_uj = total_uj - self._last_rapl_uj
                else:
                    delta_uj = (max_uj - self._last_rapl_uj) + total_uj
                delta_joules = delta_uj / 1e6
            else:
                delta_joules = 0.0

            self._last_rapl_uj = total_uj
            self._last_rapl_time = now
            return delta_joules, "MEASURED_RAPL"
        except Exception as e:
            logger.debug("RAPL read failed: %s; falling back to ESTIMATED", e)
            return None, "ESTIMATED"

    def sample_system_health(self, active_managed_count: int = 0) -> SystemHealthSnapshot:
        """Sample hardware utilization across P-cores and E-cores."""
        # Non-blocking per-CPU utilization
        per_cpu = psutil.cpu_percent(interval=None, percpu=True)
        total_cpu = float(psutil.cpu_percent(interval=None))
        mem = psutil.virtual_memory().percent

        p_utils: list[float] = []
        e_utils: list[float] = []

        for idx, util in enumerate(per_cpu):
            if idx in self.topology.p_cores:
                p_utils.append(float(util))
            elif idx in self.topology.e_cores:
                e_utils.append(float(util))
            else:
                p_utils.append(float(util))

        avg_p = float(sum(p_utils) / len(p_utils)) if p_utils else 0.0
        avg_e = float(sum(e_utils) / len(e_utils)) if e_utils else 0.0
        fairness = compute_jain_fairness(per_cpu)

        # RAPL Energy check
        measured_joules, energy_mode = self.sample_rapl_energy()
        if energy_mode == "MEASURED_RAPL" and measured_joules is not None:
            now = time.time()
            dt = max(0.001, now - self._last_rapl_time)
            power_watts = round(measured_joules / dt, 2)
        else:
            # Estimated power proxy: baseline idle + active core power components
            p_active_w = sum(u / 100.0 * 2.5 for u in p_utils)
            e_active_w = sum(u / 100.0 * 0.8 for u in e_utils)
            power_watts = round(self.base_idle_power_w + p_active_w + e_active_w, 2)

        return SystemHealthSnapshot(
            timestamp=time.time(),
            total_cpu_percent=total_cpu,
            memory_percent=mem,
            per_cpu_percent=[float(u) for u in per_cpu],
            p_core_utilization=round(avg_p, 2),
            e_core_utilization=round(avg_e, 2),
            jain_fairness_index=round(fairness, 4),
            estimated_power_watts=power_watts,
            energy_mode=energy_mode,
            measured_energy_joules=measured_joules,
            active_processes_count=active_managed_count,
        )

    def sample_managed_process(self, managed: ManagedProcess) -> ProcessMetricSnapshot | None:
        """Collect metrics for a managed process with exception guards for recycled or exited PIDs."""
        try:
            p = psutil.Process(managed.pid)
            if not p.is_running() or abs(p.create_time() - managed.create_time) > 0.5:
                return None

            with p.oneshot():
                proc_name = p.name()
                cpu_pct = float(p.cpu_percent(interval=None))
                mem_mb = float(p.memory_info().rss / (1024.0 * 1024.0))
                threads = p.num_threads()
                try:
                    ctx = p.num_ctx_switches()
                    vol_ctx = ctx.voluntary
                    invol_ctx = ctx.involuntary
                except Exception:
                    vol_ctx = 0
                    invol_ctx = 0
                try:
                    affinity = p.cpu_affinity()
                except Exception:
                    affinity = []

            # Determine core type
            core_type = "UNKNOWN"
            if affinity:
                if all(c in self.topology.p_cores for c in affinity):
                    core_type = "PERFORMANCE"
                elif all(c in self.topology.e_cores for c in affinity):
                    core_type = "EFFICIENCY"
                else:
                    core_type = "HYBRID"

            return ProcessMetricSnapshot(
                pid=managed.pid,
                name=proc_name,
                cpu_percent=round(cpu_pct, 2),
                memory_mb=round(mem_mb, 2),
                num_threads=threads,
                core_affinity=affinity,
                core_type=core_type,
                workload_type=managed.workload_type,
                voluntary_ctx_switches=vol_ctx,
                involuntary_ctx_switches=invol_ctx,
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
