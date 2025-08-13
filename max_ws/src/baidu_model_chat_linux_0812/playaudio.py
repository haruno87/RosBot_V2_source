import pyaudio
import wave
import time

def play_wav_file(file_path):
    """播放 WAV 文件，并在结束后等待 1 秒启动录音"""
    try:
        # 播放音频
        wf = wave.open(file_path, 'rb')
        p = pyaudio.PyAudio()
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )
        data = wf.readframes(1024)
        while data:
            stream.write(data)
            data = wf.readframes(1024)

        # 关闭资源
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf.close()

    except Exception as e:
        print(f"播放或启动录音失败: {e}")

#播放录音后自动开启录音
def play_wav_file1(file_path, voice_system):
    """播放 WAV 文件，并在结束后等待 1 秒启动录音"""
    try:
        # 播放音频
        wf = wave.open(file_path, 'rb')
        p = pyaudio.PyAudio()
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )
        data = wf.readframes(1024)
        while data:
            stream.write(data)
            data = wf.readframes(1024)

        # 关闭资源
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf.close()

        # 等待 1 秒后启动录音
        time.sleep(1)
        voice_system.recorder.start_recording()
        print("🎤 录音已启动，请说话...")
        try:
            while voice_system.recorder.process_frame():
                time.sleep(0.01)  # 避免占用太多CPU
        except KeyboardInterrupt:
            print("\n用户中断录音")

        voice_system.recorder.stop_recording()

    except Exception as e:
        print(f"播放或启动录音失败: {e}")


def play_wav_file_async(file_path):
    try:
        play_wav_file(file_path)
    except Exception as e:
        print(f"思考错误: {str(e)}")
