"""
Eksekutor Gatling NYATA via scala-cli.

Modul ini menggantikan simulasi lama (requests + random) dengan eksekusi Gatling
sungguhan: tulis script Scala -> jalankan scala-cli -> baca stats.json asli.
Dipakai oleh gatling_tools.trigger_gatling_test_tool dan (nanti) oleh worker.

Semua path & perintah dibaca dari environment agar tidak hardcode ke satu mesin.
"""
import os
import re
import json
import time
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any


# --- Konfigurasi lokasi (bisa di-override via .env) ---
def _runner_dir() -> Path:
    """Folder kerja Gatling: tempat simulations/ dan results/."""
    env = os.getenv("GATLING_RUNNER_DIR")
    if env:
        return Path(env)
    # Default: <project_root>/gatling-runner
    return Path(__file__).resolve().parent.parent.parent / "gatling-runner"


def _scala_cli_cmd() -> str:
    """
    Lokasi scala-cli. Prioritas: env GATLING_SCALA_CLI -> PATH -> lokasi winget default.
    """
    env = os.getenv("GATLING_SCALA_CLI")
    if env and Path(env).exists():
        return env
    found = shutil.which("scala-cli")
    if found:
        return found
    fallback = r"C:\Program Files\scala-cli-x86_64-pc-win32\scala-cli.exe"
    return fallback if Path(fallback).exists() else "scala-cli"


def _gatling_dep_header() -> str:
    """
    Baris directive scala-cli untuk Gatling. Versi bisa di-override via env.
    Script yang digenerate generate_gatling_script_tool TIDAK memuat header ini,
    jadi runner menambahkannya sendiri di depan.
    """
    version = os.getenv("GATLING_VERSION", "3.11.5")
    scala_version = os.getenv("GATLING_SCALA_VERSION", "2.13")
    return (
        f'//> using dep "io.gatling.highcharts:gatling-charts-highcharts:{version}"\n'
        f'//> using scala "{scala_version}"\n'
    )


def _ensure_dep_header(script: str) -> str:
    """Tambahkan header dependency scala-cli bila script belum memilikinya."""
    if "//> using dep" in script:
        return script
    return _gatling_dep_header() + "\n" + script


def _simulation_class_name(script: str) -> Optional[str]:
    """Nama class saja (untuk nama file & pencarian folder report)."""
    m = re.search(r"class\s+([A-Za-z0-9_]+)\s+extends\s+Simulation", script)
    return m.group(1) if m else None


def _fully_qualified_name(script: str) -> Optional[str]:
    """
    Nama class LENGKAP dengan package, untuk argumen -s Gatling.
    Script yang digenerate memakai 'package simulations', jadi Gatling butuh
    'simulations.NamaClass', bukan 'NamaClass' saja -> kalau tidak, ClassNotFoundException.
    """
    cls = _simulation_class_name(script)
    if not cls:
        return None
    pkg = re.search(r"^\s*package\s+([A-Za-z0-9_.]+)", script, re.MULTILINE)
    return f"{pkg.group(1)}.{cls}" if pkg else cls


def _timeout_seconds(duration_seconds: int) -> int:
    """
    Batas waktu proses scala-cli. Harus jauh lebih besar dari durasi tes karena
    eksekusi pertama mengunduh Gatling/compiler, plus waktu kompilasi & buat report.
    """
    base = int(os.getenv("GATLING_RUN_TIMEOUT", "900"))  # default 15 menit
    return max(base, duration_seconds + 300)


