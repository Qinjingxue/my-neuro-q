// ASR（自动语音识别）功能模块 - 支持语音打断
const { eventBus } = require('../core/event-bus.js');
const { Events } = require('../core/events.js');
const { appState } = require('../core/app-state.js');

class ASRProcessor {
    constructor(vadUrl, asrUrl, config = null) {
        this.vadUrl = vadUrl;
        this.asrUrl = asrUrl;
        this.config = config || {};

        this.voiceBargeInEnabled = this.config.asr?.voice_barge_in || false;
        console.log(`语音打断功能: ${this.voiceBargeInEnabled ? '已启用' : '已禁用'}`);

        this.isProcessingAudio = false;
        this.asrLocked = false;

        // 音频相关参数 - 仅定义
        this.audioContext = null;
        this.mediaStream = null;
        this.microphone = null;
        this.scriptNode = null;
        this.ws = null;
        this.SAMPLE_RATE = 16000;
        this.WINDOW_SIZE = 512;

        // 缓冲区和录音状态
        this.continuousBuffer = [];
        this.isRecording = false;
        this.recordingStartIndex = 0;
        this.PRE_RECORD_TIME = 1;
        this.PRE_RECORD_SAMPLES = this.SAMPLE_RATE * this.PRE_RECORD_TIME;
        
        // 静音检测
        this.lastSpeechTime = 0;
        this.SILENCE_THRESHOLD = 500;
        this.silenceTimeout = null;

        this.ttsProcessor = null;
    }

    setTTSProcessor(ttsProcessor) {
        this.ttsProcessor = ttsProcessor;
        console.log('TTS处理器已设置到ASR，语音打断功能可用');
    }

