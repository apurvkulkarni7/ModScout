import subprocess
import os
import threading
import time
from datetime import datetime
from flask import (
    Flask,
    jsonify,
    render_template_string,
    render_template,
    request,
    send_file,
)
import json
from dotenv import load_dotenv
import schedule
import re

load_dotenv()

app = Flask(__name__)

################################################################################
# Configuration
################################################################################
HPC_USERNAME = os.getenv("HPC_USERNAME")
HPC_SSH_KEY = os.getenv("HPC_SSH_KEY")

SYSTEMS = {}
for key, value in os.environ.items():
    match = re.match(r'SYSTEM_(\d+)_NAME', key)
    if match:
        system_index = match.group(1)
        system_name = value
        system_host = os.environ.get(f'SYSTEM_{system_index}_HOST')
        SYSTEMS[system_name] = {'host': system_host}

REMOTE_CMD = "$LMOD_DIR/spider -o jsonSoftwarePage $MODULEPATH"
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

DAY_MAP = {
    'monday': schedule.every().monday,
    'tuesday': schedule.every().tuesday,
    'wednesday': schedule.every().wednesday,
    'thursday': schedule.every().thursday,
    'friday': schedule.every().friday,
    'saturday': schedule.every().saturday,
    'sunday': schedule.every().sunday,
}
UPDATE_SCHEDULE = os.getenv('UPDATE_SCHEDULE')
update_day, update_time = UPDATE_SCHEDULE.split()

# State tracking
JOB_STATUS = {}
for system in SYSTEMS.keys():
    JOB_STATUS[system] = {"last_run": "Never", "is_running": False}

################################################################################
# Helper Functions
################################################################################
def process_data(system_name):
    with open(os.path.join(DATA_DIR, f"raw_{system_name}.json"), "r") as f:
        raw_data = json.load(f)

    tree = {}
    for entry in raw_data:
        package = entry["package"]
        description = entry.get("description", "No description available.")
        url = entry.get("url", "No URL available.").strip()
        for version in entry["versions"]:
            v_name = version["versionName"]
            full_name = f"{package}/{v_name}"
            for parent_set in version.get("parent", []):
                release = parent_set[0] if len(parent_set) > 0 else "Core"
                compiler = " ".join(parent_set[1:]) if len(parent_set) > 1 else "None"

                if release not in tree:
                    tree[release] = {}
                if compiler not in tree[release]:
                    tree[release][compiler] = []

                tree[release][compiler].append(
                    {
                        "package": package,
                        "version": v_name,
                        "name": full_name,
                        "description": description,
                        "url": url,
                        "release": release,
                        "compiler": compiler.replace("None", "Standalone"),
                        "load_cmd": f"module load {release} {compiler.replace('None', '')} {full_name}",
                    }
                )

    with open(os.path.join(DATA_DIR, f"processed_module_{system_name}.json"), "w") as f:
        json.dump(tree, f, indent=4)

def fetch_module_data(system_name):
    if JOB_STATUS[system_name]["is_running"]:
        return

    JOB_STATUS[system_name]["is_running"] = True
    print(f"{str(system_name).capitalize()} system module data update started at {datetime.now()}")

    # for sys in SYSTEMS:
    local_path = os.path.join(DATA_DIR, f"raw_{system_name}.json")
    try:
        # Native SSH call
        result = subprocess.run(
            [
                "ssh",
                "-i",
                f"{HPC_SSH_KEY}",
                f"{HPC_USERNAME}@{SYSTEMS[system_name]['host']}",
                REMOTE_CMD,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        with open(local_path, "w") as f:
            f.write(result.stdout)
        
    except Exception as e:
        print(f"[!] Error on {system_name}: {e}")

    process_data(system_name)
    print(f"{str(system_name).capitalize()} system module data update completed at {datetime.now()}")
    JOB_STATUS[system_name]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    JOB_STATUS[system_name]["is_running"] = False

def auto_update():
     for sys in SYSTEMS.keys():
        print(f"Starting update for {sys}")
        threading.Thread(target=fetch_module_data, args=(sys,)).start()

def background_scheduler():
        (DAY_MAP[update_day.lower()]).at(update_time).do(auto_update)
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                print(f"Error in background_scheduler: {e}")

################################################################################
# Routes
################################################################################
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/module")
def module():
    system = request.args.get("system")
    return render_template("module.html", system=system)


@app.route("/module/data")
def module_data():
    system = request.args.get("system")
    file_path = os.path.join(DATA_DIR, f"processed_module_{system}.json")
    return send_file(file_path, mimetype="application/json")

@app.route("/update")
def update():
    for sys in SYSTEMS.keys():
        print(f"Starting update for {sys}")
        threading.Thread(target=fetch_module_data, args=(sys,)).start()
    return jsonify({"message": "Update started"}), 202

@app.route('/status')
def get_status():
    for i in JOB_STATUS:
        if JOB_STATUS[i]['is_running']:
            return jsonify({'status': 'running','last_run': JOB_STATUS[i]['last_run']})
        else:
            job_status = 'completed'
            last_run = JOB_STATUS[i]['last_run']
    return jsonify({'status': job_status, 'last_run': last_run})

if __name__ == "__main__":
    # Start the scheduler thread
    scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
    scheduler_thread.start()

    app.run(debug=True, port=5000)
