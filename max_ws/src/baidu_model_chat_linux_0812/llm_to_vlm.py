#!/usr/bin/env python3
import os
import signal
import sys
import pyaudio
import time
import json
import rospy
import subprocess
import threading
import actionlib
from actionlib_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Quaternion
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from dashscope.audio.asr import (
    Recognition,
    RecognitionCallback,
    RecognitionResult,
    TranslationRecognizerRealtime,
    TranscriptionResult,
    TranslationResult,
)
from openai import OpenAI
from dashscope.audio.tts_v2 import SpeechSynthesizer, ResultCallback, AudioFormat
from datetime import datetime
from typing import List

from alibabacloud_ccc20200701.client import Client as CCC20200701Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_ccc20200701 import models as ccc20200701_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient

# coding=utf-8
import urllib
import urllib.request
import hashlib

class Sample_tele:
    def __init__(self):
        pass

    @staticmethod
    def create_client() -> CCC20200701Client:
        config = open_api_models.Config(
            access_key_id='',
            # 必填，请确保代码运行环境设置了环境变量 ALIBABA_CLOUD_ACCESS_KEY_SECRET。,
            access_key_secret='',
        )
        config.endpoint = f'ccc.cn-shanghai.aliyuncs.com'
        return CCC20200701Client(config)

    @staticmethod
    def main(
        args: List[str],
    ) -> None:
        client = Sample_tele.create_client()
        # 确保 callee 参数被正确传递，这里使用了硬编码的电话号码，实际应用中可能需要从配置或参数获取
        # 假设 args 中可能包含电话号码，或者直接使用硬编码的
        phone_to_call = '19398249958' # 硬编码的电话号码，请根据实际情况修改或从 args 获取
        # if len(args) > 1:
        #     # 简单的从 args 获取电话号码的示例，可能需要更健壮的解析
        #     phone_to_call = args[1]


        make_call_request = ccc20200701_models.MakeCallRequest(
            caller='6690398265223105', # 你的主叫号码
            callee=phone_to_call, # 被叫号码
            device_id='device', # 设备ID，根据你的配置修改
            instance_id='demo-1303351780745769' # 你的实例ID
        )
        runtime = util_models.RuntimeOptions()
        try:
            print(f"Attempting to call {phone_to_call}...")
            client.make_call_with_options(make_call_request, runtime)
            print(f"Call initiated to {phone_to_call}")
        except Exception as error:
            print(f"Call failed: {error.message}")
            if hasattr(error, 'data') and error.data:
                print(error.data.get("Recommend"))
            # UtilClient.assert_as_string(error.message) # 这行可能会导致程序退出，根据需要保留或注释

    # async main_async 方法保持不变，因为当前同步调用 main
    @staticmethod
    async def main_async(
        args: List[str],
    ) -> None:
        client = Sample_tele.create_client()
        make_call_request = ccc20200701_models.MakeCallRequest(
            callee='19398249958',
            device_id='device',
            instance_id='demo-1303351780745769'
        )
        runtime = util_models.RuntimeOptions()
        try:
            await client.make_call_with_options_async(make_call_request, runtime)
        except Exception as error:
            print(error.message)
            print(error.data.get("Recommend"))
            UtilClient.assert_as_string(error.message)

# 获取 DashScope API Key
if 'DASHSCOPE_API_KEY' in os.environ:
    dashscope_api_key = os.environ['DASHSCOPE_API_KEY']
else:
    # 如果环境变量未设置，使用占位符，实际部署时应确保设置环境变量
    dashscope_api_key = '<your-dashscope-api-key>'
    print("Warning: DASHSCOPE_API_KEY environment variable not set. Using placeholder.")


