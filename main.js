document.addEventListener("DOMContentLoaded", () => {
  const state = {
    tree: {},
    search: "",
    selected: [],
  };

  // DOM Elements
  const searchInput = document.getElementById("searchInput");
  const clearBtn = document.getElementById("clearBtn");
  const resultsArea = document.getElementById("resultsArea");
  const selectionList = document.getElementById("selectionList");
  const conflictAlert = document.getElementById("conflictAlert");
  const outputArea = document.getElementById("outputArea");
  const commandText = document.getElementById("commandText");
  const clearSelectionBtn = document.getElementById("clearSelectionBtn");

  async function init() {
    const urlParams = new URLSearchParams(window.location.search);
    const systemName = urlParams.get("system") || "processed_module_rapids"; // Default fallback

    const environMap = {
      barnard: "rapids",
      romeo: "romeo",
      alpha: "romeo",
      capella: "genoa",
    };

    updateNav()

    let environName = environMap[systemName] || "rapids";
    const jsonFile = `data/processed_module_${environName}.json`;

    try {
      const res = await fetch(jsonFile);
      if (!res.ok) throw new Error("File not found");

      state.tree = await res.json();

      document.title = `${systemName.replace(/_/g, " ").toUpperCase()} Module Browser`;

      render();
    } catch (e) {
      console.error(`Failed to load: ${jsonFile}`, e);
      document.getElementById("resultsArea").innerHTML = `
            <div class="empty-state">Error: Could not load the software stack for "${systemName}" (${jsonFile}).</div>
        `;
    }
  }

  //  Logic Helpers 
  function render() {
    renderResults();
    renderSelection();
  }

  function getSearchTerms() {
    return state.search
      .toLowerCase()
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s);
  }

  function matchesSearch(mod) {
    const terms = getSearchTerms();
    if (terms.length === 0) return true;

    const name = (mod.name || "").toLowerCase();
    const description = (mod.description || "").toLowerCase();

    return terms.some(
      (term) => name.includes(term) || description.includes(term),
    );
  }

  function isSelected(mod) {
    return state.selected.some(
      (m) => m.name === mod.name && m.compiler === mod.compiler && m.release === mod.release,
    );
  }

  function hasConflict() {
    if (state.selected.length < 2) return false;
    const getRootCompiler = (m) => m.compiler.split(" ")[0];
    const getRelease = (m) => m.release.split(" ")[0];

    const differentRelease = state.selected.some((m) => getRelease(m) !== getRelease(state.selected[0]));
    console.debug("Checking if any selected module has a different release:", differentRelease);
    if (differentRelease) {
      console.debug("Selected modules have different releases. Conflict detected.");
      return true;
    }
    
    const pkgsWithCompiler = state.selected.filter((m) => getRootCompiler(m) !== "");
    if (pkgsWithCompiler.length === 0) {
      console.debug("All selected modules have 'None' dependency. No conflict.");
      return false;
    } else if (pkgsWithCompiler.length === 1) {
      console.debug("Only one selected module has a specific compiler. No conflict in dependency.");
      return false;
    } else {
      console.debug("Multiple selected modules have specific compilers. Checking for conflicts in dependency.");
      var rootSubsetCompiler = getRootCompiler(pkgsWithCompiler[0]);
      const differentCompiler = pkgsWithCompiler.some((m) => getRootCompiler(m) && getRootCompiler(m) !== rootSubsetCompiler);
      return differentCompiler;
    }
  }

  // Actions

  function toggleModule(mod) { 
    const idx = state.selected.findIndex(
      (m) => m.name === mod.name && m.compiler === mod.compiler && m.release === mod.release,
    );

    console.debug("Toggling module:", mod, "Index in selected:", idx);

    if (idx > -1) {
      state.selected.splice(idx, 1);
    } else {
      state.selected.push(mod);
    }
    render();
  }

  function clearAllSelections() {
    state.selected = [];
    render();
  }

  // Rendering Logic

  function renderResults() {
    resultsArea.innerHTML = "";

    Object.entries(state.tree).forEach(([release, compilers]) => {
      // Updated to pass the full module object to the match function
      const filteredCompilers = Object.entries(compilers).filter(
        ([compiler, modules]) => {
          return modules.some((m) => matchesSearch(m));
        },
      );

      if (filteredCompilers.length === 0) return;

      const section = document.createElement("section");
      section.className = "release-group";
      section.innerHTML = `<h2>${release}</h2>`;

      filteredCompilers.sort((a, b) =>
        a[0] === "None" ? -1 : b[0] === "None" ? 1 : a[0].localeCompare(b[0]),
      );

      filteredCompilers.forEach(([compiler, modules]) => {
        const group = document.createElement("div");
        group.className = "compiler-group";
        group.innerHTML = `<h3>${compiler}</h3>`;

        const grid = document.createElement("div");
        grid.className = "module-grid";

        modules.sort((a, b) => a.package.localeCompare(b.package));

        modules.forEach((mod) => {
          if (!matchesSearch(mod)) return;
          const btn = document.createElement("button");
          btn.className = `module-card ${isSelected(mod) ? "selected" : ""}`;
          btn.innerHTML = `<span class="pkg-name">${mod.package}</span><span class="pkg-ver">${mod.version}</span>`;
          btn.onclick = () => toggleModule(mod);
          grid.appendChild(btn);
        });

        group.appendChild(grid);
        section.appendChild(group);
      });
      resultsArea.appendChild(section);
    });
  }

  function renderSelection() {
    selectionList.innerHTML = "";

    if (state.selected.length === 0) {
      selectionList.innerHTML =
        '<div class="empty-state">Select modules to build command</div>';
      conflictAlert.style.display = "none";
      outputArea.style.display = "none";
      return;
    }
    console.log("Selected modules:", state.selected);

    state.selected.forEach((mod) => {
      const item = document.createElement("div");
      item.className = "selected-item";
      const meta =
        mod.compiler === ""
          ? mod.release
          : `${mod.release} ${mod.compiler}`;
      item.innerHTML = `
                <div style="align-items: left;">
                    <div class="item-name">${mod.package}/${mod.version}</div>
                    <div class="item-meta">${meta}</div>
                    <div class="item-description">${mod.description || ""}</div>
                    <a class="item-description" href="${mod.url || ""}">${mod.url || ""}</a>
                </div>
                <button class="remove-btn">✕</button>
            `;
      item.querySelector(".remove-btn").onclick = () => toggleModule(mod);
      selectionList.appendChild(item);
    });

    const conflict = hasConflict();
    conflictAlert.style.display = conflict ? "block" : "none";
    outputArea.style.display =
      !conflict && state.selected.length > 0 ? "block" : "none";

    if (!conflict && state.selected.length > 0) {
      const { release, compiler } = state.selected[0];
      const names = state.selected.map((m) => m.name).join(" ");
      commandText.textContent = `module load ${release} ${compiler} ${names}`;
    }
  }

  function updateNav() {
    const urlParams = new URLSearchParams(window.location.search);
    const currentSystem = urlParams.get("system");

    document.querySelectorAll(".nav-links a").forEach((link) => {
      if (link.href.includes(`system=${currentSystem}`)) {
        link.classList.add("active");
      } else {
        link.classList.remove("active");
      }
    });
  }

  // Event Listeners 
  searchInput.addEventListener("input", (e) => {
    state.search = e.target.value;
    render();
  });

  clearBtn.addEventListener("click", () => {
    state.search = "";
    searchInput.value = "";
    render();
  });

  document.getElementById("copyCmdBox").addEventListener("click", () => {
    navigator.clipboard.writeText(commandText.textContent);
    alert("Command copied to clipboard!");
  });

  clearSelectionBtn.addEventListener("click", clearAllSelections);

  init();
});
