from voice_capture import AudioRecorder
import time 

if __name__:
        recorder=AudioRecorder()
        recorder.start_recording()
        
        try:
            while recorder.process_frame():
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\n用户中断录音")
        finally:
            recorder.stop_recording()