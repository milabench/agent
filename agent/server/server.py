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
                        break

                    rc = p.poll()
                    if rc is not None:
                        break

                    time.sleep(0.2)

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
    
    with open(cmd_pth, "w") as fp:
        if isinstance(cmd, list):
            fp.write(" ".join(cmd))
        else:
            fp.write(cmd)
    
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
        

def make_job_name(job_name=None):
    unique_id = str(uuid.uuid4())[:8]
    now = int(time.time() - 1766176827)
    if job_name is not None:
        return f"{job_name}_{now:5d}_{unique_id}"
    return f"{now:5d}_{unique_id}"


def server():
    import threading

    app = Flask(__name__)
    job_dir = os.getenv("AGENT_JOB_DIR")
    job_registry = []  
    scheduler = BackgroundScheduler()
    app.scheduler = scheduler
    app.scheduler.start()
 
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

    app.scheduler.add_job(check_jobs, 'interval', seconds=60)

    @app.route("/rpc", methods=['POST'])
    def rpc():
        """Call to python, returns json"""
        pass

    @app.route("/jobs/list", methods=['GET'])
    def list_jobs():
        return [j["job_id"] for j in job_registry]

    def tail(path, n=10):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return list(deque(f, maxlen=n))

    def job_log(job_id, name, n):
        base = os.path.join(job_dir, job_id)
        stdout = os.path.join(base, f"log.{name}")
        return tail(name, n)

    @app.route("/job/<string:job_id>/status", methods=['GET'])
    def job_status(job_id):
        base = os.path.join(job_dir, job_id)
        info = os.path.join(base, "meta", "info.json")
        with FileLock(info + ".lock"):
            with open(info, "r") as fp:
                return json.load(fp)

    @app.route("/job/<string:job_id>/log/stdout/tail", methods=['GET'])
    @app.route("/job/<string:job_id>/log/stdout/tail/<int:n>", methods=['GET'])
    def job_stdout(job_id, n=100):
        return job_log(job_id, "stdout", n)

    @app.route("/job/<string:job_id>/log/stdout/tail", methods=['GET'])
    @app.route("/job/<string:job_id>/log/stdout/tail/<int:n>", methods=['GET'])
    def job_stderr(job_id, n=100):
        return job_log(job_id, "stderr", n)

    @app.route("/jobs/submit", methods=['POST'])
    def submit_job():
        arguments = request.get_json()

        job_id = make_job_name(arguments.get("job_name"))
        base = os.path.join(job_dir, job_id)
        os.makedirs(os.path.join(job_dir, job_id, "meta"), exist_ok=True)

        script_path = os.path.join(base, "script.sbatch")
        arguments = request.get_json()

        with open(script_path, "w") as fp:
            fp.write(arguments["script"])

        cmd = ["bash", script_path]
        
        job_state = run( 
            job_dir,
            job_id,
            cmd,
            **arguments.get("options", {})
        )

        job_registry.append(job_state)
        return {"status": "ok", "job_id": job_id}

    @app.route("/popen", methods=['POST'])
    def run_command():
        """Make a job run"""
        arguments = request.get_json()
        job_name = make_job_name(arguments.get("job_name"))

        job_state = run( 
            job_dir,
            job_name,
            arguments["cmd"],
            **arguments.get("options", {})
        )

        job_registry.append(job_state)

    @app.route("/config")
    def config():
        return {
            "name": socket.gethostname(),
            "remote_folder": job_dir,
            "ssh": "",
            "config": {

            }
        }

    return app
