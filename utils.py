import json
from dotenv import load_dotenv
import schedule
import re
import pprint
from itertools import combinations, product

# import itertools


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

    with open("selected.json", "w") as f:
        json.dump(selected, f, indent=2)

    # For different release
    for m_i, m_ii in combinations(selected, 2):
        if get_release(m_i) != get_release(m_ii):
            print("Releases differ among selected modules.")
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

    pkgs_with_compiler = [set(l.get("compiler").split(" ")) for l in selected if l if get_compiler(l) != ""]
    
    if len(pkgs_with_compiler) < 2:
        return False, ""
    
    for i in range(len(pkgs_with_compiler) - 1):
        current_set = pkgs_with_compiler[i]
        
        next_set = pkgs_with_compiler[i+1]
            
        is_subset = current_set.issubset(next_set) or next_set == set([''])
        is_superset = current_set.issuperset(next_set) or next_set == set([''])
        
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


# def find_module_variant_mpackage_mrelease_mcompiler(
#     selected, anchor, all_modules_flattened
# ):
#     selected_name = get_package(selected)
#     selected_ver = get_version(selected)
#     anchor_release = get_release(anchor)
#     anchor_compiler = get_compiler(anchor)

#     mrelease_mcompiler_mpackage_mver = []  # m stands for matching
#     mrelease_mcompiler_mpackage_nmver = []  # nm stands for not matching

#     # Matching release and compiler
#     for module in all_modules_flattened:
#         if (
#             selected_name == get_package(module)
#             and anchor_release == get_release(module)
#             and anchor_compiler == get_compiler(module)
#         ):
#             if selected_ver == get_version(module):
#                 mrelease_mcompiler_mpackage_mver.append([anchor, module])
#             else:
#                 mrelease_mcompiler_mpackage_nmver.append([anchor, module])
#     return mrelease_mcompiler_mpackage_mver + mrelease_mcompiler_mpackage_nmver


# def find_module_variant_mpackage_mrelease(selected, anchor, all_modules):
#     anchor_name = get_package(anchor)
#     selected_name = get_package(selected)
#     mrelease_mpackage_mrelease = []

#     for release_i in all_modules.keys():
#         for compiler_i in all_modules[release_i].keys():
#             same_compiler_suggestion = []
#             for module_i in all_modules[release_i][compiler_i]:
#                 module_i_name = get_package(module_i)
#                 if selected_name == module_i_name or anchor_name == module_i_name:
#                     same_compiler_suggestion.append(module_i)
#             if len(same_compiler_suggestion) > 1:
#                 mrelease_mpackage_mrelease.append(same_compiler_suggestion)
#     return mrelease_mpackage_mrelease


def find_module_variant_mpackage(selected, all_modules):
    mpackage = []

    # Extract just the package names we are looking for (e.g., 'gcc', 'llvm')
    required_pkg_names = [get_package(s) for s in selected]
    # print(f"Required package names: {required_pkg_names}")  # Debug print

    for release_i in all_modules:
        for compiler_i in all_modules[release_i]:
            # print(f"Checking release: {release_i}, compiler: {compiler_i}")  # Debug print

            modules_in_bucket = all_modules[release_i][compiler_i]
            modules_in_bucket += all_modules[release_i]["None"] # Include 'None' compiler modules from same release
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
    
    mpackage.sort(reverse=True, key=lambda x: [get_release(m) for m in x]) # Sort by release in descending order
    
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
        final_load_cmd =" ".join(suggestion_i_cmd)
        final_load_cmd = final_load_cmd.replace("  ", " ")
        suggestions_parsed.append({
            "suggestion_index": idx,
            "release": get_release(suggestion[0]),
            "packages": suggestion_i_pkgs,
            "load_cmd": final_load_cmd,
        })
        # finalize this suggestion's block
        # suggestion_lines.append(f"\n")
        # suggestions_cmd.append(" ".join(cmd_tokens))

    # combine all lines into the final string
    # suggestion_str = "".join(suggestion_lines)

    return suggestions_parsed


def recommendations(selected, all_modules):
    suggestions = []

    # Flatten the module database once
    # all_modules_flattened = [
    #     pkgs
    #     for releases in all_modules
    #     for compilers in all_modules[releases]
    #     for pkgs in all_modules[releases][compilers]
    # ]



    # for anchor in selected:
    #     anchor_name = get_package(anchor)
    #     anchor_ver = get_version(anchor)

    #     for pkg in selected:
    #         pkg_name = get_package(pkg)
    #         pkg_ver = get_version(pkg)
    #         if pkg_name == anchor_name and pkg_ver == anchor_ver:
    #             continue

    #         # Try strict match (Release + Compiler)
    #         match = find_module_variant_mpackage_mrelease_mcompiler(
    #             pkg, anchor, all_modules_flattened
    #         )
    #         # print( "Strict match (Release + Compiler) results:", [match_ii.get("load_cmd") for match_i in match for match_ii in match_i])  # Debug print
    #         if match not in suggestions:
    #             suggestions += match

    #         # Fallback to just Release
    #         match = find_module_variant_mpackage_mrelease(pkg, anchor, all_modules)
    #         # print( "Fallback match (Release) results:", [match_ii.get("load_cmd") for match_i in match for match_ii in match_i])  # Debug print
    #         if match not in suggestions:
    #             suggestions += match

    # Find combinations in different releases
    match = find_module_variant_mpackage(selected, all_modules)
    # print( "Different releases match results:", [match_ii.get("load_cmd") for match_i in match for match_ii in match_i])  # Debug print
    if match not in suggestions:
        suggestions += match

    if suggestions == []:
        return dict({
            "success": False,
            "suggestion_count": 0,
            "suggestions_full": [],
            "suggestions_parsed": []
            })

    # print(f"Total suggestions before cleanup: {len(suggestions)}")  # Debug print
    suggestions = clean_up_suggestion(suggestions, selected)
    # print(f"Total suggestions after cleanup: {len(suggestions)}")  # Debug print
    suggestions_parsed = format_suggestions(suggestions)

    return dict(
        {
            "success": True,
            "suggestion_count": len(suggestions),
            # "message": f"Found {len(suggestions)} recommendations:\n{suggestion_str}",
            "suggestions_full": suggestions,
            "suggestions_parsed": suggestions_parsed
        }
    )
