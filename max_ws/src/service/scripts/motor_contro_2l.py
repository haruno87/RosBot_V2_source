#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import threading
import queue
import select
from std_msgs.msg import Int32
# ROS相关导入
import rospy
from geometry_msgs.msg import Twist
import math


# --- 全局变量 ---
# 通信器实例
usb0_communicator = None
usb1_communicator = None

# --- 机器人物理参数 (建议作为ROS参数加载) ---
WHEEL_BASE = 0.30  # 轮距 (米)
WHEEL_RADIUS = 0.05 # 轮径 (米)

# --- 运动学常数 ---
# 从 m/s 转换为 RPM 的转换系数
# RPM = (m/s) * (60 s/min) / (circumference_m/rev)
MPS_TO_RPM_FACTOR = 60.0 / (2 * math.pi * WHEEL_RADIUS)

# --- 控制参数 ---
# cmd_vel 消息处理频率限制
CMD_VEL_FREQ = 20.0  # 提高频率以获得更平滑的控制
MIN_CMD_VEL_INTERVAL = 1.0 / CMD_VEL_FREQ
last_cmd_vel_time = 0

# 速度限制
MAX_LINEAR_SPEED = 0.5   # m/s
MAX_ANGULAR_SPEED = 1.0   # rad/s (适当增加角速度限制以获得更好的转弯性能)

# (其余部分代码保持不变... 心跳包, CRC计算等)
# ...
# ... (此处省略未修改的代码，以保持简洁) ...
# ...

# CRC计算表 (保持不变)
aucCRCHi = [
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
    0x00, 0xC1, 0x81, 0x40
]

aucCRCLo = [
    0x00, 0xC0, 0xC1, 0x01, 0xC3, 0x03, 0x02, 0xC2, 0xC6, 0x06, 0x07, 0xC7,
    0x05, 0xC5, 0xC4, 0x04, 0xCC, 0x0C, 0x0D, 0xCD, 0x0F, 0xCF, 0xCE, 0x0E,
    0x0A, 0xCA, 0xCB, 0x0B, 0xC9, 0x09, 0x08, 0xC8, 0xD8, 0x18, 0x19, 0xD9,
    0x1B, 0xDB, 0xDA, 0x1A, 0x1E, 0xDE, 0xDF, 0x1F, 0xDD, 0x1D, 0x1C, 0xDC,
    0x14, 0xD4, 0xD5, 0x15, 0xD7, 0x17, 0x16, 0xD6, 0xD2, 0x12, 0x13, 0xD3,
    0x11, 0xD1, 0xD0, 0x10, 0xF0, 0x30, 0x31, 0xF1, 0x33, 0xF3, 0xF2, 0x32,
    0x36, 0xF6, 0xF7, 0x37, 0xF5, 0x35, 0x34, 0xF4, 0x3C, 0xFC, 0xFD, 0x3D,
    0xFF, 0x3F, 0x3E, 0xFE, 0xFA, 0x3A, 0x3B, 0xFB, 0x39, 0xF9, 0xF8, 0x38,
    0x28, 0xE8, 0xE9, 0x29, 0xEB, 0x2B, 0x2A, 0xEA, 0xEE, 0x2E, 0x2F, 0xEF,
    0x2D, 0xED, 0xEC, 0x2C, 0xE4, 0x24, 0x25, 0xE5, 0x27, 0xE7, 0xE6, 0x26,
    0x22, 0xE2, 0xE3, 0x23, 0xE1, 0x21, 0x20, 0xE0, 0xA0, 0x60, 0x61, 0xA1,
    0x63, 0xA3, 0xA2, 0x62, 0x66, 0xA6, 0xA7, 0x67, 0xA5, 0x65, 0x64, 0xA4,
    0x6C, 0xAC, 0xAD, 0x6D, 0xAF, 0x6F, 0x6E, 0xAE, 0xAA, 0x6A, 0x6B, 0xAB,
    0x69, 0xA9, 0xA8, 0x68, 0x78, 0xB8, 0xB9, 0x79, 0xBB, 0x7B, 0x7A, 0xBA,
    0xBE, 0x7E, 0x7F, 0xBF, 0x7D, 0xBD, 0xBC, 0x7C, 0xB4, 0x74, 0x75, 0xB5,
    0x77, 0xB7, 0xB6, 0x76, 0x72, 0xB2, 0xB3, 0x73, 0xB1, 0x71, 0x70, 0xB0,
    0x50, 0x90, 0x91, 0x51, 0x93, 0x53, 0x52, 0x92, 0x96, 0x56, 0x57, 0x97,
    0x55, 0x95, 0x94, 0x54, 0x9C, 0x5C, 0x5D, 0x9D, 0x5F, 0x9F, 0x9E, 0x5E,
    0x5A, 0x9A, 0x9B, 0x5B, 0x99, 0x59, 0x58, 0x98, 0x88, 0x48, 0x49, 0x89,
    0x4B, 0x8B, 0x8A, 0x4A, 0x4E, 0x8E, 0x8F, 0x4F, 0x8D, 0x4D, 0x4C, 0x8C,
    0x44, 0x84, 0x85, 0x45, 0x87, 0x47, 0x46, 0x86, 0x82, 0x42, 0x43, 0x83,
    0x41, 0x81, 0x80, 0x40
]

