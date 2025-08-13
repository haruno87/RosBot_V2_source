from voice_capture import VoiceCaptureSystem
import time
import json
import os
from functions import handle_tool_call, get_chat_response
from playaudio import play_wav_file1,play_wav_file_async
from text_voice import text_to_voice,voice_to_text 
import threading

with open('./function.json', 'r', encoding='utf-8') as f:
    FUNCTIONS = json.load(f)
    # print(FUNCTIONS)


if __name__ == "__main__":

    print("===== 语音唤醒系统 =====")
    with open('./instructions.txt', 'r', encoding='utf-8') as f:
        instructions = f.read()
    messages = []
    init_message = {
        "role": "system",
        "content": instructions
    }

    # 创建语音捕获系统
    voice_system = VoiceCaptureSystem()
    
    try:
        # 启动唤醒检测线程
        voice_system.start_detection()
        
        # 主循环
        while True:
            # 检查是否有新录音
            recording_path = voice_system.get_latest_recording()
            if recording_path:
                # 获取语音转文本
                input_text = voice_to_text(recording_path) # 添加提示语
                
                # 检查是否为空或无效输入
                if not input_text or len(input_text.strip()) == 0:
                    print("未检测到有效语音输入")
                    # 删除录音文件避免重复处理
                    try:
                        os.remove(recording_path)
                    except:
                        pass
                    voice_system.recorder.latest_recording_path = None
                    continue
                    
                print(f"\n用户输入: {input_text}")

                user_message = {
                    "role": "user", 
                    "content": [{"type": "text", "text": input_text}]
                }
                m=[]
                m.append(init_message)  # 添加系统消息到上下文
                messages.append(user_message)
                m.append(user_message)

                
                # 获取AI响应
                try:
                    response = get_chat_response(m, FUNCTIONS)
                    
                    # 检查是否需要工具调用
                    if "tool_calls" in response.get("choices", [{}])[0].get("message", {}):
                        tool_call = response["choices"][0]["message"]["tool_calls"][0]
                        response = handle_tool_call(messages, tool_call)
                    
                    ai_response = response.get("result") or response.get("choices", [{}])[0].get("message", {}).get("content", "抱歉，我没有理解你的意思。")
                    print("\nAI:", ai_response)  
                    
                    # 添加到对话历史
                    messages.append({"role": "assistant", "content": ai_response})
                    
                    # 语音输出AI响应（自动播放）
                    try:
                        print("正在播放语音响应...")
                        output_filename= text_to_voice(ai_response)
                        if output_filename:
                            
                            play_wav_file1(output_filename, voice_system)
                            os.remove(output_filename)
                        else:
                            print("语音合成失败，无法播放")
                    except Exception as e:
                        print(f"语音播放失败: {str(e)}")
                                        
                except Exception as e:
                    error_msg = f"发生错误: {str(e)}"
                    print("\n" + error_msg)

            time.sleep(0.1)  # 避免占用太多CPU
            
    except KeyboardInterrupt:
        print("\n用户终止程序")
    except Exception as e:
        print(f"程序出错: {e}")
    finally:
        voice_system.stop()
        print("程序已退出")