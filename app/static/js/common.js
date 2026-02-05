
// Updating modules database
export function updateModuleData() {
  fetch(`/update`)
    .then((res) => res.json())
    .then((data) => {
      alert(data.message);
    })
    .catch((e) => {
      console.error(`Failed to update module data`, e);
    });
}

// Fetching update Job Status
export async function getUpdateStatus() {
  let statusDisplay = document.getElementById("status-display");
  let statusMessage = "Update Status: ";
  try {
    // const response = await fetch("/status");
    // const result = await response.json();
    const result = await fetchJson("/status");

    const status = result.status;
    const last_run = result.last_run;
    document.getElementById("status-display").innerText = "";
    if (status === "running") {
      const runningStatus = document.createElement("span");
      runningStatus.classList.add("status-running");
      runningStatus.innerText = statusMessage + "Running";
      statusDisplay.appendChild(runningStatus);
    } else if (status === "completed") {
      const lastRun = document.createElement("div");
      lastRun.classList.add("last-run");
      lastRun.innerText = "Last updated: " + last_run;
      statusDisplay.appendChild(lastRun);
    } else {
      document.getElementById("update-btn").disabled = false;
    }
  } catch (error) {
    console.error("Error fetching status:", error);
  }
}

// Helper function to fetch JSON with error handling
export async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const err = await response.text();
    throw new Error(`Request failed: ${response.status}\n${err}`);
  }
  return response.json();
}