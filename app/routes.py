import os
import threading
from flask import (
    jsonify,
    render_template,
    request,
    send_file,
    Blueprint,
    current_app
)
from app.utils import (
    suggestions,
    has_conflict,
    fetch_module_data,
    search,
    get_data_dictionary
)

routes_bp = Blueprint('routes', __name__)

################################################################################
# Routes
################################################################################
@routes_bp.route("/")
def index():
    return render_template("index.html")

@routes_bp.route("/update", methods=["GET"])
def update():
    app = current_app._get_current_object()
    for sys in current_app.config["CUSTOM_CONFIG"].systems.keys():
        print(f"Starting update for {sys}")
        threading.Thread(target=fetch_module_data, args=(app, sys)).start()
    return jsonify({"message": "Update started"}), 202


@routes_bp.route("/status", methods=["GET"])
def get_status():
    for i in current_app.config["CUSTOM_CONFIG"].update_job_status.keys():
        if current_app.config["CUSTOM_CONFIG"].update_job_status[i]["is_running"]:
            return jsonify(
                {
                    "status": "running",
                    "last_run": current_app.config["CUSTOM_CONFIG"].update_job_status[i]["last_run"],
                }
            )
        else:
            job_status = "completed"
            last_run = current_app.config["CUSTOM_CONFIG"].update_job_status[i]["last_run"]
    return jsonify({"status": job_status, "last_run": last_run})


@routes_bp.route("/module")
def module():
    system = request.args.get("system")
    return render_template("module.html", system=system)


@routes_bp.route("/module/data", methods=["GET"])
def module_data():
    system = request.args.get("system")
    file_path = os.path.join(current_app.config["CUSTOM_CONFIG"].data_dir, f"processed_module_{system}.json")
    return send_file(file_path, mimetype="application/json")


@routes_bp.route("/module/search", methods=["GET"])
def search_module():
    system = request.args.get("system")
    search_query = request.args.get("query", "")
    data = get_data_dictionary(system)

    filtered_data = search(data, search_query)
    return jsonify(filtered_data)


@routes_bp.route("/module/conflict", methods=["POST"])
def conflict_check():
    data = request.get_json(force=True)
    selected_modules = data.get("selected", [])
    conflict, msg = has_conflict(selected_modules)

    if conflict:
        all_modules = get_data_dictionary(system="barnard")
        suggestions = suggestions(selected_modules, all_modules)
    else:
        suggestions = {}
    return jsonify({"conflict": conflict, "msg": msg, "suggestions": suggestions})