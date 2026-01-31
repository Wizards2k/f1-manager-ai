const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
    // App info
    getAppVersion: () => ipcRenderer.invoke('get-app-version'),
    isDevMode: () => ipcRenderer.invoke('is-dev-mode'),
    
    // Platform info
    platform: process.platform,
    
    // Check if running in Electron
    isElectron: true
});

// Log that preload script has loaded
console.log('[Electron] Preload script loaded successfully');
