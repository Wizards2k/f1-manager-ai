const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const fs = require('fs');

// Python process reference
let pythonProcess = null;
let mainWindow = null;

function commandExists(command) {
    try {
        const whichCmd = process.platform === 'win32' ? 'where' : 'which';
        const result = spawnSync(whichCmd, [command], { stdio: 'ignore' });
        return result.status === 0;
    } catch (error) {
        return false;
    }
}

// Find Python executable
function getPythonExecutable() {
    const customPython = process.env.PYTHON_EXECUTABLE || process.env.PYTHON;
    if (customPython) {
        return customPython;
    }
    
    if (process.platform === 'win32') {
        // Windows - use bundled Python or system Python
        const bundledPython = path.join(process.resourcesPath, 'python', 'python.exe');
        if (fs.existsSync(bundledPython)) {
            return bundledPython;
        }
        if (commandExists('py')) {
            return 'py';
        }
        return 'python'; // Fallback to system Python
    } else {
        // macOS/Linux - use venv Python first, then bundled, then system
        const venvPython = path.join(__dirname, '..', '.venv', 'bin', 'python3');
        if (fs.existsSync(venvPython)) {
            return venvPython;
        }
        const bundledPython = path.join(process.resourcesPath, 'python', 'bin', 'python3');
        if (fs.existsSync(bundledPython)) {
            return bundledPython;
        }
        if (commandExists('python3')) {
            return 'python3';
        }
        return 'python'; // Fallback to python
    }
}

// Get Python backend path
function getBackendPath() {
    const isDev = !app.isPackaged;
    
    if (isDev) {
        return path.join(__dirname, '..');
    } else {
        return path.join(process.resourcesPath, 'python_backend');
    }
}

// Start Python backend
function startPythonBackend() {
    const pythonPath = getPythonExecutable();
    const backendPath = getBackendPath();
    const mainScript = path.join(backendPath, 'python_backend', 'f1_manager_ai.py');
    
    console.log('Starting Python backend...');
    console.log('Python:', pythonPath);
    console.log('Script:', mainScript);
    
    // Set environment variables
    const env = {
        ...process.env,
        PYTHONPATH: backendPath,
        ELECTRON_MODE: 'true',
        FLASK_ENV: 'production'
    };
    
    pythonProcess = spawn(pythonPath, [mainScript], {
        cwd: backendPath,
        env: env,
        stdio: ['ignore', 'pipe', 'pipe']
    });
    
    pythonProcess.stdout.on('data', (data) => {
        console.log(`[Python] ${data.toString().trim()}`);
    });
    
    pythonProcess.stderr.on('data', (data) => {
        console.error(`[Python Error] ${data.toString().trim()}`);
    });
    
    pythonProcess.on('error', (error) => {
        console.error('Failed to start Python:', error);
        dialog.showErrorBox('Error', 'Failed to start game backend. Please check Python installation.');
    });
    
    pythonProcess.on('close', (code) => {
        console.log(`Python process exited with code ${code}`);
        if (code !== 0 && code !== null) {
            console.error('Python backend crashed!');
        }
    });
}

// Stop Python backend
function stopPythonBackend() {
    if (pythonProcess) {
        console.log('Stopping Python backend...');
        
        if (process.platform === 'win32') {
            spawn('taskkill', ['/pid', pythonProcess.pid, '/f', '/t']);
        } else {
            pythonProcess.kill('SIGTERM');
        }
        
        pythonProcess = null;
    }
}

// Create main window
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1920,
        height: 1080,
        minWidth: 1280,
        minHeight: 720,
        title: 'F1 Manager AI',
        icon: path.join(__dirname, '..', 'build', 'icon.png'),
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
            webSecurity: false // Allow loading local files
        },
        show: false, // Don't show until ready
        backgroundColor: '#1a1a1a'
    });
    
    // Remove menu bar in production
    if (app.isPackaged) {
        mainWindow.setMenuBarVisibility(false);
    }
    
    // Load loading screen first
    const isDev = !app.isPackaged;
    mainWindow.loadURL('data:text/html,<html><body style="background:#1a1a1a;color:#e10600;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;font-family:sans-serif;"><div style="text-align:center;"><h1>F1 Manager AI</h1><p>Starting game...</p></div></body></html>');
    
    // Start Python backend
    startPythonBackend();
    
    // Wait 5 seconds then load the app
    setTimeout(() => {
        console.log('Loading game...');
        mainWindow.loadURL('http://localhost:5001');
    }, 5000);
    
    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        if (isDev) {
            mainWindow.webContents.openDevTools();
        }
    });
    
    // Handle window closed
    mainWindow.on('closed', () => {
        mainWindow = null;
    });
    
    // Handle navigation
    mainWindow.webContents.on('will-navigate', (event, url) => {
        // Allow internal navigation
        if (!url.includes('localhost:5001')) {
            event.preventDefault();
            require('electron').shell.openExternal(url);
        }
    });
}

// App event handlers
app.whenReady().then(() => {
    createWindow();
    
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    stopPythonBackend();
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    stopPythonBackend();
});

app.on('quit', () => {
    stopPythonBackend();
});

// IPC handlers
ipcMain.handle('get-app-version', () => {
    return app.getVersion();
});

ipcMain.handle('is-dev-mode', () => {
    return !app.isPackaged;
});
