document.addEventListener("alpine:init", () => {
  Alpine.data("resolver", () => ({
    tree: {},
    search: "",
    selected: [],

    async init() {
      try {
        const res = await fetch("processed_module_rapids.json");
        this.tree = await res.json();
      } catch (e) {
        console.error("Failed to load module data");
      }
    },

    // Helper: Filter logic
    get searchTerms() {
      return this.search
        .toLowerCase()
        .split(",")
        .map((s) => s.trim())
        .filter((s) => s);
    },

    matchesSearch(name) {
      if (this.searchTerms.length === 0) return true;
      return this.searchTerms.some((term) => name.toLowerCase().includes(term));
    },

    // Visibility Toggles
    releaseVisible(compilers) {
      return Object.values(compilers).some((mods) =>
        this.compilerVisible(mods),
      );
    },

    compilerVisible(modules) {
      return modules.some((m) => this.matchesSearch(m.name));
    },

    // Selection Logic
    toggleModule(mod) {
      const idx = this.selected.findIndex(
        (m) => m.name === mod.name && m.compiler === mod.compiler,
      );
      idx > -1 ? this.selected.splice(idx, 1) : this.selected.push(mod);
    },

    isSelected(mod) {
      return this.selected.some(
        (m) => m.name === mod.name && m.compiler === mod.compiler,
      );
    },

    get hasConflict() {
      if (this.selected.length < 2) return false;

      // Extract the primary compiler (e.g., 'GCC/13.2.0') from the release string
      const getRootCompiler = (m) => m.compiler.split(" ")[0];

      const root = getRootCompiler(this.selected[0]);
      return this.selected.some((m) => getRootCompiler(m) !== root);
    },

    get combinedLoadCmd() {
      if (this.selected.length === 0) return "";
      const { release, compiler } = this.selected[0];
      const names = this.selected.map((m) => m.name).join(" ");
      return `module load ${release} ${compiler} ${names}`;
    },

    copyCommand() {
      navigator.clipboard.writeText(this.combinedLoadCmd);
      alert("Command copied to clipboard!");
    },
  }));
});
