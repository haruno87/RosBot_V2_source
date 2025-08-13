#!/usr/bin/env python3
import pyaudio
import snowboydetect
import time
import wave
import os
import signal
import struct
import threading
from typing import Optional
from ctypes import *
from camera_capture import capture_image_async
from playaudio import play_wav_file
from robot_face_seting import set_robot_expression

# 配置参数
MODEL_FILE = "./xiaokang.pmdl"  # 替换为你的模型文件路径
RESOURCE_FILE = "common.res"  # Snowboy资源文件
SENSITIVITY = 0.5  # 灵敏度(0-1)
SAMPLE_RATE = 16000  # 采样率
CHUNK_SIZE = 1024  # 音频块大小
MIN_USEFUL_FRAME = 40 # 无效语音帧数

# 抑制ALSA警告
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(*args):
    pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, frame_length: int = 512):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.is_recording = False
        self.audio_frames = []
        self.silence_counter = 0
        self.max_silence_frames = 16
        self.energy_threshold = 1400
        self.min_recording_frames = 16
        self.sample_rate = sample_rate
        self.frame_length = frame_length
        self.latest_recording_path = None

    def start_recording(self) -> None:
        capture_thread = threading.Thread(target=capture_image_async)
        capture_thread.start()
        set_robot_expression('listen')
        """开始录音"""
        if self.is_recording:
            print("已经在录音中")
            return
            
        self.stream = self.audio.open(
            rate=self.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.frame_length
        )
        
        self.is_recording = True
        self.audio_frames = []
        self.silence_counter = 0
        self.latest_recording_path = None
        print("🎤 正在录音... (等待语音输入)")

    def stop_recording(self) -> Optional[str]:
        """停止录音并保存文件"""
        if not self.is_recording:
            return None
        set_robot_expression('blink')    
        self.is_recording = False
        print("\n🛑 停止录音")
        print("录音帧数"+str(len(self.audio_frames)))
        if len(self.audio_frames) < MIN_USEFUL_FRAME:
            print("录音时间过短，已取消")
            self.audio_frames = []
            return None
            
        filename = "./input.wav"
        
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(self.audio_frames))
        
        duration = len(self.audio_frames) / self.sample_rate * self.frame_length
        print(f"💾 录音已保存: {filename} (时长: {duration:.1f}秒)")
        self.audio_frames = []
        self.latest_recording_path = filename
        return filename

    def process_frame(self) -> bool:
        """
        处理音频帧
        返回:
            bool: 如果录音应该继续返回True，否则返回False
        """
        if not self.is_recording or self.stream is None:
            return False
            
        data = self.stream.read(self.frame_length, exception_on_overflow=False)
        self.audio_frames.append(data)
        
        # 计算音频能量
        pcm = struct.unpack("%dh" % (len(data) // 2), data)
        sum_squares = sum(sample * sample for sample in pcm)
        rms = (sum_squares / len(pcm)) ** 0.5
        
        print(f"\r音频能量: {rms:.1f} (阈值: {self.energy_threshold}), 静音计数: {self.silence_counter}/{self.max_silence_frames}", end="")
        
        if len(self.audio_frames) > self.min_recording_frames:
            if rms < self.energy_threshold:
                self.silence_counter += 1
                if self.silence_counter >= self.max_silence_frames:
                    return False
            else:
                self.silence_counter = 0
                
        return True

    def close(self) -> None:
        """释放资源"""
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()

class VoiceWakeupDetector:
    def __init__(self, wake_callback=None):
        self.detector = snowboydetect.SnowboyDetect(
            resource_filename=RESOURCE_FILE.encode(),
            model_str=MODEL_FILE.encode())
        self.detector.SetSensitivity(str(SENSITIVITY).encode())
        self.detector.SetAudioGain(1)
        
        self.audio = pyaudio.PyAudio()
        # asound = cdll.LoadLibrary('libasound.so')
        # asound.snd_lib_error_set_handler(c_error_handler)
        
        self.stream = self.audio.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=CHUNK_SIZE)
        
        self.running = False
        self.wake_callback = wake_callback

    def play_beep(self):
        """播放提示音"""
        play_wav_file("./wozai.wav")  # 确保有一个 beep.wav 文件在当前目录

    def start(self):
        """开始监听唤醒词"""
        print("开始监听唤醒词... (按Ctrl+C退出)")
        self.running = True
        
        try:
            while self.running:
                data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                status = self.detector.RunDetection(data)
                
                if status > 0:  # 检测到唤醒词
                    print(f"检测到唤醒词! (ID: {status})")
                    self.play_beep()
                    if self.wake_callback:
                        self.wake_callback()
                
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n正在退出...")
        finally:
            self.stop()

    def stop(self):
        """停止并清理资源"""
        self.running = False
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        if hasattr(self, 'audio'):
            self.audio.terminate()
        print("已停止唤醒检测")

class VoiceCaptureSystem:
    def __init__(self):
        self.recorder = AudioRecorder(sample_rate=SAMPLE_RATE, frame_length=CHUNK_SIZE)
        self.wake_detector = VoiceWakeupDetector(wake_callback=self.on_wake_detected)
        self.detection_thread = None

    def on_wake_detected(self):
        """唤醒回调函数"""
        print("\n唤醒回调被调用")
        self.recorder.start_recording()
        
        try:
            while self.recorder.process_frame():
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\n用户中断录音")
        finally:
            self.recorder.stop_recording()

    def start_detection(self):
        """启动唤醒词检测线程"""
        self.detection_thread = threading.Thread(
            target=self.wake_detector.start,
            daemon=True
        )
        self.detection_thread.start()
        print("唤醒词检测线程已启动")

    def get_latest_recording(self) -> Optional[str]:
        """获取最新录音文件路径"""
        return self.recorder.latest_recording_path

    def stop(self):
        """停止系统"""
        self.wake_detector.stop()
        self.recorder.close()
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1)
        print("语音捕获系统已完全停止")

if __name__ == "__main__":
    # 检查模型文件是否存在
    if not os.path.exists(MODEL_FILE):
        print(f"错误: 模型文件 '{MODEL_FILE}' 不存在!")
        exit(1)
    
    if not os.path.exists(RESOURCE_FILE):
        print(f"错误: 资源文件 '{RESOURCE_FILE}' 不存在!")
        exit(1)
    
    # 设置Ctrl+C信号处理
    signal.signal(signal.SIGINT, lambda s, f: None)  # 由VoiceCaptureSystem处理停止
    
    system = VoiceCaptureSystem()
    system.start_detection()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收到停止信号...")
    finally:
        system.stop()