import sys
from typing import List
from alibabacloud_ccc20200701.client import Client as CCC20200701Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_ccc20200701 import models as ccc20200701_models
from alibabacloud_tea_util import models as util_models

import urllib
import urllib.request
import hashlib

def create_ccc_client() -> CCC20200701Client:
    """
    创建阿里云呼叫中心客户端
    """
    config = open_api_models.Config(
        access_key_id='',
        access_key_secret='',
    )
    config.endpoint = ''
    return CCC20200701Client(config)

def make_phone_call_base(phone_number: str='13655560751', caller_id: str = '6690594502322717'):
    """
    拨打电话功能
    
    参数:
        phone_number: 要拨打的电话号码
        caller_id: 主叫号码(默认使用示例中的号码)
    """
    client = create_ccc_client()
    
    make_call_request = ccc20200701_models.MakeCallRequest(
        caller=caller_id,          # 主叫号码
        callee=phone_number,       # 被叫号码
        device_id='device',         # 设备ID
        instance_id='demo-1645515438393388'  # 实例ID
    )
    
    runtime = util_models.RuntimeOptions()
    
    try:
        print(f"正在呼叫号码: {phone_number}...")
        response = client.make_call_with_options(make_call_request, runtime)
        print(f"呼叫请求已发送，响应: {response}")
        return True
    except Exception as error:
        print(f"呼叫失败: {error.message}")
        if hasattr(error, 'data') and error.data:
            print(f"建议: {error.data.get('Recommend')}")
        return False

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
        # print(f"短信发送响应代码: {the_page}")
        # 返回发送结果
        print(statusStr.get(the_page, "未知错误"))

    except Exception as e:
        # 捕获异常并返回错误信息
        print(f"发送失败：{str(e)}")        

