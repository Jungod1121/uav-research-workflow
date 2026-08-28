#!/usr/bin/env python3
"""
UAV Research Workflow — 监控台后端
聚合: docker-build / uav-sim / experiments / system / ros
"""
import glob
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT
TMP = Path("/tmp/opencode")
ROS_LOG_BASE = Path.home() / ".ros/log"

app = FastAPI(title="UAV Workflow Monitor", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- helpers ----------
def sh(cmd: str, timeout=8) -> tuple[str, int]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip(), r.returncode
    except subprocess.TimeoutExpired as e:
        return (e.stdout or "") + "\n[TIMEOUT]", 124
    except Exception as e:
        return str(e), 1

def tail_file(p: Path, lines=120) -> str:
    try:
        if not p.exists():
            return f"(no file: {p})"
        out, _ = sh(f"tail -n {lines} {str(p)!r} 2>&1 | cat -v | head -c 12000")
        # strip ANSI color codes for clean display, keep bracket tags
        out = re.sub(r"\x1b\[[0-9;]*m", "", out)
        return out or "(empty)"
    except Exception as e:
        return str(e)

def latest_docker_log() -> Path | None:
    cands = sorted(TMP.glob("docker_build*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None

def scan_experiments(limit=20):
    exps = []
    exp_root = WF / "experiments"
    if not exp_root.exists():
        return []
    for d in sorted(exp_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir() or d.name.startswith("."):
            continue
        meta = {}
        for cand in [d / "metadata.json", d / "metrics.json"]:
            if cand.exists():
                try: meta = json.loads(cand.read_text()[:8000]); break
                except: pass
        # fallback: try nested single-exp dirs (sweep runs)
        if not meta:
            # sweep aggregate
            summary = d / "summary.md"
            if summary.exists():
                meta = {"_type": "sweep"}
        mtime = datetime.fromtimestamp(d.stat().st_mtime).strftime("%m-%d %H:%M")
        exps.append({
            "id": d.name,
            "mtime": mtime,
            "ts": d.stat().st_mtime,
            "type": meta.get("_type", "exp"),
            "reach": meta.get("reached") or meta.get("reach") or "-",
            "drift": meta.get("drift_max_m", meta.get("err_mean_m", "-")),
            "events": len(meta.get("events", [])),
        })
        if len(exps) >= limit:
            break
    return exps

# ---------- API ----------
@app.get("/api/status")
def api_status():
    # docker-build
    db_out, _ = sh("systemctl --user is-active docker-build.service 2>&1", timeout=5)
    db_active = db_out.strip() == "active"
    db_log = latest_docker_log()
    db_tail = tail_file(db_log, 6) if db_log else ""
    db_success = False
    if db_log and db_log.exists():
        txt = tail_file(db_log, 400)
        db_success = "Successfully tagged uav-sim:humble" in txt or "Successfully built" in txt
    # fallback: image exists == success (log may be gone after reboot /tmp cleared)
    if not db_success:
        img_check,_ = sh("sg docker -c 'docker images --format \"{{.Repository}}:{{.Tag}}\" 2>/dev/null | grep -q \"^uav-sim:humble\" && echo yes' 2>&1", timeout=5)
        if "yes" in img_check:
            db_success = True
            if not db_tail or "(no file" in db_tail:
                db_tail = "(log cleared after reboot — image uav-sim:humble exists ✓)"

    # uav-sim
    sim_out, _ = sh("systemctl --user is-active uav-sim.service 2>&1", timeout=5)
    sim_active = sim_out.strip() == "active"
    sim_log_path = WF / "experiments/.live/v2_launch.log"
    # also try journal? fallback to ROS log dir
    sim_tail = tail_file(sim_log_path, 8) if sim_log_path.exists() else ""

    # docker images / container
    img_out, _ = sh("sg docker -c 'docker images 2>/dev/null | grep -E \"uav-sim|REPOSITORY\"' 2>&1", timeout=8)
    cont_out, _ = sh("sg docker -c 'docker ps --format \"{{.Names}}:{{.Status}}\" 2>/dev/null | grep uav-sim' 2>&1", timeout=8)

    # ros topics (quick, skip if sim not active to avoid hang)
    ros_hz = "-"
    if sim_active:
        hz_out, _ = sh("bash -c 'source /opt/ros/humble/setup.bash 2>/dev/null && source ~/px4_ros2_ws/install/setup.bash 2>/dev/null && export ROS_DOMAIN_ID=77 && timeout 6 ros2 topic hz /fmu/out/sensor_combined --window 6 2>&1 | tail -1' 2>&1", timeout=12)
        m = re.search(r"min:\s*([\d.]+)s", hz_out)
        ros_hz = m.group(0) if m else hz_out.strip()[:40] or "-"

    # system
    try:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(str(WF))
        sysinfo = {
            "cpu": psutil.cpu_percent(interval=None),
            "mem_used_gb": round((mem.total - mem.available)/1024**3,1),
            "mem_total_gb": round(mem.total/1024**3,1),
            "disk_free_gb": round(disk.free/1024**3,1),
            "load": os.getloadavg()[0],
        }
    except:
        sysinfo = {"cpu": "-", "mem_used_gb": "-", "mem_total_gb": "-", "disk_free_gb": "-", "load": "-"}

    return {
        "ts": int(time.time()*1000),
        "docker_build": {"active": db_active, "success": db_success, "log": db_tail, "path": str(db_log) if db_log else ""},
        "sim": {"active": sim_active, "log": sim_tail},
        "docker": {"images": img_out[:1800], "container": cont_out[:600]},
        "ros": {"hz": ros_hz},
        "system": sysinfo,
        "wf_root": str(WF),
    }

@app.get("/api/logs")
def api_logs(name: str = Query("docker_build", description="docker_build|sim|px4|ros"), lines: int = 120):
    mapping = {
        "docker_build": latest_docker_log() or TMP / "docker_build18.log",
        "docker_build18": TMP / "docker_build18.log",
        "sim": WF / "experiments/.live/v2_launch.log",
        "px4": WF / "experiments/.live/px4.log",
        "ros": ROS_LOG_BASE,
    }
    # ros: latest launch.log
    if name == "ros":
        cands = sorted(ROS_LOG_BASE.glob("2026-08-*/launch.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        p = cands[0] if cands else None
        if not p: return {"name": name, "path": "", "text": "(no ros log)"}
        return {"name": name, "path": str(p), "text": tail_file(p, lines)}
    p = mapping.get(name)
    if not p:
        return {"name": name, "path": "", "text": f"unknown log name: {name}"}
    return {"name": name, "path": str(p), "text": tail_file(p, lines)}

@app.get("/api/experiments")
def api_experiments():
    return {"experiments": scan_experiments(30)}

@app.post("/api/sim/{action}")
def api_sim(action: str):
    if action not in ("start","stop","restart"):
        return {"ok": False, "msg": "action must be start|stop|restart"}
    if action == "stop":
        out,_ = sh("systemctl --user stop uav-sim.service 2>&1; timeout 12 ~/work/uav-research-workflow/scripts/sim_stop.sh 2>&1 | tail -1", timeout=20)
        return {"ok": True, "out": out[-800:]}
    if action == "start":
        out,_ = sh("systemctl --user reset-failed 2>/dev/null; systemd-run --user --unit=uav-sim --working-directory=/home/jungod/work/uav-research-workflow bash -c 'source /opt/ros/humble/setup.bash && source ~/px4_ros2_ws/install/setup.bash && export ROS_DOMAIN_ID=77 STACK_INSTANCES=2 && ros2 launch launch/sim_stack.launch.py >experiments/.live/v2_launch.log 2>&1' 2>&1 | head -1", timeout=20)
        return {"ok": True, "out": out[-800:]}
    # restart
    sh("systemctl --user stop uav-sim.service 2>&1; timeout 12 ~/work/uav-research-workflow/scripts/sim_stop.sh 2>&1 | tail -1", timeout=25)
    time.sleep(1)
    out,_ = sh("systemctl --user reset-failed 2>/dev/null; systemd-run --user --unit=uav-sim --working-directory=/home/jungod/work/uav-research-workflow bash -c 'source /opt/ros/humble/setup.bash && source ~/px4_ros2_ws/install/setup.bash && export ROS_DOMAIN_ID=77 STACK_INSTANCES=2 && ros2 launch launch/sim_stack.launch.py >experiments/.live/v2_launch.log 2>&1' 2>&1 | head -1", timeout=20)
    return {"ok": True, "out": out[-800:]}

@app.get("/api/docker/{action}")
def api_docker(action: str):
    if action == "ps":
        out,_ = sh("sg docker -c 'docker ps --format \"table {{.Names}}\\t{{.Status}}\\t{{.Image}}\" 2>&1 | head -10' 2>&1", timeout=10)
        return {"out": out}
    if action == "images":
        out,_ = sh("sg docker -c 'docker images 2>&1 | head -10' 2>&1", timeout=10)
        return {"out": out}
    return {"out": "unknown"}

# ---------- static ----------
STATIC = Path(__file__).parent / "static"
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

@app.get("/")
def index():
    idx = STATIC / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return {"msg": "webui running, static/index.html not found"}

@app.get("/health")
def health(): return {"ok": True}
