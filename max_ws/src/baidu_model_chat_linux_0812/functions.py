#!/usr/bin/env python3
import json
import base64
import requests
import threading
import rospy
from std_msgs.msg import String
from text_voice import text_to_voice_play
from call_sms import make_phone_call_base, send_sms
from playaudio import play_wav_file, play_wav_file_async

# 用于跟踪所有创建的线程
active_threads = []

CONFIG1 = {
    "api_key": "",
    "appid": "app-mRnuUVg8",
    "model": "ernie-4.5-vl-28b-a3b"
}
CONFIG = {
    "api_key": "",
    "appid": "app-mRnuUVg8",
    "model": "ernie-lite-pro-128k"
}

# ----------------------------------------------------
# ROS 相关代码
# ----------------------------------------------------
# 在模块级别初始化 ROS 节点，确保只执行一次
try:
    rospy.init_node('tool_call_handler', anonymous=True)
    rospy.loginfo("ROS节点 'tool_call_handler' 已初始化。")
except rospy.exceptions.ROSInitException:
    # 如果节点已经被初始化，就跳过
    rospy.logwarn("ROS节点已在其他地方初始化，跳过。")

class RobotPublisher:
    """
    负责管理 ROS 话题发布者，并提供统一的接口来发布消息。
    """
    def __init__(self):
        # 创建 Publisher
        self.keyword_pub = rospy.Publisher('/voice_keyword', String, queue_size=10)
        rospy.loginfo("ROS Publisher '/voice_keyword' 已创建。")

    def publish_keyword(self, keyword):
        """将关键词封装成 JSON 并发布到 /voice_keyword 话题。"""
        try:
            message_dict = {"keyword": keyword}
            json_to_send = json.dumps(message_dict)
            self.keyword_pub.publish(json_to_send)
            rospy.loginfo(f"已向 /voice_keyword 话题发布 JSON: {json_to_send}")
        except Exception as e:
            rospy.logerr(f"发布关键词 '{keyword}' 时出错: {str(e)}")

# 创建一个全局的 RobotPublisher 实例
# 这样所有函数都可以直接使用它
try:
    robot_publisher = RobotPublisher()
except Exception as e:
    rospy.logerr(f"无法创建 RobotPublisher 实例: {e}")
    robot_publisher = None


def get_weather_info(cast:dict) -> str:
    """获取指定天的天气信息文本"""
    return (f"白天{cast['dayweather']}，温度{cast['daytemp']}摄氏度，风向：{cast['daywind']}，风力：{cast['daypower']}；"
            f"夜晚{cast['nightweather']}，温度{cast['nighttemp']}摄氏度，风向：{cast['nightwind']}，风力：{cast['nightpower']}")