def usMBCRC16(pucFrame, usLen):
    ucCRCHi = 0xFF
    ucCRCLo = 0xFF
    iIndex = 0

    for i in range(usLen):
        iIndex = ucCRCLo ^ pucFrame[i]
        ucCRCLo = ucCRCHi ^ aucCRCHi[iIndex]
        ucCRCHi = aucCRCLo[iIndex]

    return (ucCRCHi << 8) | ucCRCLo

def create_speed_packet(speed_rpm):
    erpm = int(speed_rpm * 4)
    erpm_hex = erpm.to_bytes(4, byteorder='big', signed=True)
    packet = bytearray.fromhex('01 10 17 73 00 02 04')
    packet.extend(erpm_hex)
    crc = usMBCRC16(packet, len(packet))
    packet.extend(crc.to_bytes(2, byteorder='little'))
    return bytes(packet)

class USBCommunicator:
    # ... (USBCommunicator 类保持不变)
    def __init__(self, port):
        
        self.port = port
        self.ser = None
        self.running = False
        self.thread = None
        self.motor_speed = 0  # 当前通信器所控制电机的速度值 (rpm)
        self.lock = threading.Lock()  # 用于线程安全地访问电机速度值
        self.reconnection_delay = 1  # 重连尝试之间的延迟（秒）
        self.max_reconnection_attempts = -1 # 最大重连尝试次数，-1表示无限次

    def connect(self):
        """
        尝试连接到串口
        :return: 连接成功返回True，否则返回False
        """
        try:
            self.ser = serial.Serial(self.port, 115200, timeout=1)
            rospy.loginfo(f"已连接到 {self.port}")
            self.ser.flushInput()
            self.ser.flushOutput()
            return True
        except serial.SerialException as e:
            rospy.logwarn(f"连接到 {self.port} 时串口错误: {str(e)}")
            return False
        except Exception as e:
            rospy.logerr(f"连接到 {self.port} 时发生未知错误: {str(e)}")
            return False

    def disconnect(self):
        """
        断开串口连接
        """
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                rospy.loginfo(f"已关闭 {self.port}")
            except Exception as e:
                rospy.logerr(f"关闭 {self.port} 时出错: {str(e)}")
            self.ser = None

    def send_data(self, data):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(data)
                return True
            except serial.SerialException as e:
                rospy.logwarn(f"向 {self.port} 发送数据时串口错误: {str(e)}")
                return False
            except Exception as e:
                rospy.logerr(f"向 {self.port} 发送数据时发生未知错误: {str(e)}")
                return False
        return False

    def read_data(self):
        if self.ser and self.ser.is_open and self.ser.in_waiting > 0:
            try:
                response = self.ser.read(self.ser.in_waiting)
                return response
            except serial.SerialException as e:
                rospy.logwarn(f"从 {self.port} 读取数据时串口错误: {str(e)}")
            except Exception as e:
                rospy.logerr(f"从 {self.port} 读取数据时发生未知错误: {str(e)}")
        return None

    def run(self):
        self.running = True
        cached_motor_speed = 0
        
        # ... (run方法内部逻辑保持不变)
        # 预先获取锁外的电机速度值，减少锁的使用频率
        cached_motor_speed = 0
        
        while self.running:
            # 尝试连接，如果失败则进入重连循环
            if not self.ser or not self.ser.is_open:
                rospy.loginfo(f"尝试连接到 {self.port}...")
                connected = False
                attempts = 0
                while self.running and not connected:
                    connected = self.connect()
                    if not connected:
                        attempts += 1
                        if self.max_reconnection_attempts != -1 and attempts >= self.max_reconnection_attempts:
                            rospy.logerr(f"达到 {self.port} 的最大重连尝试次数，停止重连。")
                            self.running = False # 停止线程
                            break
                        rospy.logwarn(f"无法连接到 {self.port}，{self.reconnection_delay}秒后重试...")
                        # 使用更短的休眠时间以提高响应性
                        time.sleep(self.reconnection_delay * 0.1)  # 更频繁地检查running状态
                
                if not self.running: # 如果在重连过程中被停止，则退出
                    break

                # 连接成功后，重置状态机变量
                last_send_time = 0
                waiting_for_response = False
                response_received = False
                last_packet_time = 0
                packet_index = 0
                rospy.loginfo(f"{self.port} 连接成功，开始通信。")

            try:
                current_time = time.time()
                
                # 检查是否有数据可读 (非阻塞)
                response = self.read_data()
                if response:
                    response_received = True
                    waiting_for_response = False
                
                # 如果还没有收到初始响应，则发送初始数据包
                if not response_received:
                    # 控制发送初始数据的频率 (每500ms)
                    if current_time - last_send_time >= 0.5:
                        if not waiting_for_response:
                            # 发送初始数据
                            if self.send_data(bytes.fromhex('01 04 13 88 00 01 B5 64')):
                                waiting_for_response = True
                                last_send_time = current_time
                else:
                    # 已经收到初始响应，开始发送数据包序列
                    # 控制每秒发送9个数据包
                    if current_time - last_packet_time >= 1.0/9.0:
                        # 生成要发送的数据包
                        if packet_index == 0 or packet_index == 3 or packet_index == 6:
                            # 心跳包 (第1, 4, 7包)
                            heartbeat_idx = (packet_index // 3) % len(heartbeat_packets)
                            self.send_data(heartbeat_packets[heartbeat_idx])
                        elif packet_index == 1:
                            # 速度模式设置包 (第2包)
                            self.send_data(speed_mode_packet)
                        else:
                            # 速度值设置包 (第3, 5, 6, 8, 9包)
                            with self.lock:
                                if cached_motor_speed != self.motor_speed:
                                    cached_motor_speed = self.motor_speed
                            speed_packet = create_speed_packet(cached_motor_speed)
                            self.send_data(speed_packet)
                        
                        packet_index += 1
                        last_packet_time = current_time
                        
                        if packet_index >= 9:
                            packet_index = 0
                
                next_packet_time = last_packet_time + 1.0/9.0
                sleep_time = max(0.0001, min(0.001, next_packet_time - time.time()))
                time.sleep(sleep_time)

            except serial.SerialException as e:
                rospy.logwarn(f"在 {self.port} 线程中发生串口错误: {str(e)}")
                self.disconnect()
            except Exception as e:
                rospy.logerr(f"在 {self.port} 线程中发生未预期错误: {str(e)}")
                self.disconnect()

        self.disconnect()

    def start(self):
        if not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self.run, daemon=True)
            self.thread.start()
            rospy.loginfo(f"已启动 {self.port} 线程")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                rospy.logwarn(f"警告: {self.port} 线程在停止时未能及时响应。")
        rospy.loginfo(f"已停止 {self.port} 线程")
    
    def set_motor_speed(self, speed):
        with self.lock:
            self.motor_speed = speed

