import os
import json
import subprocess
import traceback
import threading
import time
import uuid
import socket

from flask import Flask
from flask import request
from filelock import FileLock
from apscheduler.schedulers.background import BackgroundScheduler



def _worker_run(base_state, stdout, stderr, info, cmd, options, cancel):
    def update_status(obj):
        base_state.update(obj)
        with FileLock(info + ".lock"):
            with open(info, "w") as fp:
                json.dump(base_state, fp)

    update_status({})

    with open(stdout, "w") as stdout:
        with open(stderr, "w") as stderr:
            try:
                p = subprocess.Popen(
                    cmd,
                    stdout=stdout,
                    stderr=stderr,
                    **options
                )
                update_status({
                    "job_state": ["RUNNING"]
                })

                rc = None
                while True:
                    if cancel.is_set():
                        os.getpgid(p.pid)

                    rc = p.poll()
                    time.sleep(0.2)
                    break

                p.wait()

                status = "WTF"
                if rc is not None:
                    if cancel.is_set():
                        status = "CANCELLED"
                    elif rc == 0:
                        status = "COMPLETED"
                    else:
                        status = "FAILED"

                update_status({
                    "job_state": [status]
                })

            except:
                update_status({
                    "job_state": ["FAILED"]
                })
                traceback.print_exc(file=stderr)


def run(job_dir, job_id, cmd, **options):
    base = os.path.join(job_dir, job_id)
    os.makedirs(os.path.join(job_dir, job_id, "meta"), exist_ok=True)

    stdout = os.path.join(base, "log.stdout")
    stderr = os.path.join(base, "log.stderr")
    info = os.path.join(base, "meta", "info.json")
    cmd_pth = os.path.join(base, "cmd.sh")
    script_pth = os.path.join(base, "script.sbatch")
    state ={
        "job_state": ["UNKNOWN"],
        "comment": f"jr_job_id={job_id}",
    }

    with open(script_pth, "w") as fp:
        json.dump(cmd, fp)
    
    with open(cmd_pth, "w") as fp:
        fp.write(f"bash {script_pth}")
    
    cancel_event = threading.Event()

    thread = threading.Thread(
        target=_worker_run,
        kwargs=dict(
            base_state=state,
            stdout=stdout,
            stderr=stderr,
            info=info,
            cmd=cmd,
            options=options,
            cancel=cancel_event
        ),
        daemon=True,
    )

    thread.start()

    return {
        "job_id": job_id,
        "thread": thread,
        "cancel": cancel_event.set,
        "next": []
    }
        

def make_job_name(job_dir):
    unique_id = str(uuid.uuid4())[:8]
    now = int(time.time() - 1766176827)
    return f"{now:5d}_{unique_id}"


def server():
    app = Flask(__name__)
    job_dir = os.getenv("MILABENCH_AGENT_JOB_DIR")
    job_registry = []

    scheduler = BackgroundScheduler()
    app.scheduler = scheduler
    app.scheduler.start()
    app.scheduler.add_job(check_jobs, 'interval', seconds=60)

    def get_job(name):
        for job in job_registry:
            if job["job_id"] == name:
                return job

    def schedule_next(next_job):
        pass

    def check_jobs():
        """Check current threads, remove finished and run dependent"""
        finished = []
        for job in job_registry:
            if not job["thread"].is_alive():
                finished.append(job)
        
        for job in finished:
            job_registry.remove(job)

        for job in finished:
            if job["next"]:
                schedule_next(job["next"])

    @app.route("/popen", methods=['POST'])
    def run_command():
        arguments = request.json
        job_name = make_job_name()

        job_state = run( 
            job_dir,
            job_name,
            arguments["cmd"],
            arguments["options"]
        )

        job_registry.append(job_state)

    @app.route("/config")
    def config():
        return {
            "name": socket.gethostname(),
            "ssh": "",
            "remote_folder": job_dir,
            "config": {

            }
        }

    return app