# 初始化 OpenAI 客户端 (用于调用 Qwen)
client = OpenAI(
    api_key=dashscope_api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# TTS 模型和声音设置
model = "cosyvoice-v1"
voice = "longxiaochun"

class CosyVoiceCallback(ResultCallback):
    _player = None
    _stream = None

    def on_open(self):
        print("WebSocket is open.")
        self._player = pyaudio.PyAudio()
        # 根据 TTS 模型输出的音频格式设置 PyAudio 流
        self._stream = self._player.open(
            format=pyaudio.paInt16, channels=1, rate=22050, output=True
        )

    def on_complete(self):
        print(get_timestamp() + " Speech synthesis task complete successfully.")

    def on_error(self, message: str):
        print(f"Speech synthesis task failed, {message}")

    def on_close(self):
        print(get_timestamp() + " WebSocket is closed.")
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._player:
            self._player.terminate()
        self._stream = None # Reset stream and player on close
        self._player = None


    def on_data(self, data: bytes) -> None:
        if self._stream:
            self._stream.write(data)

# ASR 参数设置
sample_rate = 16000
channels = 1
dtype = 'int16'
format_pcm = 'pcm'
block_size = 3200
wake_up_word = "你好"

# 全局变量 (尽量减少全局变量的使用，但 listening_for_wake_up 控制 ASR 行为，可能需要保留)
listening_for_wake_up = True

mic = None
stream = None
full_text = "" # 用于累积识别到的文本

# request_chat_start = False # 这些标志现在由 self.state 和子状态标志管理
# request_chat_done = False

callback = None
synthesizer = None # TTS Synthesizer 实例

def get_timestamp():
    now = datetime.now()
    formatted_timestamp = now.strftime("[%Y-%m-%d %H:%M:%S.%f]")
    return formatted_timestamp


def send_sms(user, password, phone, content, smsapi="http://api.smsbao.com/"):
        # 状态码映射字典
    statusStr = {
        '0': '短信发送成功',
        '-1': '参数不全',
        '-2': '服务器空间不支持,请确认支持 curl 或者 fsocket,联系您的空间商解决或者更换空间',
        '30': '密码错误',
        '40': '账号不存在',
        '41': '余额不足',
        '42': '账户已过期',
        '43': 'IP 地址限制',
        '50': '内容含有敏感词'
    }

    # 对密码进行 md5 加密
    password_md5 = hashlib.md5(password.encode("utf8")).hexdigest()

    # 构造发送数据
    data = urllib.parse.urlencode({'u': user, 'p': password_md5, 'm': phone, 'c': content})

    # 构造发送 URL
    send_url = f"{smsapi}sms?{data}"

    try:
        # 发送请求
        response = urllib.request.urlopen(send_url)
        the_page = response.read().decode('utf-8')

        # 返回发送结果
        return statusStr.get(the_page, "未知错误")

    except Exception as e:
        # 捕获异常并返回错误信息
        return f"发送失败：{str(e)}"

class VoiceInteractionHandler(RecognitionCallback):
    def __init__(self, keyword_pub):
        super().__init__()
        self.keyword_pub = keyword_pub
        # 创建 move_base 客户端
        self.client = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        rospy.loginfo("Waiting for move_base action server...")
        self.client.wait_for_server()
        rospy.loginfo("Connected to move_base action server")
        self.charge_back_process = None
        self.lock = threading.Lock() # 线程锁，如果 on_event 和其他方法可能并发访问共享资源，虽然当前结构中 on_event 是主要入口
        self.keyword_goals = {
            "fall": "目标点" # 这个变量的用途在代码中不明确，保留原样
        }

        # 定义机器人可能处于的主状态
        self.state = 'listening_for_wake_up'

        # 定义子状态或标志，用于在特定主状态下进一步区分行为
        self.waiting_for_command = False
        self.waiting_for_fall_response = False
        self.waiting_for_call_request = False

        # 计时器实例
        self.fall_response_timer = None
        self.call_request_timer = None
        self.fall_no_response_count = 0 # 摔倒事件无回应计数


        # 可用的函数及其描述
        self.available_functions = {
            "go_to_location": self.go_to_location,
            "follow_me": self.start_tracker_node,
            "stop_following": self.stop_tracker_node,
            "make_phone_call": self.make_phone_call,
            "do_nothing": self.do_nothing,
            "handle_fall_event": self.handle_fall_event,
            "charge_back": self.charge_back,
            "remember_information": self.remember_information,
            "find_item": self.find_item, # 添加的函数
        }
        self.function_descriptions = [
         {
                "name": "go_to_location",
                "description": "当用户需要办理特定业务时，导航到对应的服务点。例如：当用户想要办理签证时，导航到签证服务点（A点）；当用户需要补办身份证时，导航到身份证服务点（B点）；当用户需要办理出入境时，导航到取号机（C点）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "目标地点的名称",
                            "enum": ["A点", "B点", "C点"]
                        }
                    },
                    "required": ["location"]
                }
            },
            {
                "name": "charge_back",
                "description": "回到充电桩的位置"
            },
            {
                "name": "follow_me",
                "description": "开始跟随说话人"
            },
            {
                "name": "stop_following",
                "description": "停止跟随"
            },
            {
                "name": "make_phone_call",
                "description": "发起电话呼叫",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone_number": {
                            "type": "string",
                            "description": "要拨打的电话号码"
                        }
                    },
                    "required": ["phone_number"]
                }
            },
            {
                "name": "do_nothing",
                "description": "执行无操作"
            },
            {
                "name": "handle_fall_event",
                "description": "当检测到外部节点发来摔倒信号时处理摔倒事件，不对用户语音中的摔倒做响应"
            },
            {
                "name": "remember_information",
                "description": "记住用户提供的信息，并将其添加到后续对话中",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "用于存储信息的键"
                        },
                        "value": {
                            "type": "string",
                            "description": "要存储的信息的值"
                        }
                    },
                    "required": ["key", "value"]
                }
            },
            { # 添加的函数描述
                "name": "find_item",
                "description": "去桌子附近然后在桌面上寻找指定的物品",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_name": {
                            "type": "string",
                            "description": "要寻找的物品的名称"
                        }
                    },
                    "required": ["item_name"]
                }
            }
        ]
        self.system_prompt_file = '/home/saber/max_ws/maga/src/deepseek/scripts/system_prompt.json'
        self.system_prompt_key = 'prompt'
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self):
        try:
            with open(self.system_prompt_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                prompt = data.get(self.system_prompt_key)
                if prompt is None:
                    rospy.logerr(f"JSON 文件 {self.system_prompt_file} 中找不到键 '{self.system_prompt_key}'。")
                    return "你是家庭教育及康养服务机器人，要求输出的内容简洁，语气亲近，输出20字以内"
                return prompt
        except FileNotFoundError:
            rospy.logerr(f"找不到 JSON 文件: {self.system_prompt_file}")
            return "你是家庭教育及康养服务机器人，要求输出的内容简洁，语气亲近，输出20字以内"
        except json.JSONDecodeError:
            rospy.logerr(f"无法解析 JSON 文件: {self.system_prompt_file}")
            return "你是家庭教育及康养服务机器人，要求输出的内容简洁，语气亲近，输出20字以内"

    def go_to_location(self, location):
        """
        将LLM识别的地点映射为内部指令，并将其打包成接收端需要的JSON格式并发送。
        """
        rospy.loginfo(f"接收到导航请求，目标地点: '{location}'")

        # 1. 定义从“地点”到“指令字符串”的映射
        #    这里的指令字符串必须与您接收端 keyword_goals 字典的键完全一致
        location_to_command_map = {
            "A点": "go to point a",
            "B点": "go to point b",
            "C点": "go to point c",
        }

        # 2. 查找对应的指令字符串
        command_string = location_to_command_map.get(location)

        if command_string:
            # 3. 【核心修正】构建一个字典，其键名必须是 "keyword"
            message_dict = {
                "keyword": command_string 
            }
            
            # 4. 将字典转换为JSON格式的字符串
            json_to_send = json.dumps(message_dict)
            
            rospy.loginfo(f"将发送最终正确的JSON: {json_to_send}")
            
            # 5. 发布这个完全符合下游要求的JSON字符串
            self.keyword_pub.publish(json_to_send) # 在实际环境中请取消此行注释

            rospy.loginfo("JSON指令已发送。")
            
            self.synthesize_and_play(f"好的,请跟着我前往办理。\n")
        else:
            rospy.logwarn(f"无法为地点 '{location}' 找到对应的指令。")
            self.synthesize_and_play(f"抱歉，我无法识别地点 {location}。")

        self._transition_to_state('listening_for_wake_up')

    def make_phone_call(self, phone_number):
        phone_number='13169957918'
        rospy.loginfo(f"发起电话呼叫到: {phone_number}")
        # 调用打电话的逻辑，传递电话号码
        Sample_tele.main(['--', phone_number]) # 假设 Sample_tele.main 可以接受电话号码作为参数
        self.synthesize_and_play(f"正在呼叫{phone_number}")
        # 电话呼叫完成后，可以考虑回到监听唤醒词状态
        # self._transition_to_state('listening_for_wake_up') # 示例：电话呼叫完成回到监听状态

    def charge_back(self):
        rospy.loginfo("返回充电桩")
        keyword_msg = json.dumps({"keyword": "Go to charge"})
        self.keyword_pub.publish(keyword_msg)
        self.synthesize_and_play("好的,我将返回充电桩充电，待会见啦!\n")
        # 充电完成后，可以考虑回到监听唤醒词状态
        # self._transition_to_state('listening_for_wake_up') # 示例：充电完成回到监听状态

    def do_nothing(self):
        rospy.loginfo("执行无操作")
        self.synthesize_and_play("好的")
        # 执行无操作后，回到监听唤醒词状态
        self._transition_to_state('listening_for_wake_up')

    def handle_fall_event(self):
        """处理摔倒事件的起始逻辑"""
        rospy.loginfo("收到摔倒信息，触发摔倒处理")
        # 确保当前不在处理摔倒事件，避免重复触发
        # 使用状态来管理，如果状态已经是 handling_fall_response，则忽略
        if self.state != 'handling_fall_response':
            # 暂时将状态设置为 handling_fall_response，以防止在处理过程中重复触发
            self._transition_to_state('handling_fall_response')

            self.synthesize_and_play_care_message() # 播放关怀语音并发起电话呼叫

            # 在播放完语音和发起呼叫后，立即将状态切换回监听唤醒词
            self._transition_to_state('listening_for_wake_up')

            # 重置任何与摔倒相关的标志
            self.waiting_for_fall_response = False
            self.fall_no_response_count = 0

            # 发送摔倒事件的 ROS 消息 (可能仍然需要通知其他节点)
            keyword_msg = json.dumps({"keyword": "fall"})
            self.keyword_pub.publish(keyword_msg)

            # 如果立即返回监听唤醒词状态，之前注释掉的计时器和 on_event 中处理
            # 'handling_fall_response' 状态的逻辑可能就不再需要了。
            # on_event 方法将根据 'listening_for_wake_up' 状态处理用户在语音后的任何发言。

        else:
            rospy.loginfo("已在摔倒处理流程中，忽略重复触发")


    def start_tracker_node(self):
        rospy.loginfo("开始跟随")
        keyword_msg = json.dumps({"keyword": "follow"})
        self.keyword_pub.publish(keyword_msg)
        self.synthesize_and_play("好的收到！我开始跟着你啦！\n")
        # 进入跟随状态，可能需要一个新的主状态 'following'
        # self._transition_to_state('following') # 示例：进入跟随状态

    def stop_tracker_node(self):
        rospy.loginfo("停止跟随")
        keyword_msg = json.dumps({"keyword": "stop"})
        self.keyword_pub.publish(keyword_msg)
        self.synthesize_and_play("好的收到！停止跟随！\n")
        # 停止跟随后，回到监听唤醒词状态
        self._transition_to_state('listening_for_wake_up')

    def find_item(self, item_name=""):
        """
        导航到指定位置，到达后发布目标物品名称。
        Args:
            item_name (str): 要寻找的物品的名称。
        """
        rospy.loginfo(f"开始导航到桌子并寻找物品: {item_name}")

        # 播放语音提示
        self.synthesize_and_play(f"好的，我即将运动到桌子附近，并寻找{item_name}。\n")
        #[ INFO] [1751780065.113742926]: Setting goal: Frame:map, Position(5.398, -1.921, 0.000), Orientation(0.000, 0.000, 0.012, 1.000) = Angle: 0.023

        # 定义目标位姿
        goal_pose = PoseStamped()
        goal_pose.header.frame_id = "map"  # 替换为你的地图坐标系
        goal_pose.pose.position.x = 5.412
        goal_pose.pose.position.y = -1.970
        goal_pose.pose.position.z = 0.033
        # 将欧拉角转换为四元数 (x, y, z, w)
        quaternion = [0.000, 0.000, -0.001, 1.000]
        goal_pose.pose.orientation.x = quaternion[0]
        goal_pose.pose.orientation.y = quaternion[1]
        goal_pose.pose.orientation.z = quaternion[2]
        goal_pose.pose.orientation.w = quaternion[3]

        # 创建一个 SimpleActionClient 连接到 move_base action server
        client = actionlib.SimpleActionClient('move_base', MoveBaseAction) # 请确认你的导航 Action Server 名称
        rospy.loginfo("等待 move_base action server 启动...")
        client.wait_for_server()
        rospy.loginfo("move_base action server 已启动。")

        # 创建一个导航目标
        goal = MoveBaseGoal()
        goal.target_pose = goal_pose
        goal.target_pose.header.stamp = rospy.Time.now()

        rospy.loginfo("发送导航目标...")
        client.send_goal(goal)

        # 等待导航完成
        client.wait_for_result()

        # 检查导航结果
        if client.get_state() == GoalStatus.SUCCEEDED:
            rospy.loginfo("成功到达目标位置！")
            # 到达目的地后发布目标物品消息
            target_item_msg = json.dumps({"target_item": item_name})
            self.keyword_pub.publish(target_item_msg)
            self.synthesize_and_play(f"我已到达，开始寻找。\n")
            rospy.loginfo(f"已发布目标物品消息: {target_item_msg}")
        else:
            rospy.logwarn("导航失败！")

        # 找完东西后回到初始状态
        self._transition_to_state('listening_for_wake_up')

    def on_open(self) -> None:
        global mic, stream
        print('RecognitionCallback open.') # 可以修改打印信息以反映新的识别器类型
        mic = pyaudio.PyAudio()
        stream = mic.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True
        )

    def on_close(self) -> None:
        global mic, stream
        print('RecognitionCallback close.') # 可以修改打印信息
        if stream:
            stream.stop_stream()
            stream.close()
        if mic:
            mic.terminate()
        stream = None
        mic = None

    def on_complete(self) -> None:
        print('RecognitionCallback completed.') # 可以修改打印信息


    def on_error(self, message) -> None:
        print('RecognitionCallback task_id: ', message.request_id) # 可以修改打印信息
        print('RecognitionCallback error: ', message.message) # 可以修改打印信息
        rospy.logerr(f"ASR Error: {message.message}")
        if stream and stream.is_active():
            stream.stop_stream()
            stream.close()
        # sys.exit(1) # 根据需要决定是否退出

    def process_llm_response(self, response):
        """处理 LLM 的响应，包括文本回复和函数调用"""
        if response.choices:
            message = response.choices[0].message
            if message.function_call:
                function_name = message.function_call.name
                arguments = json.loads(message.function_call.arguments)
                if function_name in self.available_functions:
                    rospy.loginfo(f"Function Call: {function_name} with arguments {arguments}")
                    # 执行函数调用
                    self.available_functions[function_name](**arguments)
                    # 注意：函数调用内部可能会改变 self.state
                else:
                    rospy.logwarn(f"未知的函数调用: {function_name}")
                    self.synthesize_and_play("我不明白你的指令")
                    # 未知函数调用后，回到监听唤醒词状态
                    self._transition_to_state('listening_for_wake_up')
            else:
                content = message.content
                print(f"Qwen 响应: {content}")
                self.synthesize_and_play(content if content else "好的\n")
                # 文本回复后，回到监听唤醒词状态
                self._transition_to_state('listening_for_wake_up')
        else:
            self.synthesize_and_play("没有收到有效的回复")
            # 没有有效回复，回到监听唤醒词状态
            self._transition_to_state('listening_for_wake_up')

    def on_event(
        self,
        request_id,
        transcription_result: TranscriptionResult = None,
        translation_result: TranslationResult = None,
        usage=None,
    ) -> None:
        """处理新的 ASR 识别和翻译结果事件"""
        global full_text
        global listening_for_wake_up

        print("request id: ", request_id)
        print("usage: ", usage)

        if transcription_result is not None:
            text = transcription_result.text.strip()
            print(f'Recognition text (State: {self.state}, ASR wake-up: {listening_for_wake_up}): {text}')

            if self.state == 'listening_for_wake_up':
                full_text += text
                if transcription_result.is_sentence_end:  # 使用文档中正确的属性
                    if wake_up_word in full_text:
                        rospy.loginfo("唤醒词 detected!")
                        self.synthesize_and_play("在呢\n")
                        self._transition_to_state('waiting_for_command')
                    full_text = ""
            elif self.state == 'waiting_for_command':
                full_text += text
                if transcription_result.is_sentence_end:  # 使用文档中正确的属性
                    print(f'用户指令: {full_text}')
                    # 尝试判断用户是否需要寻找桌面上的物品
                    if "找" in full_text and ("茶几" in full_text or "桌" in full_text) and "什么" in full_text:
                        # 提取要寻找的物品名称
                        import re
                        match = re.search(r"找(?:桌子|桌面|茶几|茶|桌)上的(.*)", full_text)
                        if match:
                            item_name = match.group(1).strip()
                            rospy.loginfo(f"用户请求寻找茶几上的物品: {item_name}")
                            self.find_item(item_name)
                            self.synthesize_and_play("好的收到。\n")
                            self._transition_to_state('listening_for_wake_up')
                            full_text = ""
                            return
                        else:
                            rospy.loginfo("未能提取到要寻找的物品名称，继续调用 LLM。")
                            # 如果未能提取到物品名称，或者用户意图不明确，仍然调用 LLM
                            completion = client.chat.completions.create(
                                model="qwen-plus",
                                messages=[
                                    {"role": "system", "content": self.system_prompt},
                                    {"role": "user", "content": full_text}
                                ],
                                functions=self.function_descriptions,
                                function_call="auto",
                                stream=False
                            )
                            self.process_llm_response(completion)
                            full_text = ""
                            return
                    else:
                        # 如果不是寻找桌面物品的需求，正常调用 LLM
                        completion = client.chat.completions.create(
                            model="qwen-plus",
                            messages=[
                                {"role": "system", "content": self.system_prompt},
                                {"role": "user", "content": full_text}
                            ],
                            functions=self.function_descriptions,
                            function_call="auto",
                            stream=False
                        )
                        self.process_llm_response(completion)
                        full_text = ""
            elif self.state == 'handling_fall_response':
                self.state == 'waiting_for_command'
                # if self.waiting_for_fall_response:
                #     full_text += text
                    # ... (摔倒处理逻辑保持不变)
            # elif self.state == 'waiting_for_call_request':
            #     if self.waiting_for_call_request:
            #         full_text += text
                    # ... (电话请求处理逻辑保持不变)

    def synthesize_and_play(self, text):
        """合成语音并播放"""
        global synthesizer
        # 在每次播放前重新初始化 Synthesizer，确保状态正确
        # 注意：频繁创建 Synthesizer 实例可能有性能开销，如果需要优化，可以考虑复用实例
        synthesizer = SpeechSynthesizer(
            model=model,
            voice=voice,
            format=AudioFormat.PCM_22050HZ_MONO_16BIT,
            callback=CosyVoiceCallback() # 每次播放使用一个新的 CosyVoiceCallback 实例
        )
        try:
            synthesizer.streaming_call(text)
            synthesizer.streaming_complete() # 等待播放完成
        except Exception as e:
            rospy.logerr(f"TTS synthesis failed: {e}")
            # 播放失败时，确保清理资源
            if synthesizer:
                synthesizer.close()


    def synthesize_and_play_care_message(self):
        # """播放摔倒关怀消息"""
        result = send_sms(
                user='kengo_',
                password='12138.aaa',
                phone='19398249958',
                content='【康养机器人】社康请注意，11栋C户疑似发生老人发生摔倒事件！请及时到户处理!门锁密码为：114514。'
        )         # 用户1
        print(result)
        # result = send_sms(
        #         user='kengo_',
        #         password='12138.aaa',
        #         phone='19398249958',
        #         content='【康养机器人】社康请注意，11栋C户疑似发生老人发生摔倒事件！请及时到户处理!门锁密码为：114514。'
        # )
        # print(result)
        # result = send_sms(
        #         user='kengo_',
        #         password='12138.aaa',
        #         phone='13502756071',
        #         content='【康养机器人】社康请注意，11栋C户疑似发生老人发生摔倒事件！请及时到户处理!门锁密码为：114514。'
        # )         # 用户3
        # print(result)
        care_message = "检测到发生摔倒，别着急，我马上帮你呼叫以及发送短信寻求帮助！\n" # 根据需要修改消息内容
        rospy.loginfo("语音播报: %s", care_message)
        self.synthesize_and_play(care_message)
        rospy.loginfo("用户请求电话呼叫")
        Sample_tele.main(sys.argv[1:])



    # def fall_response_timeout(self):
    #     """摔倒后等待用户回应的超时处理"""
    #     # 只有在确实处于等待摔倒回应状态时才处理超时
    #     if self.state == 'handling_fall_response' and self.waiting_for_fall_response:
    #         self.fall_no_response_count += 1
    #         rospy.loginfo(f"摔倒回应超时，次数: {self.fall_no_response_count}")

    #         if self.fall_no_response_count == 1:
    #             self.synthesize_and_play("我没有收到您的回应，请告诉我您是否需要帮助。\n")
    #             self.fall_response_timer = threading.Timer(8.0, self.fall_response_timeout)
    #             self.fall_response_timer.start()
    #         elif self.fall_no_response_count == 2:
    #             self.synthesize_and_play("我还是没有收到您的回应。\n")
    #             self.fall_response_timer = threading.Timer(5.0, self.fall_response_timeout)
    #             self.fall_response_timer.start()
    #         elif self.fall_no_response_count == 3:
    #             self.synthesize_and_play("你情况还好吗？我即将帮您拨打紧急联系人的电话。\n")
    #             self.fall_response_timer = threading.Timer(5.0, self.fall_response_timeout)
    #             self.fall_response_timer.start()
    #         else: # 达到3次超时
    #             print("三次无响应，开始主动拨打电话")
    #             self.synthesize_and_play("我没有收到您的回应，现在我要帮您打电话并且发送短信信息寻求帮助了。\n")
    #             # 执行拨打电话的逻辑
    #             Sample_tele.main(sys.argv[1:]) # 同样，确保这里能获取到正确的电话号码
    #             # 调用发送短信的函数
    #             result = send_sms(
    #                 user='kengo_',
    #                 password='12138.aaa',
    #                 phone='13169957918',
    #                 content='【康养机器人】老人发生摔倒！请及时处理!'
    #             )

    #             # 输出发送结果
    #             print(result)
    #             # 摔倒处理流程完成，回到监听唤醒词状态
    #             self._transition_to_state('listening_for_wake_up')
    #             self.waiting_for_fall_response = False # 重置子状态
    #             global full_text
    #             full_text = "" # 清除文本


    # def call_request_timeout(self):
    #     """摔倒后等待电话请求回答的超时处理"""
    #     # 只有在确实处于等待电话请求状态时才处理超时
    #     if self.state == 'waiting_for_call_request' and self.waiting_for_call_request:
    #         print("电话请求超时，假设用户不需要电话帮助")
    #         self.synthesize_and_play("我没有收到您的回应，假设您现在不需要电话帮助。如果需要，请再次呼唤我。\n")
    #         # 处理流程结束，回到监听唤醒词状态
    #         self._transition_to_state('listening_for_wake_up')
    #         self.waiting_for_call_request = False # 重置子状态
    #         global full_text
    #         full_text = "" # 清除文本

    def fall_callback(self, msg):
        """ROS 订阅摔倒信息的回调函数"""
        # 这个回调函数应该只负责接收摔倒信息并触发摔倒处理的开始
        # 不应该在这里直接修改 listening_for_wake_up 或其他状态
        global full_text
        # global request_chat_start # 不再需要这些全局变量
        # global request_chat_done
        # global listening_for_wake_up # 不在这里修改

        # print("fall_callback = {listening_for_wake_up} ") # 调试日志

        try:
            data = json.loads(msg.data)
            if data.get("FallState", 0) == 1:
                rospy.loginfo("收到摔倒信息，准备触发摔倒处理")
                # 触发摔倒处理的起始函数
                self.handle_fall_event()
                # # 在触发处理后，清空当前累积的文本，避免干扰摔倒处理流程中的语音识别
                # full_text = ''
        except json.JSONDecodeError:
            rospy.logerr("收到的消息不是有效的JSON格式")
        except Exception as e:
            rospy.logerr("处理摔倒信息时出错: %s", str(e))

    def remember_information(self, key, value):
        """
        将信息存储到 JSON 文件中，并将其添加到 prompt 中。

        :param key: 用于存储信息的键。
        :param value: 要存储的信息的值。
        """
        config_file_path = self.system_prompt_file
        config_key = self.system_prompt_key
        try:
            with open(config_file_path, 'r+', encoding='utf-8') as f:
                config_data = json.load(f)
                # 确保 'prompt' 键存在，如果不存在则创建
                if config_key not in config_data:
                    config_data[config_key] = ""
                # 累加新信息到现有的 prompt
                config_data[config_key] += f" {key}: {value}."
                f.seek(0)
                json.dump(config_data, f, indent=4, ensure_ascii=False)
                f.truncate()
            rospy.loginfo(f"信息 '{value}' 成功存储到键 '{key}' 中，并已添加到 prompt。")
            self.synthesize_and_play("好的，我已经记住了。")
            # 重新加载 prompt，确保下次对话包含记忆的信息
            self.system_prompt = self._load_system_prompt()
        except Exception as e:
            rospy.logerr(f"存储信息到 JSON 文件时出错: {e}")
            self.synthesize_and_play("抱歉，我没能记住。")
        finally:
            # 存储信息后，回到监听唤醒词状态
            self._transition_to_state('listening_for_wake_up')


    def _transition_to_state(self, new_state):
        """
        状态转换辅助方法，用于统一管理状态切换时的操作
        """
        rospy.loginfo(f"State Transition: {self.state} -> {new_state}")
        self.state = new_state

        # 根据新的主状态，设置 ASR 的监听模式 (全局变量 listening_for_wake_up)
        global listening_for_wake_up
        if self.state == 'listening_for_wake_up':
            listening_for_wake_up = True
            rospy.loginfo("ASR set to listen for wake-up word.")
        else:
            listening_for_wake_up = False
            rospy.loginfo("ASR set to listen for continuous speech.")

        # 重置与旧状态相关的子状态标志和计时器 (如果需要)
        if new_state != 'waiting_for_command':
            self.waiting_for_command = False
        # if new_state != 'handling_fall_response' and new_state != 'waiting_for_call_request':
        #     self.waiting_for_fall_response = False
            # if self.fall_response_timer is not None:
            #     self.fall_response_timer.cancel()
            # self.fall_response_timer = None
            # self.fall_no_response_count = 0 # 重置摔倒计数
        if new_state != 'waiting_for_call_request':
            self.waiting_for_call_request = False
            if self.call_request_timer is not None:
                self.call_request_timer.cancel()
            self.call_request_timer = None

        # 清空累积的文本，避免跨状态干扰
        global full_text
        full_text = ""


