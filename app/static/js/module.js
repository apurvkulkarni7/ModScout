import { fetchJson } from "./common.js";

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
  const conflictSuggestions = document.getElementById("conflictSuggestions");
  const errorModuleSelection = document.getElementById(
    "errorMsgModuleSelection",
  );
  const outputArea = document.getElementById("outputArea");
  const commandText = document.getElementById("commandText");
  const clearSelectionBtn = document.getElementById("clearSelectionBtn");

  //////////////////////////////////////////////////////////////////////////////
  //  Helper functions
  //////////////////////////////////////////////////////////////////////////////

  // Initialization function to load module data and render the page
  async function init() {
    const urlParams = new URLSearchParams(window.location.search);
    const systemName = urlParams.get("system") || "processed_module_rapids"; // Default fallback

    fetchJson(`/module/data?system=${systemName}`)
      .then((data) => {
        if (data.error) {
          throw new Error(data.error);
        }
        state.tree = data;
        document.title += `: ${systemName.replace(/_/g, " ").toUpperCase()}`;
        render();
      })
      .catch((e) => {
        console.error(
          `Failed to load module data for system: ${systemName}`,
          e,
        );
        document.getElementById("resultsArea").innerHTML = `
              <div class="empty-state">Error: Could not load the software stack file for "${systemName}".</div>
          `;
      });

    renderNavBar();
  }

  // for renduring everything
  function render() {
    renderResults();
    renderSelection();
  }

  function isSelected(mod) {
    return state.selected.some(
      (m) =>
        m.name === mod.name &&
        m.compiler === mod.compiler &&
        m.release === mod.release,
    );
  }

  async function hasConflict(selectedModules, system) {
    const data = await fetchJson("/module/conflict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected: selectedModules, system: system }),
    });

    return data;
  }

  // Building suggestion message upon conflict
  function buildSuggestionsMessage(suggestions_parsed) {
    const total = suggestions_parsed.length;

    // Group items by `release`
    const byRelease = suggestions_parsed.reduce((acc, rec) => {
      const rel = rec.release || "Unknown Release";
      if (!acc[rel]) acc[rel] = [];
      acc[rel].push({ ...rec });
      return acc;
    }, {});

    let msg = `<div> Found ${total} suggestions:</div>`;
    let globalIdx = 1;
    for (const [release, items] of Object.entries(byRelease)) {
      msg += `<div><strong>${release}</strong>:</div>`;
      items.forEach((item) => {
        // msg += `<div>${globalIdx}) ${item.packages.join(', ')}</div>`;
        msg += `<div class="pkg-item" 
                   data-pkg="${item.load_cmd}" 
                   style="cursor: pointer;margin: 5px 0;" 
                   title="Click to copy loading command:\n${item.load_cmd}">
                   ${globalIdx}) ${item.packages.join(", ")}
              </div>`;
        globalIdx++;
      });
      msg += "<br>";
    }
    return msg;
  }

  function toggleModule(mod) {
    const idx = state.selected.findIndex(
      (m) =>
        m.name === mod.name &&
        m.compiler === mod.compiler &&
        m.release === mod.release,
    );

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

  // Logic to handle suggestion selection and copying command to clipboard
  function initSuggestionSelection(event) {
    const target = event.target.closest(".pkg-item");
    if (target) {
      const cmdToCopy = target.getAttribute("data-pkg");
      if (cmdToCopy) {
        navigator.clipboard
          .writeText(cmdToCopy)
          .then(() => {
            console.log("Copied to clipboard:", cmdToCopy);

            // Visual feedback
            alert(`Copied loading command to clipboard:\n${cmdToCopy}`);
            const originalBg = target.style.backgroundColor;
            target.style.backgroundColor = "#9df3b1";
            setTimeout(() => {
              target.style.backgroundColor = originalBg;
            }, 1000);
          })
          .catch((err) => {
            console.error("Failed to copy text: ", err);
          });
      }
    }
  }

  //////////////////////////////////////////////////////////////////////////////
  // Rendering Logics
  //////////////////////////////////////////////////////////////////////////////
  // Navigation bar
  function renderNavBar() {
    fetchJson("/module/system_list")
      .then((data) => {
        const systemNames = data.systems;
        const navLinksDiv = document.getElementById("global-nav");
        systemNames.forEach((systemName) => {
          const link = document.createElement("a");
          link.href = `/module?system=${systemName}`;
          link.textContent = systemName;
          const div = document.createElement("div");
          div.className = "nav-links";
          div.appendChild(link);
          navLinksDiv.appendChild(div);
        });
      })
      .then(() => {
        const urlParams = new URLSearchParams(window.location.search);
        const currentSystem = urlParams.get("system");
        document.querySelectorAll(".nav-links a").forEach((link) => {
          if (link.href.includes(`system=${currentSystem}`)) {
            link.classList.add("active");
            console.log("Current system:", currentSystem);
          } else {
            link.classList.remove("active");
          }
        });
      })
      .catch((error) => console.error("Error fetching system names:", error));
  }

  // Rendering search results
  function renderResults() {
    const query = state.search;
    const urlParams = new URLSearchParams(window.location.search);
    const systemName = urlParams.get("system");
    fetchJson(`/module/search?system=${systemName}&query=${query}`).then(
      (data) => {
        resultsArea.innerHTML = "";
        const sortedReleases_key = Object.keys(data).sort().reverse();
        const sortedReleases = sortedReleases_key.map((key) => [
          key,
          data[key],
        ]);

        sortedReleases.forEach((release_item) => {
          const release = release_item[0];
          const compiler = release_item[1];

          const section = document.createElement("section");
          section.className = "release-group";
          section.innerHTML = `<h2>${release}</h2>`;
          // section.innerHTML = `<summary style="cursor: pointer; font-weight: bold;"><h2>${release}</h2></summary>`;

          const sortedCompilers_key = Object.keys(compiler).sort((a, b) => {
            if (a.toLowerCase() === "none" || a.trim() === "") return -1;
            if (b.toLowerCase() === "none" || b.trim() === "") return 1;
            return a.localeCompare(b);
          });
          const sortedCompilerEntries = sortedCompilers_key.map((key) => [
            key,
            compiler[key],
          ]);

          sortedCompilerEntries.forEach((compiler_item) => {
            let compiler = compiler_item[0];
            let modules = compiler_item[1];
            
            

            if (!compiler.toUpperCase().endsWith("_EXT")) {
              if (compiler.toLowerCase() === "none" || compiler.trim() === "") {
                compiler = "Standalone";
              }

              const group = document.createElement("div");
              group.className = "compiler-group";
              group.innerHTML = `<h3>${compiler}</h3>`;

              const grid = document.createElement("div");
              grid.className = "module-grid";
              modules.forEach((mod) => {
                const btn = document.createElement("button");
                btn.className = `module-card ${isSelected(mod) ? "selected" : ""}`;
                btn.innerHTML = `<span class="pkg-name">${mod.package}</span><span class="pkg-ver">${mod.version}</span>`;
                btn.onclick = () => toggleModule(mod);
                grid.appendChild(btn);
              });

              group.appendChild(grid);
              section.appendChild(group);
            } else if (compiler.toUpperCase().endsWith("_EXT")) {
              compiler = compiler.replace("_EXT","").replace("_Ext","")
              const group = document.createElement("div");
              group.className = "compiler-group";
              group.innerHTML = `<h3>Extenstions - ${compiler}</h3>`;

              const grid = document.createElement("div");
              grid.className = "module-grid";
              modules.forEach((mod) => {
                const btn = document.createElement("button");
                btn.className = `module-card extension ${isSelected(mod) ? "selected" : ""}`;
                btn.innerHTML = `
                <span class="pkg-name">${mod.package} <span class="floating-alpha">(E)</span></span>
                <span class="pkg-ver">${mod.version}</span>
                `;
                btn.onclick = () => toggleModule(mod);
                grid.appendChild(btn);
              });

              group.appendChild(grid);
              section.appendChild(group);
              
            }


          });
          // section.innerHTML = `<details ${true ? 'open' : ''}>${section.innerHTML}</details>`;
          resultsArea.appendChild(section);
        });
      },
    );
  }

  // Rendering selected modules and conflict status
  async function renderSelection() {
    const system = new URLSearchParams(window.location.search).get("system");
    selectionList.innerHTML = "";

    if (state.selected.length === 0) {
      selectionList.innerHTML =
        '<div class="empty-state">Select modules to build command</div>';
      conflictAlert.style.display = "none";
      conflictSuggestions.style.display = "none";
      outputArea.style.display = "none";
      return;
    }

    state.selected.forEach((mod) => {
      const item = document.createElement("div");
      item.className = "selected-item";
      const compiler =
        mod.compiler === "" ? mod.release : `${mod.release} ${mod.compiler}`;
      if (mod.is_extension === false) {
        item.innerHTML = `
                <div style="align-items: left;">
                    <div class="item-name">${mod.package}/${mod.version}</div>
                    <div class="item-compiler">${compiler}</div>
                    <div style="direction: rtl; padding: 0.5rem; max-height: 100px; overflow-y: scroll;">
                      <div class="item-description">${mod.description || ""}</div>
                    </div>
                </div>
                <button class="remove-btn">✕</button>
            `;
      } else if (mod.is_extension === true) {
        item.innerHTML = `
                <div style="align-items: left;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                      <div class="item-name">${mod.package}/${mod.version}</div>
                      <div class="item-compiler" style="color: #666;"> (Extension) </div>
                    </div>
                    <div class="item-compiler">${compiler.slice(0,-4)}</div>
                    <div style="direction: rtl; padding: 0.5rem; max-height: 50px; overflow-y: scroll;">
                      <div class="item-description">${mod.description || ""}</div>
                    </div>
                </div>
                <button class="remove-btn">✕</button>
            `;
      }
      item.querySelector(".remove-btn").onclick = () => toggleModule(mod);
      selectionList.appendChild(item);
    });

    const {
      conflict: conflict,
      msg: conflict_msg,
      suggestions: suggestions,
    } = await hasConflict(state.selected, system);
    conflictAlert.style.display = conflict ? "block" : "none";
    errorModuleSelection.innerText = conflict_msg;
    conflictSuggestions.style.display = conflict ? "block" : "none";
    if (conflict) {
      const suggestions_msg = buildSuggestionsMessage(
        suggestions.suggestions_parsed,
      );
      conflictSuggestions.innerHTML = suggestions_msg;
    }
    outputArea.style.display =
      !conflict && state.selected.length > 0 ? "block" : "none";

    if (!conflict && state.selected.length > 0) {
      let { release, compiler } = state.selected[0];

      const names = state.selected
        .map((m) => {
          if (m.is_extension == false) {
            return m.name;
          }
        })
        .join(" ");
      
      if (compiler.toUpperCase().endsWith("_EXT")) {
        compiler = compiler.replace("_Ext", "");
        compiler = compiler.replace("_EXT", "");
      }
      commandText.textContent = `module load ${release} ${compiler} ${names}`;
    }
  }

  //////////////////////////////////////////////////////////////////////////////
  // Event Listeners
  //////////////////////////////////////////////////////////////////////////////

  // Render results for each typed character with a debounce (delay) to improve
  // performance by reducing requests while typing.
  let searchTimeout;
  searchInput.addEventListener("input", (e) => {
    clearTimeout(searchTimeout);
    state.search = e.target.value.trim();
    searchTimeout = setTimeout(() => {
      render();
    }, 300);
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

  document.addEventListener("click", initSuggestionSelection);

  clearSelectionBtn.addEventListener("click", clearAllSelections);

  init();
});