    /**
     * 【核心修改 #3】
     * 重构 WebSocket 设置，使其返回一个 Promise，并在 startRecording 中调用。
     */
    async setupWebSocket() {
        if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(this.vadUrl);

            this.ws.onopen = () => {
                console.log('VAD WebSocket已连接');
                resolve();
            };
            
            this.ws.onmessage = (event) => {
                if (!this.voiceBargeInEnabled) {
                    if (this.isProcessingAudio || this.asrLocked) return;
                } else {
                    if (this.asrLocked) return;
                }

                const data = JSON.parse(event.data);
                const isSpeaking = data.is_speech;

                if (isSpeaking) {
                    this.handleSpeech();
                } else {
                    this.handleSilence();
                }
            };
            
            this.ws.onclose = () => {
                console.log('VAD WebSocket已断开');
                this.ws = null;
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket错误:', error);
                this.ws = null;
                reject(error);
            };
        });
    }

    handleSpeech() {
        if (!this.voiceBargeInEnabled) {
            if (this.isProcessingAudio || this.asrLocked) return;
        } else {
            if (this.asrLocked) return;
            if (appState.isPlayingTTS() && this.ttsProcessor) {
                console.log('检测到用户语音，执行语音打断');
                this.ttsProcessor.interrupt();
            }
        }

        this.lastSpeechTime = Date.now();

        if (this.silenceTimeout) {
            clearTimeout(this.silenceTimeout);
            this.silenceTimeout = null;
        }

        if (!this.isRecording) {
            this.isRecording = true;
            this.recordingStartIndex = this.continuousBuffer.length;

            if (this.voiceBargeInEnabled && appState.isPlayingTTS()) {
                console.log('语音打断：开始录音');
            } else {
                console.log('正常模式：开始录音');
            }
        }
    }

    handleSilence() {
        if (!this.voiceBargeInEnabled) {
            if (this.isProcessingAudio || this.asrLocked) return;
        } else {
            if (this.asrLocked) return;
        }

        if (this.isRecording) {
            const currentTime = Date.now();
            const silenceDuration = currentTime - this.lastSpeechTime;

            if (!this.silenceTimeout) {
                this.silenceTimeout = setTimeout(() => {
                    this.finishRecording();
                    this.silenceTimeout = null;
                }, this.SILENCE_THRESHOLD);
            }
        }
    }

    /**
     * 【核心修改 #4】
     * startRecording 现在负责创建所有资源。
     */
    async startRecording() {
        try {
            if (this.audioContext && this.audioContext.state !== 'closed') {
                console.log('音频处理已在运行中。');
                return;
            }
            console.log('正在启动 ASR 录音...');

            await this.setupWebSocket();
            if (!this.ws) {
                throw new Error("WebSocket 连接失败，无法启动录音。");
            }

            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: this.SAMPLE_RATE,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            this.audioContext = new AudioContext({ sampleRate: this.SAMPLE_RATE });
            this.microphone = this.audioContext.createMediaStreamSource(this.mediaStream);
            this.scriptNode = this.audioContext.createScriptProcessor(this.WINDOW_SIZE, 1, 1);
            
            this.microphone.connect(this.scriptNode);
            this.scriptNode.connect(this.audioContext.destination);

            this.scriptNode.onaudioprocess = (e) => {
                if (this.asrLocked) return;

                const audioData = e.inputBuffer.getChannelData(0);
                this.continuousBuffer.push(...Array.from(audioData));
                
                if (this.continuousBuffer.length > this.SAMPLE_RATE * 30) {
                    const excessSamples = this.continuousBuffer.length - this.SAMPLE_RATE * 30;
                    this.continuousBuffer = this.continuousBuffer.slice(excessSamples);
                    if (this.isRecording) {
                        this.recordingStartIndex = Math.max(0, this.recordingStartIndex - excessSamples);
                    }
                }
                
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(audioData);
                }
            };

            console.log('音频处理已启动');
        } catch (err) {
            console.error('启动音频错误:', err);
            this.stopRecording(); // 如果启动失败，确保清理所有资源
        }
    }

    /**
     * 【核心修改 #5】
     * stopRecording 现在负责销毁所有资源。
     */
    stopRecording() {
        console.log('正在停止 ASR 录音...');
        
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }

        if (this.scriptNode) {
            this.scriptNode.onaudioprocess = null;
            this.scriptNode.disconnect();
            this.scriptNode = null;
        }
        if (this.microphone) {
            this.microphone.disconnect();
            this.microphone = null;
        }

        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close().catch(e => console.error("关闭AudioContext时出错:", e));
            this.audioContext = null;
        }
        
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.close();
        }
        this.ws = null;

        if (this.silenceTimeout) clearTimeout(this.silenceTimeout);
        this.isRecording = false;
        this.continuousBuffer = [];

        console.log('音频处理已彻底停止，麦克风已释放。');
    }

    async finishRecording() {
        if (!this.isRecording || this.asrLocked) return;
        this.isRecording = false;
        this.asrLocked = true;
        console.log('ASR锁定：开始处理录音');

        const recordingEndIndex = this.continuousBuffer.length;
        const actualStartIndex = Math.max(0, this.recordingStartIndex - this.PRE_RECORD_SAMPLES);
        const recordedSamples = this.continuousBuffer.slice(actualStartIndex, recordingEndIndex);

        if (recordedSamples.length > this.SAMPLE_RATE * 0.5) {
            const wavBlob = this.float32ToWav(new Float32Array(recordedSamples));
            if (this.voiceBargeInEnabled && !appState.isPlayingTTS()) {
                console.log('语音打断：录音完成，正在识别...');
            }
            await this.processRecording(wavBlob);
        } else {
            console.log("录音太短，丢弃");
            this.asrLocked = false;
        }
        this.continuousBuffer = this.continuousBuffer.slice(-this.PRE_RECORD_SAMPLES);
    }

    float32ToWav(samples) {
        const buffer = new ArrayBuffer(44 + samples.length * 2);
        const view = new DataView(buffer);

        this.writeString(view, 0, 'RIFF');
        view.setUint32(4, 36 + samples.length * 2, true);
        this.writeString(view, 8, 'WAVE');
        this.writeString(view, 12, 'fmt ');
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, 1, true);
        view.setUint32(24, this.SAMPLE_RATE, true);
        view.setUint32(28, this.SAMPLE_RATE * 2, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        this.writeString(view, 36, 'data');
        view.setUint32(40, samples.length * 2, true);

        this.floatTo16BitPCM(view, 44, samples);
        return new Blob([buffer], { type: 'audio/wav' });
    }

    writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }

    floatTo16BitPCM(view, offset, input) {
        for (let i = 0; i < input.length; i++, offset += 2) {
            const s = Math.max(-1, Math.min(1, input[i]));
            view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        }
    }

    async processRecording(audioBlob) {
        const formData = new FormData();
        formData.append('file', audioBlob, 'recording.wav');
        const useCloudASR = this.config.cloud?.asr?.enabled === true;
        let asrUrl;

        if (useCloudASR) {
            asrUrl = this.config.cloud.asr.url;
            if (this.config.cloud.asr.model) {
                formData.append('model', this.config.cloud.asr.model);
            }
        } else {
            asrUrl = this.asrUrl;
        }

        try {
            const headers = {};
            if (useCloudASR && this.config.cloud?.api_key) {
                headers['Authorization'] = `Bearer ${this.config.cloud.api_key}`;
            }
            console.log(`使用${useCloudASR ? `云端 (${this.config.cloud?.provider || '未知'})` : '本地'}ASR: ${asrUrl}`);
            const response = await fetch(asrUrl, { method: 'POST', headers: headers, body: formData });
            const result = await response.json();
            const recognizedText = result.text || (result.status === 'success' && result.text);

            if (recognizedText) {
                console.log("用户说:", recognizedText);
                if (this.voiceBargeInEnabled) {
                    console.log('语音打断：识别完成，发送给AI处理');
                }
                if (this.onSpeechRecognized) {
                    this.onSpeechRecognized(recognizedText);
                }
                return recognizedText;
            } else {
                console.error('ASR失败:', result.message || result.error || '未知错误');
                this.asrLocked = false;
                return null;
            }
        } catch (error) {
            console.error('处理录音失败:', error);
            this.asrLocked = false;
            return null;
        }
    }

    resumeRecording() {
        this.isProcessingAudio = false;
        this.asrLocked = false;
        console.log('ASR已解锁，可以接收新的语音输入');
    }

    setOnSpeechRecognized(callback) {
        this.onSpeechRecognized = callback;
    }

    getVoiceBargeInStatus() {
        return {
            enabled: this.voiceBargeInEnabled,
            isRecording: this.isRecording,
            asrLocked: this.asrLocked,
            isProcessingAudio: this.isProcessingAudio
        };
    }

    setVoiceBargeIn(enabled) {
        this.voiceBargeInEnabled = enabled;
        console.log(`语音打断功能已${enabled ? '启用' : '禁用'}`);
    }
}

module.exports = { ASRProcessor };