def encode_image_to_base64(image_path, urlencoded=False):
    """将图片编码为base64"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"图片编码错误: {e}")
        return None

def get_chat_response(messages, tools=None, Config=CONFIG):
    """获取AI响应，支持工具调用"""
    payload = {
        "model": Config["model"],
        "messages": messages,
        "stream": False,
        "max_tokens": 150,
    }
    
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    
    headers = {
        'Authorization': f'Bearer {Config["api_key"]}',
        'appid': Config["appid"],
        'Content-Type': 'application/json'
    }
    
    response = requests.post(
        "https://qianfan.baidubce.com/v2/chat/completions",
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8")
    )
    # print(response)
    return response.json()


def get_image(messages, arguments, Config):
    """处理图片分析的工具调用"""
    try:
        image_path = "./captured_image.jpg"  # 调用拍照函数获取照片路径
        image_encoded = encode_image_to_base64(image_path)
        question = arguments.get("question", "")+"(回答50字以内，要求完整句子)"
        
        user_message_image = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": question
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/jpg;base64," + image_encoded
                    }
                }
            ]
        }
        messages.append(user_message_image)
    
        response = get_chat_response(messages, tools=None, Config=Config)
        print("图片分析结果:", response)
        return response
    except Exception as e:
        return f"图片分析出错: {str(e)}"


def only_text(messages, arguments, Config):
    """处理仅文本的工具调用"""
    question = arguments.get("question", "")+"(回答50字以内，要求完整句子)"
    
    user_message_text = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": question
            }
        ]
    }
    
    messages.append(user_message_text)
    response = get_chat_response(messages, tools=None, Config=Config)
    return response

#伪函数
def go_to_location(location):
    """将LLM识别的地点映射为内部指令，并发布到ROS话题。"""
    if robot_publisher:
        try:
            rospy.loginfo(f"接收到导航请求，目标地点: '{location}'")
            location_to_command_map = {
                "饮水机": "go to point a",
                "维修台": "go to point b",
                "大桌子": "go to point c",
                "A点": "go to point a",
                "B点": "go to point b",
                "C点": "go to point c",
            }
            command_string = location_to_command_map.get(location)
            if command_string:
                robot_publisher.publish_keyword(command_string)
            else:
                rospy.logwarn(f"无法为地点 '{location}' 找到对应的指令。")
        except Exception as e:
            rospy.logerr(f"执行导航到 {location} 时发生错误: {str(e)}")
    else:
        rospy.logerr("RobotPublisher 未初始化，无法发布话题。")
    
def charge_back(messages):
    """处理回到充电桩的工具调用"""
    print("回到充电桩位置...")

def follow_me(messages):
    """处理开始跟随说话人的工具调用"""
    print("开始跟随说话人...")

def stop_following(messages):
    """处理停止跟随的工具调用"""
    print("停止跟随...")

def make_phone_call(messages, arguments):
    """处理发起电话呼叫的工具调用"""
    phone_number = arguments.get("phone_number", "")
    make_phone_call(phone_number)
    if not phone_number:
        return {"error": "电话号码不能为空"}
    
    print(f"拨打电话: {phone_number}...")

def handle_fall_event(messages):


    # text_to_voice_play("检测到发生摔倒，正在为您拨打电话以及发送短信寻求帮助","handle_fall_event_audio.wav")  # 确保有一个摔倒提示音频文件在当前目录
    play_wav_file("./handle_fall_event_audio.wav")
    print("检测到发生摔倒，正在为您拨打电话以及发送短信寻求帮助")
    send_sms(
            user='kengo_',
            password='12138.aaa',
            phone='13655560751',
            content='【康养机器人】社康请注意，11栋C户疑似发生老人发生摔倒事件！请及时到户处理!门锁密码为：114514。'
    )         # 用户1

    make_phone_call_base()

    """处理摔倒事件的工具调用"""
    print("处理摔倒事件...")

def remember_information(messages, arguments):
    """处理记住信息的工具调用"""
    key = arguments.get("key", "")
    value = arguments.get("value", "")
    
    if not key or not value:
        return {"error": "键和值不能为空"}
    
    print(f"记住信息: {key} = {value}")
    # 这里可以将信息存储到某个数据结构中，供后续使用
    return {"status": "信息已记住"}

def find_item(messages, arguments):
    """处理寻找物品的工具调用"""
    location = arguments.get("location", "")
    item_name = arguments.get("item_name", "")
    
    if not location or not item_name:
        return {"error": "位置和物品名称不能为空"}
    
    print(f"在 {location} 寻找物品: {item_name}...")
    # 这里可以添加实际的寻找逻辑
    go_to_location(messages, {"location": location})
    get_image(messages, {"question": f"请在{location}找一找{item_name}，如果有，请描述它的位置"}, CONFIG1)
    

def get_weather(messages: list, arguments: dict, Config):
    """处理天气查询"""
    try:
        location = arguments['location']
        if not location:
            raise Exception('请提供地点信息')

        # 通过天气API获取指定位置的信息
        api_key = "313da09aeaebdacd799508a49b04c456"  # 正式使用时替换成对应的API KEY
        api_city = location
        api_url = (f"https://restapi.amap.com/v3/weather/weatherInfo?key={api_key}"
                   f"&city={api_city}&extensions=all&output=json")
        response = requests.get(api_url)

        if response.status_code != 200:
            raise Exception(f'天气API请求失败：{response.status_code} {response.text}')

        data = response.json()
        if data['status'] != '1' or data['infocode'] != '10000':
            raise Exception(data['info'])
        if data['count'] == '0':
            raise Exception(f'未找到地点：{location}')

        # 拼接天气文本（现在先把json打印出来）
        # weather_info = json.dumps(data, ensure_ascii=False, indent=4).strip()
        casts = data['forecasts'][0]['casts']
        weather_info = (f"当天天气：{get_weather_info(casts[0])}。\n"
                        f"明天天气：{get_weather_info(casts[1])}。")

        print(f"查询到的天气信息：\n{weather_info}")

        prompt = f"请简要总结一下{location}的天气情况，适当地描述天气并作出评价与建议，注意回复要简短，不要超过50字。以下是当地天气预报信息：\n{weather_info}"

        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
        messages.append(user_message)
        response1 = get_chat_response(messages, tools=None, Config=Config)
        return response1

    except Exception as e:
        print("查询天气出错")
        return f"天气信息查询出错：{e}"



def handle_tool_call(messages, tool_call):
    """处理工具调用"""
    print("处理工具调用:", tool_call)
    function_name = tool_call["function"]["name"]
    arguments = json.loads(tool_call["function"]["arguments"])
    
    if function_name == "get_image":
        playaudio_thread = threading.Thread(
            target=play_wav_file_async,
            args=("./thinking.wav",)  # 确保有一个 wozai.wav 文件在当前目录
        )
        playaudio_thread.start()
        return get_image(messages, arguments, CONFIG1)
    elif function_name == "only_text":
        return only_text(messages, arguments, CONFIG1)
    elif function_name == "go_to_location":
        thread = threading.Thread(target=go_to_location, args=(arguments.get("location"),))
        thread.start()
        active_threads.append(thread)
        text_to_voice_play(f"正在导航到 {arguments.get('location', '未知地点')}","go_to_location.wav")
        return None
    elif function_name == "charge_back":
        return charge_back(messages)
    elif function_name == "follow_me":
        return follow_me(messages)
    elif function_name == "stop_following":     
        return stop_following(messages)
    elif function_name == "make_phone_call":
        return make_phone_call(messages, arguments)     
    elif function_name == "handle_fall_event":
        return handle_fall_event(messages)
    elif function_name == "remember_information":
        return remember_information(messages, arguments)
    elif function_name == "find_item":
        return find_item(messages, arguments)   
    elif function_name == "get_weather":
        playaudio_thread = threading.Thread(
            target=play_wav_file_async,
            args=("./thinking.wav",)  # 确保有一个 wozai.wav 文件在当前目录
        )
        # playaudio_thread.start()
        return get_weather(messages,arguments,CONFIG)
    else:
        return {"error": f"未知的工具调用: {function_name}"}
        