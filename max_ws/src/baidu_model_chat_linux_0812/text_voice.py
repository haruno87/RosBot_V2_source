import base64
# import urllib
import requests
import json
import os
from playaudio import play_wav_file

API_KEY = "rwgTQFiPgx5jFfRmsvThws1X"
SECRET_KEY = "PBiy5jZ9tJwlYZ2xQ8X4YCoc7laGPmnV"

def text_to_voice(text, filename="./output.wav"):

    # 请求语音合成
    url = "https://tsn.baidu.com/text2audio"
    
    payload='tex='+text+'&tok='+ get_access_token() +'&cuid=mM7DUU9MTZQwmM8JG8NDGAzL6FbEED2r&ctp=1&lan=zh&spd=5&pit=5&vol=6&per=5&aue=6'


    response = requests.request("POST",url, data=payload.encode("utf-8"),timeout=3)
    content_type = response.headers.get("content-type", "")

    if content_type == "audio/wav":
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"语音合成成功！保存为: {filename}")
        return filename

    else:
        print("语音合成失败！错误信息:", response.text)
        return None

def text_to_voice_play(text, filename="output.wav"):

    # 请求语音合成
    url = "https://tsn.baidu.com/text2audio"
    
    payload='tex='+text+'&tok='+ get_access_token() +'&cuid=mM7DUU9MTZQwmM8JG8NDGAzL6FbEED2r&ctp=1&lan=zh&spd=5&pit=5&vol=6&per=5&aue=6'


    response = requests.request("POST",url, data=payload.encode("utf-8"))
    content_type = response.headers.get("content-type", "")

    if content_type == "audio/wav":
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"语音合成成功！保存为: {filename}")
        play_wav_file(filename)
        return filename

    else:
        print("语音合成失败！错误信息:", response.text)
        return None


def voice_to_text(voice_file_path,is_continue=False):
    voice_encoded = get_file_content_as_base64(voice_file_path, urlencoded=False)   
    url = "https://vop.baidu.com/pro_api"
    file_size = os.path.getsize(voice_file_path)
    # speech 可以通过 get_file_content_as_base64("C:\fakepath\output.wav",False) 方法获取
    payload = json.dumps({
        "format": "wav",
        "rate": 16000,
        "channel": 1,
        "cuid": "leIuQ3GiNpowo7vYEv6Zrg5EjDdpcQ7J",
        "dev_pid": 80001,
        "speech": voice_encoded,
        "len": file_size,
        "token": get_access_token()
    }, ensure_ascii=False)
    headers = {
        'Accept': 'application/json'
    }
    
    if not is_continue:
        response = requests.request("POST", url, headers=headers, data=payload.encode("utf-8"))
        result_list = response.json().get("result", [""])
        
        # 提取第一个元素，如果列表非空，否则返回空字符串
        text = result_list[0] if result_list else ""
        print(text)
        return text
    
    else:
        try:
            response = requests.request("POST", url, headers=headers, data=payload.encode("utf-8"))
            result_list = response.json().get("result", [""])
            
            # 提取第一个元素，如果列表非空，否则返回空字符串
            text = result_list[0] if result_list else ""
            print("语音转文本"+text)
            return text
        except Exception as e:
            print(f"语音识别失败！错误信息: {str(e)}")
            return ""
    

def get_file_content_as_base64(path, urlencoded=False):
    """
    获取文件base64编码
    :param path: 文件路径
    :param urlencoded: 是否对结果进行urlencoded 
    :return: base64编码信息
    """
    with open(path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf8")
        # if urlencoded:
        #     content = urllib.parse.quote_plus(content)
    return content

def get_access_token():
    """
    使用 AK，SK 生成鉴权签名（Access Token）
    :return: access_token，或是None(如果错误)
    """
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {"grant_type": "client_credentials", "client_id": API_KEY, "client_secret": SECRET_KEY}
    return str(requests.post(url, params=params).json().get("access_token"))

if __name__ == '__main__':
    voice_to_text("output.wav")  # 替换为实际的音频文件路径
