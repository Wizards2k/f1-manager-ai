const { spawn } = require('child_process');
const path = require('path');

function getElectronBinary() {
    try {
        return require('electron');
    } catch (error) {
        console.error('Electron non è installato. Esegui `npm install` prima di `npm run dev`.');
        process.exit(1);
    }
}

const electronBinary = getElectronBinary();
const projectRoot = path.resolve(__dirname, '..');

const fs = require('fs');

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;

env.PYTHONPATH = env.PYTHONPATH
    ? `${env.PYTHONPATH}${path.delimiter}${projectRoot}${path.delimiter}${path.join(projectRoot, 'python_backend')}`
    : `${projectRoot}${path.delimiter}${path.join(projectRoot, 'python_backend')}`;

// Use venv Python if available
const venvPython = path.join(projectRoot, '.venv', 'bin', 'python3');
if (fs.existsSync(venvPython)) {
    env.PYTHON_EXECUTABLE = venvPython;
    env.VIRTUAL_ENV = path.join(projectRoot, '.venv');
    env.PATH = path.join(projectRoot, '.venv', 'bin') + path.delimiter + (env.PATH || '');
}

const child = spawn(electronBinary, ['.'], {
    cwd: projectRoot,
    env,
    stdio: 'inherit'
});

child.on('close', (code) => {
    process.exit(code);
});

child.on('error', (error) => {
    console.error('Errore nell’avvio di Electron:', error);
    process.exit(1);
});
