/**
 * AudioWorkletProcessor for Voxatar.
 * Captures microphone audio at 16kHz, 16-bit PCM mono.
 * Sends raw PCM frames to the main thread via port.postMessage.
 */
class AudioCaptureProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.bufferSize = options.processorOptions?.bufferSize || 3200; // 100ms at 16kHz
    this._buffer = new Float32Array(this.bufferSize);
    this._writeIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input && input[0] && input[0].length > 0) {
      const channelData = input[0]; // mono

      for (let i = 0; i < channelData.length; i++) {
        this._buffer[this._writeIndex++] = channelData[i];

        if (this._writeIndex >= this.bufferSize) {
          // Convert Float32 to Int16 PCM
          const pcm16 = new Int16Array(this.bufferSize);
          for (let j = 0; j < this.bufferSize; j++) {
            const s = Math.max(-1, Math.min(1, this._buffer[j]));
            pcm16[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }

          // Send raw PCM bytes to main thread
          this.port.postMessage(pcm16.buffer);

          // Reset buffer
          this._buffer = new Float32Array(this.bufferSize);
          this._writeIndex = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("audio-capture-processor", AudioCaptureProcessor);