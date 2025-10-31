// ASRController.js - ASR控制器
const { ASRProcessor } = require('../../voice/asr-processor.js');
const { eventBus } = require('../../core/event-bus.js');
const { Events } = require('../../core/events.js');

class ASRController {
    constructor(vadUrl, asrUrl, config, inputRouter, diaryManager) {
        this.config = config;
        this.inputRouter = inputRouter;
        this.diaryManager = diaryManager;
        // 这个属性现在只决定 ASR 的【初始状态】，而不是决定是否创建 ASR 处理器
        this.asrEnabled = config.asr?.enabled !== false;
        this.voiceBargeInEnabled = config.asr?.voice_barge_in || false;

        this.asrProcessor = new ASRProcessor(vadUrl, asrUrl, config);
        this.setupASRCallback();
    }

    setupASRCallback() {
        if (!this.asrProcessor) return;
        this.asrProcessor.setOnSpeechRecognized(async (text) => {
            // --- 核心优化：将 handleVoiceInput（发送LLM请求）提前 ---
            // 立即开始处理高延迟的LLM请求
            const llmPromise = this.inputRouter.handleVoiceInput(text);

            // 同时，执行低延迟的UI更新
            if (this.inputRouter.uiController) {
                this.inputRouter.uiController.addNewLine(`${this.config.subtitle_labels.user}: ${text}`, 3000);
            }

            if (this.diaryManager) {
                this.diaryManager.resetTimer();
            }

            try {
                // 等待LLM请求流程完成
                await llmPromise;
            } finally {
                if (this.asrProcessor) {
                    setTimeout(() => {
                        this.asrProcessor.resumeRecording();
                    }, 100);
                }
            }
        });
    }

    setTTSProcessor(ttsProcessor) {
        if (this.asrProcessor && this.voiceBargeInEnabled && ttsProcessor) {
            this.asrProcessor.setTTSProcessor(ttsProcessor);
        }
    }
    
    async startRecording() {
        if (this.asrEnabled && this.asrProcessor) await this.asrProcessor.startRecording();
    }

    /**
     * 【核心修改 #1】
     * 移除此处的 asrEnabled 检查。
     * Controller 的职责是转发指令，具体的执行逻辑应由 ASRProcessor 决定。
     */
    stopRecording() {
        if (this.asrProcessor) this.asrProcessor.stopRecording();
    }
    
    async pauseRecording() {
        if (this.asrEnabled && this.asrProcessor) this.asrProcessor.pauseRecording();
    }
    
    async resumeRecording() {
        if (this.asrEnabled && this.asrProcessor) this.asrProcessor.resumeRecording();
    }
    
    getVoiceBargeInStatus() {
        if (!this.asrEnabled || !this.asrProcessor) return { enabled: false };
        return this.asrProcessor.getVoiceBargeInStatus();
    }
    
    setVoiceBargeIn(enabled, ttsProcessor) {
        this.voiceBargeInEnabled = enabled;
        if (this.asrEnabled && this.asrProcessor) {
            this.asrProcessor.setVoiceBargeIn(enabled);
            if (enabled && ttsProcessor) this.asrProcessor.setTTSProcessor(ttsProcessor);
        }
    }

    /**
     * 【核心修改 #2】
     * 修正 toggleASR 的逻辑，使其能够正确地开启和关闭。
     */
    async toggleASR() {
        // 如果 asrProcessor 从未被创建（因为配置中禁用了ASR），则无法切换
        if (!this.asrProcessor) {
            if (this.inputRouter.uiController) {
                this.inputRouter.uiController.addNewLine('ASR功能在配置中被禁用，无法切换', 3000);
            }
            console.warn('ASR功能在配置中被禁用，无法进行热切换。');
            return this.asrEnabled;
        }

        if (this.asrEnabled) {
            // 当前是开启状态 -> 将其关闭
            this.asrEnabled = false; // 1. 更新状态
            this.stopRecording();    // 2. 执行关闭（现在会无条件执行）
            if (this.inputRouter.uiController) {
                this.inputRouter.uiController.addNewLine('语音识别已关闭', 2000);
            }
        } else {
            // 当前是关闭状态 -> 将其开启
            this.asrEnabled = true;  // 1. 更新状态
            await this.startRecording(); // 2. 执行开启
            if (this.inputRouter.uiController) {
                this.inputRouter.uiController.addNewLine('语音识别已开启', 2000);
            }
        }
        return this.asrEnabled;
    }

    isEnabled() {
        return this.asrEnabled;
    }
}

module.exports = { ASRController };