def signal_handler(sig, frame):
    print('Ctrl+C pressed, stopping recording and translation...')
    if 'recognition' in globals():
        recognition.stop()
    if stream and stream.is_active():
        stream.stop_stream()
        stream.close()
    if mic: # Terminate PyAudio instance
        mic.terminate()
    sys.exit(0)

if __name__ == '__main__':
    rospy.init_node('voice_interaction_node')
    keyword_pub = rospy.Publisher('/voice_keyword', String, queue_size=10)
    handler = VoiceInteractionHandler(keyword_pub)
    rospy.Subscriber('/mqtt_data', String, handler.fall_callback)
    

    # 初始化 ASR Recognition 实例
    recognition = TranslationRecognizerRealtime(
        model="gummy-realtime-v1",
        format=format_pcm,
        sample_rate=sample_rate,
        transcription_enabled=True,  # 启用转录
        translation_enabled=False, # 如果你不需要翻译，可以设置为 False
        callback=handler,
    )

    try:
        recognition.start() # 启动 ASR 识别
        signal.signal(signal.SIGINT, signal_handler)
        print(f"等待唤醒词 '{wake_up_word}'...")

        # 主循环，持续读取音频并发送给 ASR
        while not rospy.is_shutdown():
            if stream:
                try:
                    # 从麦克风读取音频数据
                    data = stream.read(block_size, exception_on_overflow=False)
                    # 将音频数据发送给 ASR 进行识别
                    recognition.send_audio_frame(data)
                except OSError as e:
                    if e.errno == -9999:
                        rospy.logerr("音频输入超时，正在尝试重新初始化...")
                        # 发生超时时，尝试重新初始化音频流
                        if stream:
                            stream.stop_stream()
                            stream.close()
                        if mic:
                            mic.terminate()
                        mic = pyaudio.PyAudio()
                        stream = mic.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True
                        )
                    else:
                        rospy.logerr(f"发生 OSError: {e}")
                        break # 其他 OSError 退出循环
                except Exception as e:
                    rospy.logerr(f"发生未知异常: {e}")
                    break # 其他异常退出循环
            else:
                # 如果音频流不可用，等待或退出
                rospy.logwarn("音频流不可用，等待...")
                time.sleep(1) # 等待一段时间再检查
                # break # 或者直接退出循环

    finally:
        # 程序退出前停止 ASR 和清理资源
        print("Shutting down...")
        if 'recognition' in globals() and recognition:
            recognition.stop()
        if stream and stream.is_active():
            stream.stop_stream()
            stream.close()
        if mic:
            mic.terminate()
        rospy.signal_shutdown("Program finished or interrupted")
