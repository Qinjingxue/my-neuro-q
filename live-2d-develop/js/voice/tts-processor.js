// 改进的文本处理器 - (最终版，采用串行请求-并发播放模式)
const { eventBus } = require('../core/event-bus.js');
const { Events } = require('../core/events.js');
const { TTSPlaybackEngine } = require('./tts-playback-engine.js');
const { TTSRequestHandler } = require('./tts-request-handler.js');

class EnhancedTextProcessor {
   constructor(ttsUrl, uiController, onAudioDataCallback, onStartCallback, onEndCallback, config = null) {
       this.config = config || {};
       this.onEndCallback = onEndCallback;

       this.requestHandler = new TTSRequestHandler(this.config, ttsUrl);
       this.playbackEngine = new TTSPlaybackEngine(this.config, uiController, onAudioDataCallback, onStartCallback, onEndCallback);

       this.textSegmentQueue = [];
       this.audioDataQueue = [];

       this.isProcessing = false; // 标记处理线程是否正在工作
       this.isPlaying = false;    // 标记播放线程是否正在工作
       this.shouldStop = false;
       this._isCurrentlyPlayingSequence = false;

       // 启动两个核心“线程”
       this.startProcessingThread();
       this.startPlaybackThread();
   }

   setEmotionMapper(emotionMapper) {
       this.playbackEngine.setEmotionMapper(emotionMapper);
   }
   
    /**
     * 线程1：处理文本队列 (串行请求)
     * 这个线程一次只处理一个文本片段，确保音频顺序正确。
     */
    async startProcessingThread() {
        // 使用一个永续的异步循环来模拟线程
        while (true) {
            // 如果被中断或队列为空，则暂停
            if (this.shouldStop || this.textSegmentQueue.length === 0) {
                await new Promise(resolve => setTimeout(resolve, 300)); // 短暂休眠，避免CPU空转
                continue;
            }

            this.isProcessing = true;
            const segment = this.textSegmentQueue.shift(); // 取出第一个片段

            try {
                // 等待当前片段的API请求完成
                const audioData = await this.requestHandler.convertTextToSpeech(segment);
                
                // 如果成功获取音频且未被中断，则加入播放队列
                if (audioData && !this.shouldStop) {
                    this.audioDataQueue.push({ audio: audioData, text: segment });
                }
            } catch (error) {
                // 如果单个请求失败，只打印错误，然后继续处理下一个片段
                console.error(`TTS API请求失败 (片段: "${segment}"):`, error);
            } finally {
                this.isProcessing = false;
            }
        }
    }

    /**
     * 线程2：处理音频队列 (并发播放)
     * 这个线程独立运行，只要队列里有音频就拿出来播放。
     */
    async startPlaybackThread() {
        while (true) {
            if (this.shouldStop || this.audioDataQueue.length === 0 || this.isPlaying) {
                await new Promise(resolve => setTimeout(resolve, 300));
                continue;
            }
            
            // 标记整个语音序列开始
            if (!this._isCurrentlyPlayingSequence) {
                this._isCurrentlyPlayingSequence = true;
                eventBus.emit(Events.TTS_START);
            }

            this.isPlaying = true;
            const audioPackage = this.audioDataQueue.shift();
            
            // 等待音频播放完成
            await this.playbackEngine.playAudio(audioPackage.audio, audioPackage.text);
            
            this.isPlaying = false;

            // 检查整个语音序列是否已全部完成
            if (!this.isPlaying && !this.isProcessing && this.textSegmentQueue.length === 0 && this.audioDataQueue.length === 0) {
                this._isCurrentlyPlayingSequence = false;
                if (this.onEndCallback) this.onEndCallback();
                eventBus.emit(Events.TTS_END);
            }
        }
    }
   
    // 接收流式文本并分段
   addStreamingText(text) {
       if (this.shouldStop) return;
       this.requestHandler.segmentStreamingText(text, this.textSegmentQueue);
   }
   
    // 结束流式文本
   finalizeStreamingText() {
       this.requestHandler.finalizeSegmentation(this.textSegmentQueue);
   }

    // 处理完整的非流式文本
   async processTextToSpeech(text) {
       if (!text.trim()) return;
       this.reset(); // 开始新句子前先重置状态
       this.requestHandler.segmentFullText(text, this.textSegmentQueue);
   }

    // 重置所有状态和队列
   reset() {
       this.shouldStop = true; // 临时停止线程
       
       this.requestHandler.abortAllRequests();
       this.playbackEngine.reset();
       
       this.textSegmentQueue = [];
       this.audioDataQueue = [];
       this.isProcessing = false;
       this.isPlaying = false;
       this._isCurrentlyPlayingSequence = false; 

       // 短暂延迟后恢复线程运行
       setTimeout(() => { this.shouldStop = false; }, 100);
   }

    // 中断所有操作
    interrupt() {
        console.log('打断TTS播放...');
        eventBus.emit(Events.TTS_INTERRUPTED);
        
        this.shouldStop = true;
        
        this.requestHandler.abortAllRequests();
        this.playbackEngine.stop();
        
        this.textSegmentQueue = [];
        this.audioDataQueue = [];
       this.isProcessing = false;
        this.isPlaying = false;
        this._isCurrentlyPlayingSequence = false;
 
        if (this.onEndCallback) this.onEndCallback();
        
        // 立即恢复线程，准备接收新任务
        this.shouldStop = false;
        console.log('TTS处理器已立即重置');
    }

   stop() {
      this.interrupt();
   }

   // 判断是否还在播放整个语音序列
   isPlaying() {
       return this._isCurrentlyPlayingSequence;
   }
}

module.exports = { EnhancedTextProcessor };