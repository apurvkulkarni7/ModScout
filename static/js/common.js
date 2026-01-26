function updateModuleData() {
  fetch(`/update`)
    .then((res) => res.json())
    .then((data) => {
      alert(data.message);
    })
    .catch((e) => {
      console.error(`Failed to update module data`, e);
    });
}

async function getUpdateStatus() {
  let statusDisplay = document.getElementById("status-display");
  let statusMessage = "Update Status: ";
  try {
    const response = await fetch("/status");
    const result = await response.json();
    const status = result.status;
    const last_run = result.last_run;
    document.getElementById("status-display").innerText = "";
    if (status === "running") {
      const runningStatus = document.createElement("span");
      runningStatus.classList.add("status-running");
      runningStatus.innerText = statusMessage + "Running";
      statusDisplay.appendChild(runningStatus);
      // document.getElementById("update-btn").disabled = true;
    } else if (status === "completed") {
      // const completedStatus = document.createElement("span");
      // completedStatus.classList.add("status-completed");
      // completedStatus.innerText = statusMessage + "Completed";
      // statusDisplay.appendChild(completedStatus);

      const lastRun = document.createElement("div");
      lastRun.classList.add("last-run");
      lastRun.innerText = "Last updated: " + last_run;
      statusDisplay.appendChild(lastRun);
      // document.getElementById("update-btn").disabled = false;
    } else {
      // const failedStatus = document.createElement("span");
      // failedStatus.classList.add("status-failed");
      // failedStatus.innerText = statusMessage + "Failed";
      // statusDisplay.appendChild(failedStatus);
      document.getElementById("update-btn").disabled = false;
    }
  } catch (error) {
    console.error("Error fetching status:", error);
  }
}

setInterval(getUpdateStatus, 5000);
