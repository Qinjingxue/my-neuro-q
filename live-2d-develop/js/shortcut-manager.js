const { globalShortcut, BrowserWindow, app } = require('electron');

/**
 * 全局快捷键管理器
 * 统一管理应用的所有全局快捷键
 */
class ShortcutManager {
    constructor() {
        this.shortcuts = [];
    }

    /**
     * 注册所有快捷键
     */
    registerAll() {
        this._registerAppControls();
        this._registerTTSInterrupt();
        this._registerWindowVisibilityToggle(); 
        this._registerWindowTopMost();
        this._registerChatFocus();
        this._registerMotionAndMusicControls();
        this._registerSubtitleToggle(); 
        this._registerASRToggle();

        console.log(`已注册 ${this.shortcuts.length} 个全局快捷键`);
    }

    _registerAppControls() {
        this._register('CommandOrControl+Q', () => app.quit(), '退出应用');
    }

    _registerTTSInterrupt() {
        this._register('CommandOrControl+G', () => {
            BrowserWindow.getAllWindows()[0]?.webContents.send('interrupt-tts');
        }, '打断 TTS 语音');
    }

    _registerWindowTopMost() {
        this._register('Alt+3', () => {
            BrowserWindow.getAllWindows().forEach(win => win.setAlwaysOnTop(true, 'screen-saver'));
        }, '强制窗口置顶');
    }

    // --- 核心修改：重命名并重写了此方法 ---
    _registerWindowVisibilityToggle() {
        this._register('Alt+2', () => {
            const win = BrowserWindow.getAllWindows()[0];
            if (win) {
                if (win.isVisible()) {
                    // 1. 如果当前可见，则隐藏窗口
                    win.hide();
                    // 2. 发送信号停止渲染，节省资源
                    win.webContents.send('renderer-stop');
                } else {
                    // 1. 如果当前隐藏，则显示窗口
                    win.show();
                    // 2. 强制设为最顶层
                    win.setAlwaysOnTop(true, 'screen-saver');
                    // 3. 发送信号恢复渲染
                    win.webContents.send('renderer-start');
                }
            }
        }, '显示/隐藏桌宠 (节省性能)');
    }

    _registerChatFocus() {
        this._register('Alt+W', () => {
            const mainWindow = BrowserWindow.getAllWindows()[0];
            if (mainWindow) {
                mainWindow.show();
                mainWindow.focus();
                mainWindow.webContents.send('toggle-chat-focus');
            }
        }, '切换焦点到聊天框');
    }

    _registerASRToggle() {
        this._register('Alt+1', () => {
            BrowserWindow.getAllWindows()[0]?.webContents.send('toggle-asr');
        }, '切换 ASR 语音识别');
    }
    
    // --- 核心修改：新增方法 ---
    _registerSubtitleToggle() {
        this._register('Alt+0', () => {
             BrowserWindow.getAllWindows()[0]?.webContents.send('toggle-subtitle-visibility');
        }, '显示/隐藏字幕组件');
    }

    _registerMotionAndMusicControls() {
        for (let i = 1; i <= 9; i++) {
            const action = () => {
                const mainWindow = BrowserWindow.getAllWindows()[0];
                if (!mainWindow) return;
                if (i === 6) {
                    mainWindow.webContents.send('trigger-music-play');
                } else if (i === 8) {
                    mainWindow.webContents.send('trigger-music-stop-with-motion');
                } else {
                    mainWindow.webContents.send('trigger-motion-hotkey', i - 1);
                }
            };
            const desc = i === 6 ? '播放随机音乐' : i === 8 ? '停止音乐并播放赌气动作' : `触发动作 ${i}`;
            this._register(`CommandOrControl+Shift+${i}`, action, desc);
        }
        this._register('CommandOrControl+Shift+0', () => {
            BrowserWindow.getAllWindows()[0]?.webContents.send('stop-all-motions');
        }, '停止所有动作');
    }

    _register(accelerator, callback, description = '') {
        try {
            if (globalShortcut.register(accelerator, callback)) {
                this.shortcuts.push({ accelerator, description });
                console.log(`✓ 已注册快捷键: ${accelerator}${description ? ` (${description})` : ''}`);
            } else {
                console.warn(`✗ 快捷键注册失败: ${accelerator}`);
            }
        } catch (error) {
            console.error(`注册快捷键 ${accelerator} 时出错:`, error);
        }
    }

    unregisterAll() {
        globalShortcut.unregisterAll();
        console.log('已取消所有全局快捷键');
        this.shortcuts = [];
    }

    getRegisteredShortcuts() {
        return this.shortcuts;
    }
}

module.exports = { ShortcutManager };