def key_callback(key_msg, usb0_communicator, usb1_communicator):
    # ... (key_callback 保持不变)
    key_val = key_msg.data
    
    left_motor_speed = 0
    right_motor_speed = 0

    if key_val == 1:
        left_motor_speed = -150
        right_motor_speed = 150
    elif key_val == 2:
        left_motor_speed = 150
        right_motor_speed = 150
    elif key_val == 3:
        left_motor_speed = -150
        right_motor_speed = -150
    elif key_val == 4:
        left_motor_speed = 150
        right_motor_speed = -150
    elif key_val == 5:
        left_motor_speed = 0
        right_motor_speed = 0

    usb0_communicator.set_motor_speed(left_motor_speed)
    usb1_communicator.set_motor_speed(right_motor_speed)

# ==============================================================================
# ======================  核心修改: CMD_VEL 回调函数  ===========================
# ==============================================================================
def cmd_vel_callback(msg):
    """
    接收 /cmd_vel 消息并将其转换为左右轮的RPM指令
    """
    global usb0_communicator, usb1_communicator, last_cmd_vel_time

    # 1. 频率限制: 防止过于频繁地处理消息
    current_time = time.time()
    if current_time - last_cmd_vel_time < MIN_CMD_VEL_INTERVAL:
        return
    last_cmd_vel_time = current_time

    # 2. 提取并限制速度: 确保速度在安全范围内
    vx = msg.linear.x
    wz = msg.angular.z
    
    vx = max(min(vx, MAX_LINEAR_SPEED), -MAX_LINEAR_SPEED)
    wz = max(min(wz, MAX_ANGULAR_SPEED), -MAX_ANGULAR_SPEED)

    # 3. 运动学逆解: 计算每个轮子需要的线速度 (m/s)
    #    这是标准差速驱动模型，计算结果带有方向（正负号）
    left_mps = vx - (wz * WHEEL_BASE / 2.0)
    right_mps = vx + (wz * WHEEL_BASE / 2.0)

    # 4. 单位转换: 将线速度 (m/s) 转换为电机转速 (RPM)
    left_rpm = left_mps * MPS_TO_RPM_FACTOR
    right_rpm = right_mps * MPS_TO_RPM_FACTOR

    # 5. 发送指令到电机:
    #    根据 key_callback 的测试，我们知道左轮(usb0)的电机方向是反的。
    #    所以我们需要将计算出的左轮RPM值取反。
    #    右轮(usb1)方向是标准的，直接发送计算值。
    #    这个逻辑现在可以正确处理前进/后退和转向。
    final_left_rpm = -left_rpm
    final_right_rpm = right_rpm
    
    usb0_communicator.set_motor_speed(final_left_rpm)
    usb1_communicator.set_motor_speed(final_right_rpm)

    # 6. 【重要】添加日志打印，用于调试
    #    取消下面的注释，可以实时看到计算过程，非常有助于调试！
    # rospy.loginfo(f"cmd_vel[vx:{vx:.2f}, wz:{wz:.2f}] -> "
    #               f"RPM[L:{left_rpm:.0f}, R:{right_rpm:.0f}] -> "
    #               f"Sent[L:{final_left_rpm:.0f}, R:{final_right_rpm:.0f}]")


