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
import pprint
from itertools import combinations
from utils import recommendations, has_conflict

load_dotenv()

app = Flask(__name__)

################################################################################
# Configuration
################################################################################
APP_PORT = int(os.getenv("APP_PORT", 8000))

HPC_USERNAME = os.getenv("HPC_USERNAME")
HPC_SSH_KEY = os.getenv("HPC_SSH_KEY")

SYSTEMS = {}
for key, value in os.environ.items():
    match = re.match(r"SYSTEM_(\d+)_NAME", key)
    if match:
        system_index = match.group(1)
        system_name = value
        system_host = os.environ.get(f"SYSTEM_{system_index}_HOST")
        SYSTEMS[system_name] = {"host": system_host}

REMOTE_CMD = "$LMOD_DIR/spider -o jsonSoftwarePage $MODULEPATH"
DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

DATA_DICTIONARY = {}

DAY_MAP = {
    "monday": schedule.every().monday,
    "tuesday": schedule.every().tuesday,
    "wednesday": schedule.every().wednesday,
    "thursday": schedule.every().thursday,
    "friday": schedule.every().friday,
    "saturday": schedule.every().saturday,
    "sunday": schedule.every().sunday,
}
UPDATE_SCHEDULE = os.getenv("UPDATE_SCHEDULE")
update_day, update_time = UPDATE_SCHEDULE.split()

# State tracking
JOB_STATUS = {}
for system in SYSTEMS.keys():
    JOB_STATUS[system] = {"last_run": "Never", "is_running": False}


################################################################################
# Helper Functions
################################################################################
def get_data_dictionary(system):
    file_path = os.path.join(DATA_DIR, f"processed_module_{system}.json")
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
        DATA_DICTIONARY[system] = data
    return DATA_DICTIONARY.get(system, {})


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
                        "compiler": compiler.replace("None", ""),
                        "load_cmd": f"module load {release} {compiler.replace('None', '')} {full_name}",
                    }
                )

    with open(os.path.join(DATA_DIR, f"processed_module_{system_name}.json"), "w") as f:
        json.dump(tree, f, indent=4)


def fetch_module_data(system_name):
    if JOB_STATUS[system_name]["is_running"]:
        return

    JOB_STATUS[system_name]["is_running"] = True
    print(
        f"{str(system_name).capitalize()} system module data update started at {datetime.now()}"
    )

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
    print(
        f"{str(system_name).capitalize()} system module data update completed at {datetime.now()}"
    )
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



def search(data, query):
    filtered_data = {}

    if query is None or query == "":
        filtered_data = data

    # Split and clean queries
    search_queries = [q.strip() for q in query.split(",") if q.strip()]

    for search_query in search_queries:
        search_query_lower = search_query.lower()

        # Parse package and version if "/" is present
        package_query, version_query = None, None
        if "/" in search_query:
            parts = search_query_lower.split("/", 1)
            package_query = parts[0]
            version_query = parts[1] if len(parts) > 1 else ""

        for release, compilers in data.items():
            for compiler, modules in compilers.items():
                filtered_modules = []

                for mod in modules:
                    mod_pkg = mod.get("package", "").lower()
                    mod_ver = mod.get("version", "").lower()
                    mod_desc = mod.get("description", "").lower()

                    # If "package/version" format used
                    if package_query is not None:
                        if package_query in mod_pkg and version_query in mod_ver:
                            filtered_modules.append(mod)
                    # Generic search in package or description
                    elif (
                        search_query_lower in mod_pkg or search_query_lower in mod_desc
                    ):
                        filtered_modules.append(mod)

                if filtered_modules:
                    # Initialize nested dicts safely
                    if release not in filtered_data:
                        filtered_data[release] = {}
                    if compiler not in filtered_data[release]:
                        filtered_data[release][compiler] = []

                    # Prevent duplicate modules if multiple queries match the same thing
                    for m in filtered_modules:
                        if m not in filtered_data[release][compiler]:
                            filtered_data[release][compiler].append(m)
    # sorted_releases = sorted(filtered_data.keys(), reverse=True)
    # final_response = {}
    # for rel in sorted_releases:
    #     compilers = filtered_data[rel]
    #     none_compilers = [c for c in compilers.keys() if c.strip().lower() == "none" or c.strip() == ""]
    #     other_compilers = [c for c in compilers.keys() if c not in none_compilers]
    #     sorted_compilers = none_compilers + sorted(other_compilers)
    #     final_response[rel] = {c: compilers[c] for c in sorted_compilers}
    return filtered_data


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


@app.route("/module/data", methods=["GET"])
def module_data():
    system = request.args.get("system")
    file_path = os.path.join(DATA_DIR, f"processed_module_{system}.json")
    return send_file(file_path, mimetype="application/json")


@app.route("/update", methods=["GET"])
def update():
    for sys in SYSTEMS.keys():
        print(f"Starting update for {sys}")
        threading.Thread(target=fetch_module_data, args=(sys,)).start()
    return jsonify({"message": "Update started"}), 202


@app.route("/status", methods=["GET"])
def get_status():
    for i in JOB_STATUS:
        if JOB_STATUS[i]["is_running"]:
            return jsonify({"status": "running", "last_run": JOB_STATUS[i]["last_run"]})
        else:
            job_status = "completed"
            last_run = JOB_STATUS[i]["last_run"]
    return jsonify({"status": job_status, "last_run": last_run})


@app.route("/module/search", methods=["GET"])
def search_module():
    system = request.args.get("system")
    search_query = request.args.get("query", "")
    data = get_data_dictionary(system)

    filtered_data = search(data, search_query)
    return jsonify(filtered_data)


@app.route("/module/conflict", methods=["POST"])
def conflict_check():
    data = request.get_json(force=True)
    selected_modules = data.get('selected',[])
    conflict, msg = has_conflict(selected_modules)

    if conflict:
        all_modules = get_data_dictionary(system='barnard')
        suggestions = recommendations(selected_modules,all_modules)
    else:
        suggestions = {}
    return jsonify({"conflict": conflict, "msg": msg, "suggestions": suggestions})


if __name__ == "__main__":
    scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
    scheduler_thread.start()
    app.run(debug=True, port=APP_PORT)
