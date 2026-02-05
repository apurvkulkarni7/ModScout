import { getUpdateStatus } from "./common.js";

document.addEventListener("DOMContentLoaded", () => {
  const navLinksDiv = document.getElementById("main-nav-grid");
  const gridContainer = document.querySelector(".main-nav-grid");

  getUpdateStatus();
  
  fetch("/module/system_list")
    .then((response) => response.json())
    .then((data) => {
      const systemNames = data.systems;    
      const numColumns = Math.min(systemNames.length,4);
      gridContainer.style.gridTemplateColumns = `repeat(${numColumns}, 1fr)`;

      systemNames.forEach((systemName) => {
        const link = document.createElement("a");
        link.href = `/module?system=${systemName}`;
        link.innerHTML = `🖧<br>${systemName}`;
        const systemCard = document.createElement("div");
        systemCard.className = "system-card";
        systemCard.appendChild(link);
        systemCard.innerHTML += `<div class="arrow"></div>`;
        navLinksDiv.appendChild(systemCard);
      });
    })
    .catch((error) => console.error("Error fetching system names:", error));
});