def main():
    global usb0_communicator, usb1_communicator
    rospy.init_node('motor_control_node', anonymous=True)

    # 从ROS参数服务器获取参数，如果未设置则使用默认值
    # 这样可以在launch文件中轻松配置，而无需修改代码
    global WHEEL_BASE, WHEEL_RADIUS, MPS_TO_RPM_FACTOR, MAX_LINEAR_SPEED, MAX_ANGULAR_SPEED
    WHEEL_BASE = rospy.get_param('~wheel_base', 0.30)
    WHEEL_RADIUS = rospy.get_param('~wheel_radius', 0.05)
    MAX_LINEAR_SPEED = rospy.get_param('~max_linear_speed', 0.5)
    MAX_ANGULAR_SPEED = rospy.get_param('~max_angular_speed', 1.0)
    
    # 根据获取到的参数重新计算转换系数
    MPS_TO_RPM_FACTOR = 60.0 / (2 * math.pi * WHEEL_RADIUS)

    rospy.loginfo("Motor node started with parameters:")
    rospy.loginfo(f"  wheel_base: {WHEEL_BASE} m")
    rospy.loginfo(f"  wheel_radius: {WHEEL_RADIUS} m")
    rospy.loginfo(f"  max_linear_speed: {MAX_LINEAR_SPEED} m/s")
    rospy.loginfo(f"  max_angular_speed: {MAX_ANGULAR_SPEED} rad/s")

    # 初始化并启动通信器
    usb0_port = rospy.get_param('~usb0_port', '/dev/ttyUSB0')
    usb1_port = rospy.get_param('~usb1_port', '/dev/ttyUSB1')
    usb0_communicator = USBCommunicator(usb0_port)
    usb1_communicator = USBCommunicator(usb1_port)
    
    usb0_communicator.start()
    usb1_communicator.start()
    
    # 设置订阅者
    rospy.Subscriber('key_msg', Int32, lambda msg: key_callback(msg, usb0_communicator, usb1_communicator))
    rospy.Subscriber('/cmd_vel', Twist, cmd_vel_callback)

    rospy.loginfo("Motor node is running and waiting for commands...")

    try:
        rospy.spin()
    except (KeyboardInterrupt, rospy.ROSInterruptException):
        rospy.loginfo("Shutting down motor node...")
    finally:
        usb0_communicator.stop()
        usb1_communicator.stop()
        rospy.loginfo("All communication threads stopped. Program exiting.")

if __name__ == "__main__":
    # 心跳包和速度模式包定义
    heartbeat_packets = [
        bytes.fromhex('01 06 17 70 00 01 4C 65'),
        bytes.fromhex('01 06 17 70 00 02 0C 64'),
        bytes.fromhex('01 06 17 70 00 03 CD A4')
    ]
    speed_mode_packet = bytes.fromhex('01 06 17 71 00 01 1D A5')
    main()
