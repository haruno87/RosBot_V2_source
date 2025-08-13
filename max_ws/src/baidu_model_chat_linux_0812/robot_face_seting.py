import requests
localhost="192.168.1.18"
def set_robot_expression(expression_type, host=localhost, port=8080):
    """
    设置机器人表情的独立函数
    参数:
        expression_type: 表情类型 ('blink', 'sleep', 'wake', 'listen')
        host: 服务主机地址 (默认localhost)
        port: 服务端口 (默认8080)
    返回:
        服务器响应文本 (如 "ok: listen")
    异常:
        ValueError: 当传入无效的表情类型时
        ConnectionError: 当连接服务器失败时
    """
    valid_expressions = {'blink', 'sleep', 'wake', 'listen'}
    if expression_type not in valid_expressions:
        print(f"无效的表情类型，请使用以下之一: {valid_expressions}")
    try:
        response = requests.get(
            f"http://{host}:{port}/set",
            params={"expression": expression_type},
            timeout=1  # 5秒超时
        )
        response.raise_for_status()
        print("设置表情监听模式成功")
    except requests.exceptions.RequestException as e:
        print(f"无法连接到机器人服务: {str(e)}")


# 使用示例
if __name__ == "__main__":
    # 设置为聆听状态
    print(set_robot_expression("blink"))  
    
