// Electron 主程序
const { app, BrowserWindow, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let apiProcess;

// 開發模式判斷
const isDev = !app.isPackaged;
const VITE_DEV_URL = 'http://localhost:5173';

function startApiServer() {
  // 啟動 FastAPI 後端（python api_server.py）
  const apiPath = isDev
    ? path.join(__dirname, '..', '..', 'api_server.py')
    : path.join(process.resourcesPath, 'api_server.py');

  apiProcess = spawn('python', [apiPath], {
    cwd: path.dirname(apiPath),
    stdio: 'pipe',
  });

  apiProcess.stdout.on('data', (data) => {
    console.log(`[API] ${data}`);
  });

  apiProcess.stderr.on('data', (data) => {
    console.error(`[API] ${data}`);
  });

  apiProcess.on('close', (code) => {
    console.log(`[API] exited with code ${code}`);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'KG 成本管理系統',
    icon: path.join(__dirname, '..', 'public', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  if (isDev) {
    mainWindow.loadURL(VITE_DEV_URL);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  // 外部連結用系統瀏覽器開啟
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  startApiServer();
  // 等 API 啟動
  setTimeout(createWindow, 1500);
});

app.on('window-all-closed', () => {
  if (apiProcess) apiProcess.kill();
  app.quit();
});

app.on('before-quit', () => {
  if (apiProcess) apiProcess.kill();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
