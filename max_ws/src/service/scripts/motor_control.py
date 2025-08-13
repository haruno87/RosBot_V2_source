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
from geometry_msgs.msg import Twist, Pose
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
import tf
from tf.transformations import quaternion_from_euler
import math

# --- 全局配置参数 ---
# 备注: 请务必精确测量并填写这些物理参数，它们是里程计精度的基础。
class Config:
    WHEEL_RADIUS = 0.055    # 轮半径 (单位: 米)
    WHEEL_DISTANCE = 0.35       # 轮间距 (单位: 米)
    FUSION_RATIO = 0.9          # IMU融合权重 (0.0-1.0), 越高越相信IMU的角速度
    BASE_COV_POS = 0.01         # 基础位置协方差
    BASE_COV_ORI = 0.03         # 基础朝向协方差
    IMU_TIMEOUT = 1.0           # IMU数据超时 (单位: 秒)

# --- 线程安全的数据共享结构 ---
# 用于在ROS回调线程和里程计计算线程之间安全地传递数据
class RobotState:
    def __init__(self):
        self.lock = threading.RLock()
        self.left_rpm = 0
        self.right_rpm = 0
        self.imu_angular_z = 0.0
        self.last_imu_time = None

    def update_imu(self, angular_z, timestamp):
        with self.lock:
            self.imu_angular_z = angular_z
            self.last_imu_time = timestamp

    def update_motor_speed(self, left_rpm, right_rpm):
        """
        更新电机的物理期望转速 (RPM)。
        这里的RPM值是用于运动学计算的，正值代表前进。
        """
        with self.lock:
            self.left_rpm = left_rpm
            self.right_rpm = right_rpm

    def get_all(self):
        with self.lock:
            return (self.left_rpm, self.right_rpm,
                   self.imu_angular_z, self.last_imu_time)

# --- 全局变量 ---
robot_state = RobotState()
current_pose = Pose()
current_pose.orientation.w = 1.0  # 初始化姿态，单位四元数
prev_time = None

# 全局变量，供回调使用
usb0_communicator = None
usb1_communicator = None

# --- 控制参数 ---
# cmd_vel 消息处理频率限制
# 修改: 调整为9Hz，与底层电机通信协议的9帧/秒保持一致
CMD_VEL_FREQ = 9.0
MIN_CMD_VEL_INTERVAL = 1.0 / CMD_VEL_FREQ
last_cmd_vel_time = 0

# 速度限制 (请根据机器人实际能力调整)
MAX_LINEAR_SPEED = 4.0   # m/s
MAX_ANGULAR_SPEED = 2.0  # rad/s

# 运动学参数 (与Config类保持一致)
WHEEL_BASE = Config.WHEEL_DISTANCE
WHEEL_RADIUS = Config.WHEEL_RADIUS

# 单位转换因子: 从 m/s 到 RPM
# RPM = (V_mps / (2 * π * wheel_radius)) * 60
MPS_TO_RPM_FACTOR = 60 / (2 * math.pi * WHEEL_RADIUS)

# 要发送的数据 (原始示例中的初始数据包)
data_to_send = bytes.fromhex('01 04 13 88 00 01 B5 64')

# 心跳包数据
heartbeat_packets = [
    bytes.fromhex('01 06 17 70 00 01 4C 65'),
    bytes.fromhex('01 06 17 70 00 02 0C 64'),
    bytes.fromhex('01 06 17 70 00 03 CD A4')
]

# 速度模式设置包
speed_mode_packet = bytes.fromhex('01 06 17 71 00 01 1D A5')

# --- CRC计算 (保持不变) ---
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
    0x2D, 0xED, 0xEC, 0x2C, 0xE4, 0x24, 0x25, 0xE5, 0x27, 0E7, 0xE6, 0x26,
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

# --- 新增/修改开始 ---
# 串口配置
baudrate = 115200
timeout = 1
# --- 新增/修改结束 ---

