from datetime import datetime
import time
import json
import os
import subprocess
from itertools import combinations, product
import threading
from flask import app, current_app
import schedule


def get_data_dictionary(system):
    cfg = current_app.config["CUSTOM_CONFIG"]
    file_path = os.path.join(cfg.data_dir, f"processed_module_{system}.json")
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
        cfg.data_dictionary[system] = data
        # print(f"Data dictionary for {system} loaded.")
    return cfg.data_dictionary.get(system, {})


def process_data(system_name):
    with open(
        os.path.join(
            current_app.config["CUSTOM_CONFIG"].data_dir, f"raw_{system_name}.json"
        ),
        "r",
    ) as f:
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

    with open(
        os.path.join(
            current_app.config["CUSTOM_CONFIG"].data_dir,
            f"processed_module_{system_name}.json",
        ),
        "w",
    ) as f:
        json.dump(tree, f, indent=4)


def fetch_module_data(app, system_name):
    with app.app_context():
        cfg = app.config["CUSTOM_CONFIG"]
        if cfg.update_job_status[system_name]["is_running"]:
            return

        cfg.update_job_status[system_name]["is_running"] = True
        print(
            f"{str(system_name).capitalize()} system module data update started at {datetime.now()}"
        )

        # Fetch normal data
        local_path = os.path.join(
            current_app.config["CUSTOM_CONFIG"].data_dir, f"raw_{system_name}.json"
        )
        remote_cmd = "$LMOD_DIR/spider -o jsonSoftwarePage $MODULEPATH"
        try:
            # Native SSH call
            result = subprocess.run(
                [
                    "ssh",
                    "-i",
                    f"{cfg.hpc_ssh_key}",
                    f"{cfg.hpc_username}@{cfg.systems[system_name]['host']}",
                    remote_cmd,
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

        # Fetching extension information

        # Set update task status
        cfg.update_job_status[system_name]["last_run"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        cfg.update_job_status[system_name]["is_running"] = False


def auto_update(app):
    with app.app_context():
        cfg = app.config["CUSTOM_CONFIG"]
        for sys in cfg.systems.keys():
            print(f"Starting update for {sys}")
            threading.Thread(target=fetch_module_data, args=(app, sys)).start()


def background_scheduler(app):
    with app.app_context():
        cfg = app.config["CUSTOM_CONFIG"]
        cfg.day_map[cfg.update_day.lower()].at(cfg.update_time).do(auto_update, app)

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

    return filtered_data


def get_compiler(m):
    return m.get("compiler", "").strip()


def get_release(m):
    return m.get("release", "").strip()


def get_package(m):
    return m.get("package", "").strip()


def get_version(m):
    return m.get("version", "").split("-")[0].strip()


def has_conflict(selected):
    if len(selected) < 2:
        return False, ""

    # For different release
    for m_i, m_ii in combinations(selected, 2):
        if get_release(m_i) != get_release(m_ii):
            return True, "Modules must share the same releases."

    # If releases are same
    # Standalone
    msg = ""
    for m_i, m_ii in combinations(selected, 2):
        if (
            get_compiler(m_i) == get_compiler(m_ii)
            and get_package(m_i) == get_package(m_ii)
            and m_i.get("version") != m_ii.get("version")
        ):
            versions = tuple(sorted([m_i.get("version"), m_ii.get("version")]))
            msg += (
                f"Same modules ({get_package(m_i)}) with different versions "
                f"{versions} cannot be loaded together.\n"
            )
    if msg != "":
        return True, msg

    pkgs_with_compiler = [
        set(l.get("compiler").split(" "))
        for l in selected
        if l
        if get_compiler(l) != ""
    ]

    if len(pkgs_with_compiler) < 2:
        return False, ""

    for i in range(len(pkgs_with_compiler) - 1):
        current_set = pkgs_with_compiler[i]

        next_set = pkgs_with_compiler[i + 1]

        is_subset = current_set.issubset(next_set) or next_set == set([""])
        is_superset = current_set.issuperset(next_set) or next_set == set([""])

        if not (is_subset or is_superset):
            return True, "Modules must share the same dependencies."

    return False, ""


def clean_up_suggestion(suggestions, selected):
    selected_pkgs = [item["package"] for item in selected]

    # Deduplication
    seen = []
    filtered_pkgs = []

    for group in suggestions:
        # print(f"Evaluating group: {[item['load_cmd'] for item in group]}")  # Debug print
        # Deduplication: Check if we've processed this exact group before
        if group not in seen:
            # print(f"Adding above group to seen list.")  # Debug print
            seen.append(group)

            # Only keep if the packages match the selected list
            current_pkgs = [item["package"] for item in group]
            # print(f"Current packages: {current_pkgs}, Selected packages: {selected_pkgs}")  # Debug print
            if current_pkgs == selected_pkgs:
                # print(f"Group matches selected packages. Keeping it.")  # Debug print
                filtered_pkgs.append(group)

    return filtered_pkgs


def find_module_variant_mpackage(selected, all_modules):
    mpackage = []

    # Extract just the package names we are looking for (e.g., 'gcc', 'llvm')
    required_pkg_names = [get_package(s) for s in selected]
    # print(f"Required package names: {required_pkg_names}")  # Debug print

    for release_i in all_modules:
        for compiler_i in all_modules[release_i]:
            # print(f"Checking release: {release_i}, compiler: {compiler_i}")  # Debug print

            modules_in_bucket = all_modules[release_i][compiler_i]
            modules_in_bucket += all_modules[release_i][
                "None"
            ]  # Include 'None' compiler modules from same release
            # Group available modules by package name
            # Example: {'gcc': ['gcc/9.1', 'gcc/9.2', 'gcc/9.3'], 'llvm': ['llvm/10', 'llvm/11']}
            candidates = {name: [] for name in required_pkg_names}
            # print(f"candidates: {candidates}")  # Debug print

            for module in modules_in_bucket:
                pkg_name = get_package(module)
                if pkg_name in candidates:
                    candidates[pkg_name].append(module)

            # Ensure ALL requested packages exist in this bucket
            # If we found 3 GCCs but 0 LLVMs, this bucket is invalid for the user's request.
            if all(len(variants) > 0 for variants in candidates.values()):

                # We create a list of lists: [[gcc1, gcc2...], [llvm1, llvm2...]]
                lists_to_combine = [candidates[name] for name in required_pkg_names]

                # Generate Cartesian Product (The gcc_num x llvm_num combinations)
                # C(gcc1, llvm1), (gcc1, llvm2), (gcc2, llvm1)...
                for combination in product(*lists_to_combine):
                    variant_list = list(combination)

                    if variant_list not in mpackage:
                        mpackage.append(variant_list)

    mpackage.sort(
        reverse=True, key=lambda x: [get_release(m) for m in x]
    )  # Sort by release in descending order

    return mpackage


def format_suggestions(suggestions):
    """Build a readable string and a list of unique command strings for each suggestion."""
    suggestions_parsed = []

    for idx, suggestion in enumerate(suggestions, start=1):
        # suggestion_lines.append(f"{idx}) ")
        suggestion_i_pkgs = []
        suggestion_i_cmd = []
        for item in suggestion:
            name = item.get("name")
            suggestion_i_pkgs.append(name)
            # if idx_item < len(suggestion) - 1:
            #     suggestion_lines.append(", ")
            for token in item.get("load_cmd").split(" "):
                if token not in suggestion_i_cmd:
                    suggestion_i_cmd.append(token)
        final_load_cmd = " ".join(suggestion_i_cmd)
        final_load_cmd = final_load_cmd.replace("  ", " ")
        suggestions_parsed.append(
            {
                "suggestion_index": idx,
                "release": get_release(suggestion[0]),
                "packages": suggestion_i_pkgs,
                "load_cmd": final_load_cmd,
            }
        )
    return suggestions_parsed


def suggestions(selected, all_modules):
    suggestions = []

    # Find combinations in different releases
    match = find_module_variant_mpackage(selected, all_modules)
    # print( "Different releases match results:", [match_ii.get("load_cmd") for match_i in match for match_ii in match_i])  # Debug print
    if match not in suggestions:
        suggestions += match

    if suggestions == []:
        return dict(
            {
                "success": False,
                "suggestion_count": 0,
                "suggestions_full": [],
                "suggestions_parsed": [],
            }
        )

    # print(f"Total suggestions before cleanup: {len(suggestions)}")  # Debug print
    suggestions = clean_up_suggestion(suggestions, selected)
    # print(f"Total suggestions after cleanup: {len(suggestions)}")  # Debug print
    suggestions_parsed = format_suggestions(suggestions)

    return dict(
        {
            "success": True,
            "suggestion_count": len(suggestions),
            "suggestions_full": suggestions,
            "suggestions_parsed": suggestions_parsed,
        }
    )