def run_gatling_simulation(
    simulation_name: str,
    script: str,
    duration_seconds: int = 30,
) -> Dict[str, Any]:
    """
    Jalankan satu simulasi Gatling sungguhan.

    Return dict:
      - success: bool
      - metrics: dict metrik nyata dari stats.json (bila sukses)
      - report_dir: path folder hasil Gatling
      - stdout_tail / error: untuk diagnosa bila gagal
    """
    runner = _runner_dir()
    sims_dir = runner / "simulations"
    results_dir = runner / "results"
    sims_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    class_name = _simulation_class_name(script)
    if not class_name:
        return {"success": False, "error": "Nama class Simulation tidak ditemukan di script."}
    fqn = _fully_qualified_name(script)  # nama lengkap dengan package untuk -s Gatling

    # Bersihkan folder simulations supaya scala-cli hanya melihat SATU script.
    # Kalau ada beberapa .scala, scala-cli bisa menjalankan class yang salah.
    for old in sims_dir.glob("*.scala"):
        try:
            old.unlink()
        except OSError:
            pass

    full_script = _ensure_dep_header(script)
    script_path = sims_dir / f"{class_name}.scala"
    script_path.write_text(full_script, encoding="utf-8")

    scala_cli = _scala_cli_cmd()
    cmd = [
        scala_cli, "run", str(script_path),
        "--main-class", "io.gatling.app.Gatling",
        "--", "-s", fqn, "-rf", str(results_dir),
    ]

    print(f"[Gatling Runner] Menjalankan: {class_name} (durasi target {duration_seconds}s)")
    print(f"[Gatling Runner] scala-cli: {scala_cli}")

    # Catat waktu mulai agar hanya report yang dibuat SESUDAH ini yang diambil,
    # bukan report dari eksekusi sebelumnya.
    run_started = time.time()
    t0 = run_started
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(runner),
            capture_output=True,
            text=True,
            timeout=_timeout_seconds(duration_seconds),
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Eksekusi Gatling melebihi batas waktu {_timeout_seconds(duration_seconds)}s."}
    except FileNotFoundError:
        return {"success": False, "error": f"scala-cli tidak ditemukan di '{scala_cli}'. Set GATLING_SCALA_CLI di .env."}

    elapsed = round(time.time() - t0, 1)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")

    # Gatling memberi exit code != 0 bila ADA assertion yang gagal, padahal
    # tesnya tetap berjalan dan report tetap dibuat. Jadi jangan andalkan exit code;
    # andalkan keberadaan stats.json. Yang benar-benar gagal adalah bila report
    # tidak terbentuk sama sekali.
    report_dir = _latest_report_dir(results_dir, class_name, run_started)
    if not report_dir:
        tail = "\n".join(output.strip().splitlines()[-20:])
        return {
            "success": False,
            "error": "Report Gatling tidak terbentuk. Kemungkinan kompilasi/eksekusi gagal.",
            "stdout_tail": tail,
            "elapsed": elapsed,
        }

    stats = _parse_stats_json(report_dir)
    if not stats:
        return {
            "success": False,
            "error": "stats.json tidak terbaca dari report Gatling.",
            "report_dir": str(report_dir),
            "elapsed": elapsed,
        }

    stats["elapsed_seconds"] = elapsed
    return {
        "success": True,
        "metrics": stats,
        "report_dir": str(report_dir),
        "simulation_class": class_name,
        "elapsed": elapsed,
    }


def _latest_report_dir(results_dir: Path, class_name: str, run_started: float) -> Optional[Path]:
    """
    Folder report Gatling bernama '<classlowercase>-<timestamp>'. Ambil yang
    dibuat SESUDAH run dimulai dan mengandung js/stats.json.

    Filter run_started penting: tanpa itu, report dari eksekusi lama bisa terambil
    dan metrik yang dilaporkan jadi salah (bug yang sempat terjadi saat verifikasi).
    """
    prefix = class_name.lower()

    def fresh(d: Path) -> bool:
        # beri toleransi 5 detik mundur untuk selisih jam pembuatan folder
        return d.is_dir() and (d / "js" / "stats.json").exists() and d.stat().st_mtime >= (run_started - 5)

    candidates = [d for d in results_dir.glob(f"{prefix}-*") if fresh(d)]
    if not candidates:
        candidates = [d for d in results_dir.glob("*") if fresh(d)]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


def _parse_stats_json(report_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Baca metrik NYATA dari stats.json Gatling.
    Struktur (terverifikasi dari output Gatling 3.11):
      stats.numberOfRequests {total, ok, ko}
      stats.minResponseTime / maxResponseTime / meanResponseTime {total}
      stats.percentiles3 {total}  -> p95
      stats.percentiles4 {total}  -> p99
      stats.meanNumberOfRequestsPerSecond {total}
    """
    stats_file = report_dir / "js" / "stats.json"
    try:
        data = json.loads(stats_file.read_text(encoding="utf-8"))
        s = data.get("stats", {})

        def val(key: str) -> float:
            node = s.get(key) or {}
            return float(node.get("total", 0) or 0)

        total = int(val("numberOfRequests"))
        ok = int((s.get("numberOfRequests") or {}).get("ok", 0) or 0)
        ko = int((s.get("numberOfRequests") or {}).get("ko", 0) or 0)
        error_rate = round((ko / total) * 100, 2) if total > 0 else 0.0

        return {
            "total_requests": total,
            "successful_requests": ok,
            "failed_requests": ko,
            "error_rate": error_rate,
            "min_response_time": val("minResponseTime"),
            "max_response_time": val("maxResponseTime"),
            "mean_response_time": val("meanResponseTime"),
            "p95_response_time": val("percentiles3"),
            "p99_response_time": val("percentiles4"),
            "throughput_rps": round(val("meanNumberOfRequestsPerSecond"), 2),
        }
    except Exception as e:
        print(f"[Gatling Runner] Gagal parse stats.json: {e}")
        return None