class USBCommunicator:
    def __init__(self, port):
        self.port = port
        self.ser = None
        self.running = False
        self.thread = None
        self.motor_speed = 0
        self.lock = threading.Lock()
        self.reconnection_delay = 1
        self.max_reconnection_attempts = -1

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, baudrate, timeout=timeout)
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
                return self.ser.read(self.ser.in_waiting)
            except serial.SerialException as e:
                rospy.logwarn(f"从 {self.port} 读取数据时串口错误: {str(e)}")
            except Exception as e:
                rospy.logerr(f"从 {self.port} 读取数据时发生未知错误: {str(e)}")
        return None

    def run(self):
        self.running = True
        cached_motor_speed = 0
        while self.running:
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
                            self.running = False
                            break
                        rospy.logwarn(f"无法连接到 {self.port}，{self.reconnection_delay}秒后重试...")
                        time.sleep(self.reconnection_delay)
                if not self.running:
                    break
                last_send_time = 0
                waiting_for_response = False
                response_received = False
                last_packet_time = 0
                packet_index = 0
                rospy.loginfo(f"{self.port} 连接成功，开始通信。")

            try:
                current_time = time.time()
                response = self.read_data()
                if response:
                    response_received = True
                    waiting_for_response = False
                
                if not response_received:
                    if current_time - last_send_time >= 0.5:
                        if not waiting_for_response:
                            if self.send_data(data_to_send):
                                waiting_for_response = True
                                last_send_time = current_time
                else:
                    if current_time - last_packet_time >= 1.0/9.0:
                        if packet_index in [0, 3, 6]:
                            heartbeat_idx = (packet_index // 3) % len(heartbeat_packets)
                            self.send_data(heartbeat_packets[heartbeat_idx])
                        elif packet_index == 1:
                            self.send_data(speed_mode_packet)
                        else:
                            with self.lock:
                                if cached_motor_speed != self.motor_speed:
                                    cached_motor_speed = self.motor_speed
                            speed_packet = create_speed_packet(cached_motor_speed)
                            self.send_data(speed_packet)
                        
                        packet_index = (packet_index + 1) % 9
                        last_packet_time = current_time
                
                time.sleep(0.001)

            except serial.SerialException as e:
                rospy.logerr(f"在 {self.port} 线程中发生串口错误: {str(e)}")
                self.disconnect()
            except Exception as e:
                rospy.logerr(f"在 {self.port} 线程中发生未预期错误: {str(e)}", exc_info=True)
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
            self.thread.join(timeout=2)
            if self.thread.is_alive():
                rospy.logwarn(f"警告: {self.port} 线程在停止时未能及时响应。")
        rospy.loginfo(f"已停止 {self.port} 线程")
    
    def set_motor_speed(self, speed):
        with self.lock:
            self.motor_speed = speed

def key_callback(key_msg, usb0_communicator, usb1_communicator):
    key_val = key_msg.data
    left_motor_cmd = 0
    right_motor_cmd = 0

    if key_val == 1:  # 前进
        left_motor_cmd = -150
        right_motor_cmd = 150
    elif key_val == 2:  # 左转
        left_motor_cmd = -25
        right_motor_cmd = -25
    elif key_val == 3:  # 右转
        left_motor_cmd = 25
        right_motor_cmd = 25
    elif key_val == 4:  # 后退
        left_motor_cmd = 150
        right_motor_cmd = -150
    elif key_val == 5:  # 停止
        left_motor_cmd = 0
        right_motor_cmd = 0

    usb0_communicator.set_motor_speed(left_motor_cmd)  # 左轮电机
    usb1_communicator.set_motor_speed(right_motor_cmd) # 右轮电机
    
    physical_left_rpm = -left_motor_cmd
    physical_right_rpm = right_motor_cmd
    robot_state.update_motor_speed(physical_left_rpm, physical_right_rpm)

def cmd_vel_callback(msg):
    global usb0_communicator, usb1_communicator, last_cmd_vel_time

    current_time = time.time()
    if current_time - last_cmd_vel_time < MIN_CMD_VEL_INTERVAL:
        return
    last_cmd_vel_time = current_time

    vx = max(min(msg.linear.x, MAX_LINEAR_SPEED), -MAX_LINEAR_SPEED)
    wz = max(min(msg.angular.z, MAX_ANGULAR_SPEED), -MAX_ANGULAR_SPEED)

    left_mps = vx - (wz * WHEEL_BASE / 2.0)
    right_mps = vx + (wz * WHEEL_BASE / 2.0)

    left_rpm = int(left_mps * MPS_TO_RPM_FACTOR)
    right_rpm = int(right_mps * MPS_TO_RPM_FACTOR)

    usb0_communicator.set_motor_speed(left_rpm)
    usb1_communicator.set_motor_speed(-right_rpm)
    robot_state.update_motor_speed(left_rpm, right_rpm)

def dynamic_covariance(linear_vel, angular_vel):
    if abs(linear_vel) < 0.05 and abs(angular_vel) < 0.1:
        pos_cov = Config.BASE_COV_POS * 5
        ori_cov = Config.BASE_COV_ORI * 3
    else:
        pos_cov = Config.BASE_COV_POS
        ori_cov = Config.BASE_COV_ORI
    
    return [pos_cov, 0, 0, 0, 0, 0,
            0, pos_cov, 0, 0, 0, 0,
            0, 0, 1e6, 0, 0, 0,
            0, 0, 0, 1e6, 0, 0,
            0, 0, 0, 0, 1e6, 0,
            0, 0, 0, 0, 0, ori_cov]

def imu_callback(msg):
    robot_state.update_imu(msg.angular_velocity.z, rospy.Time.now())

def calculate_odometry(dt):
    global current_pose
    
    left_rpm, right_rpm, imu_angular_z, last_imu_time = robot_state.get_all()
    
    left_ang_vel = left_rpm * 2 * math.pi / 60
    right_ang_vel = right_rpm * 2 * math.pi / 60
    
    left_lin_vel = left_ang_vel * Config.WHEEL_RADIUS
    right_lin_vel = right_ang_vel * Config.WHEEL_RADIUS
    
    wheel_angular_vel = (right_lin_vel - left_lin_vel) / Config.WHEEL_DISTANCE
    
    if last_imu_time is not None and (rospy.Time.now() - last_imu_time).to_sec() < Config.IMU_TIMEOUT:
        final_angular_vel = Config.FUSION_RATIO * imu_angular_z + (1 - Config.FUSION_RATIO) * wheel_angular_vel
    else:
        final_angular_vel = wheel_angular_vel
        # rospy.logwarn_throttle(5, "IMU data timeout, using wheel odometry only for orientation.")

    linear_vel = (right_lin_vel + left_lin_vel) / 2
    
    (roll, pitch, theta) = tf.transformations.euler_from_quaternion(
        [current_pose.orientation.x, current_pose.orientation.y, current_pose.orientation.z, current_pose.orientation.w])
    
    delta_x = linear_vel * math.cos(theta + final_angular_vel * dt / 2.0) * dt # 使用中值法提高精度
    delta_y = linear_vel * math.sin(theta + final_angular_vel * dt / 2.0) * dt
    delta_theta = final_angular_vel * dt
    
    current_pose.position.x += delta_x
    current_pose.position.y += delta_y
    theta += delta_theta
    
    q = quaternion_from_euler(0, 0, theta)
    current_pose.orientation.x = q[0]
    current_pose.orientation.y = q[1]
    current_pose.orientation.z = q[2]
    current_pose.orientation.w = q[3]
    
    return linear_vel, final_angular_vel

def publish_odometry_and_tf(odom_pub, odom_broadcaster):
    global prev_time
    current_time = rospy.Time.now()
    
    if prev_time is None:
        prev_time = current_time
        robot_state.last_imu_time = current_time
        return
    
    dt = (current_time - prev_time).to_sec()
    if dt <= 0:
        rospy.logwarn("Time delta is zero or negative, skipping odometry calculation.")
        return

    linear_vel, angular_vel = calculate_odometry(dt)
    
    odom = Odometry()
    odom.header.stamp = current_time
    odom.header.frame_id = "odom"
    # 修改: child_frame_id 统一为 base_link，这是ROS的标准做法
    odom.child_frame_id = "laser"
    
    odom.pose.pose = current_pose
    odom.pose.covariance = dynamic_covariance(linear_vel, angular_vel)
    
    odom.twist.twist.linear.x = linear_vel
    odom.twist.twist.angular.z = angular_vel
    odom.twist.covariance = odom.pose.covariance

    odom_pub.publish(odom)
    
    # 修改: TF发布 odom -> base_link 的变换
    # 备注: 不再发布 base_link -> laser 的静态变换。
    #       请确保所有其他配置文件(costmap, amcl)都使用 base_link 作为 robot_base_frame。
    #       如果 laser 和 base_link 之间存在物理偏移，应在launch文件中使用 static_transform_publisher 单独发布。
    odom_broadcaster.sendTransform(
        (current_pose.position.x, current_pose.position.y, 0),
        (current_pose.orientation.x, current_pose.orientation.y, 
         current_pose.orientation.z, current_pose.orientation.w),
        current_time,
        "laser",  # 子坐标系
        "odom"        # 父坐标系
    )
    
    prev_time = current_time

def main():
    global usb0_communicator, usb1_communicator
    rospy.init_node('motor_control_node', anonymous=True)

    # --- 初始化串口通信 ---
    # /dev/Motor1 对应左轮电机 (usb0)
    # /dev/Motor2 对应右轮电机 (usb1)
    usb0_communicator = USBCommunicator('/dev/Motor1')
    usb1_communicator = USBCommunicator('/dev/Motor2')
    
    usb0_communicator.start()
    usb1_communicator.start()
    
    # --- ROS接口 ---
    odom_pub = rospy.Publisher("odom", Odometry, queue_size=50)
    odom_broadcaster = tf.TransformBroadcaster()
    
    rospy.Subscriber('key_msg', Int32, lambda msg: key_callback(msg, usb0_communicator, usb1_communicator))
    rospy.Subscriber('/cmd_vel', Twist, cmd_vel_callback)
    rospy.Subscriber("/imu/data", Imu, imu_callback)
    
    rospy.loginfo("Motor control node started. Publishing to /odom and odom->base_link TF.")
    
    # 修改: 提高主循环频率，以提供更高频的里程计和TF
    rate = rospy.Rate(50)

    try:
        while not rospy.is_shutdown():
            publish_odometry_and_tf(odom_pub, odom_broadcaster)
            rate.sleep()
            
    except (rospy.ROSInterruptException, KeyboardInterrupt):
        rospy.loginfo("节点被中断，正在停止...")
    finally:
        usb0_communicator.stop()
        usb1_communicator.stop()
        rospy.loginfo("所有通信已完成，程序退出。")

if __name__ == "__main__":
    main()
