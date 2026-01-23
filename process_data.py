import json

# json_data = json.load(open('module_rapids.json'))#[:10]
# with open('subset_lmod.json', 'w') as file:
#     json.dump(json_data, file)

with open('data/module_rapids.json', 'r') as f:
    raw_data = json.load(f)

tree = {}
for entry in raw_data:
    package = entry['package']
    # if str(package).lower() != "vtk":
    #     continue
    description = entry.get('description', 'No description available.')
    for version in entry['versions']:
        v_name = version['versionName']
        full_name = f"{package}/{v_name}"
        for parent_set in version.get('parent', []):
            release = parent_set[0] if len(parent_set) > 0 else "Core"
            # compiler = parent_set[1] if len(parent_set) > 1 else "Direct"
            compiler = " ".join(parent_set[1:]) if len(parent_set) > 1 else "None"

            if release not in tree: tree[release] = {}
            if compiler not in tree[release]: tree[release][compiler] = []
            
            tree[release][compiler].append({
                "package": package,      # Separated package
                "version": v_name,       # Separated version
                "name": full_name,       # Full string for search
                "description": description,
                "release": release,
                "compiler": compiler.replace('None', ''),
                "load_cmd": f"module load {release} {compiler.replace('None', '')} {full_name}"
            })

with open('processed_module_rapids.json', 'w') as f:
    json.dump(tree, f, indent=4)