const { app, BrowserWindow } = require('electron');

function createWindow() {
  const win = new BrowserWindow({
    width: 1920,
    height: 1080,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    hasShadow: false,
    fullscreenable: false,
    resizable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  win.loadFile('index.html');
  

  win.once('ready-to-show', () => {
  win.setIgnoreMouseEvents(true, { forward: true });
});
}

app.whenReady().then(createWindow);