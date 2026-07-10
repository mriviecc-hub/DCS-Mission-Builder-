const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  generateMission: (prompt) => ipcRenderer.invoke("generate-mission", prompt),
  getSettings: () => ipcRenderer.invoke("settings:get"),
  saveSettings: (partial) => ipcRenderer.invoke("settings:save", partial),
  autodetectDcs: () => ipcRenderer.invoke("settings:autodetect-dcs"),
  pickFile: (filters) => ipcRenderer.invoke("dialog:pick-file", filters),
  pickDirectory: () => ipcRenderer.invoke("dialog:pick-directory"),
  showItemInFolder: (filePath) => ipcRenderer.invoke("shell:show-item", filePath),
  backendHealth: () => ipcRenderer.invoke("backend:health"),
});
