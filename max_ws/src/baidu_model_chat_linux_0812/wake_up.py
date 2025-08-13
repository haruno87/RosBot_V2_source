import os
import time
from typing import Callable, Optional
from snowboydetect import SnowboyDetect
from pvrecorder import PvRecorder 

class VoiceWakeupDetector:
    def __init__(self, resource_filename: str, model_str: str, 
                 sensitivity: float = 0.4, 
                 wake_callback: Optional[Callable] = None):
        """
        基于Snowboy的语音唤醒检测器
        
        参数:
            resource_filename: Snowboy资源文件路径(.res)
            model_str: 模型文件路径(.pmdl或.umdl)
            sensitivity: 唤醒词检测灵敏度(0-1)
            wake_callback: 唤醒回调函数
        """
        self.resource_filename = resource_filename
        self.model_str = model_str
        self.sensitivity = str(sensitivity)
        self.wake_callback = wake_callback
        
        self.detector = None
        self.recorder = None
        self.is_running = False
        
        if not os.path.exists(self.resource_filename):
            raise FileNotFoundError(f"资源文件不存在: {self.resource_filename}")
        if not os.path.exists(self.model_str):
            raise FileNotFoundError(f"模型文件不存在: {self.model_str}")

    def start(self) -> None:
        """启动唤醒词检测"""
        if self.is_running:
            print("检测器已在运行中")
            return

        try:
            self.detector = SnowboyDetect(
                resource_filename=self.resource_filename,
                model_str=self.model_str
            )
            self.detector.SetSensitivity(self.sensitivity)
            
            self.recorder = PvRecorder(
                device_index=-1,
                frame_length=512  # Snowboy通常使用512的帧长度
            )

            self._print_device_info()
            self.is_running = True
            print(f"开始监听唤醒词")
            print("说唤醒词或按Ctrl+C退出...")

            self.recorder.start()
            self._detection_loop()

        except Exception as e:
            print(f"启动失败: {e}")
            self.stop()

    def stop(self) -> None:
        """停止检测并释放资源"""
        if self.recorder is not None:
            if self.recorder.is_recording:
                self.recorder.stop()
            self.recorder.delete()
            self.recorder = None

        if self.detector is not None:
            del self.detector
            self.detector = None

        self.is_running = False
        print("资源已释放")

    def _print_device_info(self) -> None:
        """打印音频设备信息"""
        print("\n===== 音频设备信息 =====")
        print(f"采样率: {self.detector.SampleRate()} Hz")
        print(f"声道数: {self.detector.NumChannels()}")
        print(f"位深度: {self.detector.BitsPerSample()}")

        devices = PvRecorder.get_available_devices()
        print("\n可用录音设备:")
        for i, device in enumerate(devices):
            print(f"  {i}: {device}")

        print(f"\n使用设备: {self.recorder.selected_device}")
        print("=======================\n")

    def _detection_loop(self) -> None:
        """唤醒词检测主循环"""
        try:
            while self.is_running:
                pcm = self.recorder.read()
                result = self.detector.RunDetection(pcm)
                
                if result > 0:  # Snowboy检测到唤醒词返回1
                    self._on_wakeword_detected()
                    
        except KeyboardInterrupt:
            print("\n用户中断检测")
        except Exception as e:
            print(f"检测出错: {e}")
        finally:
            self.stop()

    def _on_wakeword_detected(self) -> None:
        """唤醒词检测回调"""
        print("\n✅ 检测到唤醒词!")
        self._play_notification_sound()
        if self.wake_callback:
            self.wake_callback()

    def _play_notification_sound(self) -> None:
        """播放提示音"""
        try:
            import winsound
            winsound.Beep(1000, 200)
        except:
            try:
                import os
                os.system('play -nq -t alsa synth 0.2 sine 1000')
            except:
                print("(提示音不可用)")