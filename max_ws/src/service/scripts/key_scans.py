#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import sys, select, termios, tty
import signal
from std_msgs.msg import Int32  # 使用标准消息类型

settings = None

def getKey():
    """
    捕获键盘输入，并立即返回按下的键。
    使用非阻塞模式。
    """
    tty.setraw(sys.stdin.fileno())  # 设置终端为原始模式
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)  # 非阻塞等待输入，超时0.1秒

    if rlist:
        key = sys.stdin.read(1)  # 读取一个字符
    else:
        key = '0'  # 没有按键按下时返回'0'

    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)  # 恢复终端设置
    return key


def signal_handler(sig, frame):
    # 恢复终端设置
    if settings:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    rospy.loginfo("程序已通过 Ctrl+C 中断，恢复终端设置。")
    sys.exit(0)


if __name__ == "__main__":
    # 保存原始终端设置
    settings = termios.tcgetattr(sys.stdin)

    # 初始化ROS节点
    rospy.init_node("keyboard_control_node")

    # 创建 Int32 消息发布器，发布到 key_msg 话题
    key_pub = rospy.Publisher("key_msg", Int32, queue_size=10)

    # 初始化 Int32 消息
    key_msg = Int32()
    key_msg.data = 0  # 初始状态为 0 (空闲)

    # 注册信号处理函数，确保Ctrl+C时终端设置被恢复
    signal.signal(signal.SIGINT, signal_handler)

    rospy.loginfo("键盘控制节点已启动。")
    rospy.loginfo("使用 'W/w' (前进), 'A/a' (左转), 'S/s' (后退), 'D/d' (右转), 'X/x' (停止)。")
    rospy.loginfo("按 'q' 键退出程序。")  # 更新提示信息

    try:
        while not rospy.is_shutdown():
            key = getKey()

            # 添加 'q' 键退出逻辑
            if key == 'q':
                rospy.loginfo("检测到 'q' 键，程序即将退出。")
                break  # 退出循环

            # 根据按键设置 key_val
            if key in ['W', 'w']:
                key_msg.data = 1
            elif key in ['A', 'a']:
                key_msg.data = 2
            elif key in ['D', 'd']:
                key_msg.data = 3
            elif key in ['S', 's']:
                key_msg.data = 4
            elif key in ['X', 'x']:
                key_msg.data = 5
            elif key == '0':
                key_msg.data = 0
            else:
                # 对于其他未知按键，发送 0 表示无效或空闲
                key_msg.data = 0

            # 发布 key_msg 消息
            key_pub.publish(key_msg)

            # 可选：打印当前按键值（用于调试）
            # rospy.loginfo("Published key_val: %d, Key Pressed: %r", key_msg.data, key)

    except rospy.ROSInterruptException:
        rospy.loginfo("ROS 被中断。")
    finally:
        # 确保程序退出时，终端设置被恢复
        if settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        rospy.loginfo("键盘控制节点已关闭。")
        sys.exit(0)