const els = {
  prompt: document.getElementById("prompt"),
  generateBtn: document.getElementById("generate-btn"),
  generateLoading: document.getElementById("generate-loading"),
  errorBox: document.getElementById("error-box"),
  resultBox: document.getElementById("result-box"),
  resultTitle: document.getElementById("result-title"),
  resultBriefing: document.getElementById("result-briefing"),
  resultGrid: document.getElementById("result-grid"),
  resultPath: document.getElementById("result-path"),
  showInFolderBtn: document.getElementById("show-in-folder-btn"),
  backendStatus: document.getElementById("backend-status"),

  apiKey: document.getElementById("api-key"),
  moosePath: document.getElementById("moose-path"),
  dcsFolder: document.getElementById("dcs-folder"),
  pickMooseBtn: document.getElementById("pick-moose-btn"),
  pickFolderBtn: document.getElementById("pick-folder-btn"),
  autodetectBtn: document.getElementById("autodetect-btn"),
  saveSettingsBtn: document.getElementById("save-settings-btn"),
  settingsSaved: document.getElementById("settings-saved"),
};

let lastSavedPath = null;

function showError(message) {
  els.errorBox.textContent = message;
  els.errorBox.classList.add("show");
  els.resultBox.classList.remove("show");
}

function clearError() {
  els.errorBox.classList.remove("show");
}

function showResult(data) {
  const spec = data.spec;
  els.resultTitle.textContent = spec.title;
  els.resultBriefing.textContent = spec.briefing;

  const fields = [
    ["Mission type", spec.mission_type],
    ["Player aircraft", `${spec.player_aircraft_count}x ${spec.player_aircraft}`],
    ["Home airport", spec.home_airport],
    ["Target area", spec.target_airport],
    ["Time of day", spec.time_of_day],
    ["Weather", spec.weather],
  ];
  if (spec.mission_type === "CAP") {
    fields.push(["Enemy air", `${spec.enemy_air_count}x ${spec.enemy_air_unit}`]);
  } else {
    fields.push(["Target profile", spec.strike_target_profile]);
  }

  els.resultGrid.innerHTML = fields
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");

  lastSavedPath = data.saved_path;
  const parserNote = data.parser_used === "rule_based"
    ? " (parsed offline - no API key configured)"
    : " (parsed by Claude)";
  els.resultPath.textContent = `Saved to: ${data.saved_path}${parserNote}`;
  els.resultBox.classList.add("show");
  clearError();
}

async function generate() {
  const prompt = els.prompt.value.trim();
  if (!prompt) {
    showError("Describe the mission first.");
    return;
  }
  els.generateBtn.disabled = true;
  els.generateLoading.style.display = "inline";
  clearError();
  try {
    const data = await window.api.generateMission(prompt);
    showResult(data);
  } catch (err) {
    showError(err.message || String(err));
  } finally {
    els.generateBtn.disabled = false;
    els.generateLoading.style.display = "none";
  }
}

async function loadSettingsIntoForm() {
  const settings = await window.api.getSettings();
  els.apiKey.value = settings.anthropicApiKey || "";
  els.moosePath.value = settings.moosePath || "";
  els.dcsFolder.value = settings.dcsMissionsFolder || "";
}

async function saveSettingsFromForm() {
  await window.api.saveSettings({
    anthropicApiKey: els.apiKey.value.trim(),
    moosePath: els.moosePath.value.trim(),
    dcsMissionsFolder: els.dcsFolder.value.trim(),
  });
  els.settingsSaved.style.display = "inline";
  setTimeout(() => (els.settingsSaved.style.display = "none"), 1500);
}

async function checkBackend() {
  const ok = await window.api.backendHealth();
  els.backendStatus.textContent = ok ? "backend ready" : "backend not responding";
  if (!ok) {
    setTimeout(checkBackend, 2000);
  }
}

els.generateBtn.addEventListener("click", generate);
els.saveSettingsBtn.addEventListener("click", saveSettingsFromForm);
els.showInFolderBtn.addEventListener("click", () => {
  if (lastSavedPath) window.api.showItemInFolder(lastSavedPath);
});
els.pickMooseBtn.addEventListener("click", async () => {
  const file = await window.api.pickFile([{ name: "Lua script", extensions: ["lua"] }]);
  if (file) els.moosePath.value = file;
});
els.pickFolderBtn.addEventListener("click", async () => {
  const dir = await window.api.pickDirectory();
  if (dir) els.dcsFolder.value = dir;
});
els.autodetectBtn.addEventListener("click", async () => {
  const dir = await window.api.autodetectDcs();
  if (dir) {
    els.dcsFolder.value = dir;
  } else {
    showError("Could not auto-detect a DCS Saved Games folder. Browse to it manually.");
  }
});

loadSettingsIntoForm();
checkBackend();
