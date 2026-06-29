# RosBot V2 部署与配置指南

## 硬件准备

### 必要硬件

1. **Orange Pi 5 / 树莓派 4B+** (推荐 Orange Pi 5，性能更强)
2. **宇树 Unitree LiDAR 4D** 或 **思岚 RP LiDAR**
3. **WIT IMU 姿态传感器**
4. **USB 摄像头**
5. **USB 麦克风** (阵列麦克风效果更佳)
6. **音箱/喇叭**
7. **差速驱动底盘 + 编码电机**

### 接线指南

| 设备 | 接口 | 备注 |
|------|------|------|
| Unitree LiDAR | USB 3.0 | 需要高速接口 |
| RP LiDAR | USB 2.0 | — |
| WIT IMU | USB/串口 | 波特率 921600 |
| 摄像头 | USB | CSI 亦可 |
| 麦克风 | USB | 免驱 USB 声卡 |
| 电机驱动 | GPIO/串口 | 根据驱动板型号 |

## 系统环境配置

### 1. 安装 ROS Noetic

```bash
# Ubuntu 20.04
sudo sh -c 'echo "deb http://packages.ros.org/ros/ubuntu $(lsb_release -sc) main" > /etc/apt/sources.list.d/ros-latest.list'
curl -s https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -
sudo apt update
sudo apt install ros-noetic-desktop-full
echo "source /opt/ros/noetic/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### 2. 安装系统依赖

```bash
sudo apt update
sudo apt install -y \
    python3-pip python3-dev python3-numpy \
    python3-opencv libopencv-dev \
    portaudio19-dev python3-pyaudio \
    libatlas-base-dev libhdf5-dev \
    ros-noetic-move-base ros-noetic-amcl \
    ros-noetic-octomap-ros ros-noetic-octomap-msgs \
    ros-noetic-pcl-ros ros-noetic-map-server \
    ros-noetic-gmapping ros-noetic-teb-local-planner \
    ros-noetic-dwa-local-planner ros-noetic-global-planner
```

### 3. 安装 Python 依赖

```bash
pip3 install -r requirements.txt
```

### 4. 配置 Snowboy 唤醒词

```bash
# 访问 https://snowboy.hahack.com/ 训练自定义唤醒词
# 将生成的 .pmdl 文件放到 max_ws/src/baidu_model_chat_linux_0812/ 目录
# 修改 voice_capture.py 中的 MODEL_FILE 变量指向你的唤醒词模型
```

### 5. 配置 API 密钥

```bash
cp .env.example .env
nano .env
```

需要配置的 API 服务：

| 服务 | 获取地址 | 说明 |
|------|----------|------|
| 百度文心 ERNIE | https://qianfan.cloud.baidu.com/ | LLM 大模型 |
| 百度语音 ASR/TTS | https://ai.baidu.com/tech/speech | 语音识别与合成 |
| 阿里云 DashScope | https://dashscope.console.aliyun.com/ | Qwen LLM + ASR/TTS |
| 阿里云呼叫中心 | https://ccc.console.aliyun.com/ | 电话呼叫 |
| 高德地图 | https://lbs.amap.com/dev/ | 天气查询 API |
| SMS宝 | http://www.smsbao.com/ | 短信发送 |

> **不要将 .env 文件提交到 Git！它已在 .gitignore 中。**

### 6. 编译 ROS 工作空间

```bash
cd max_ws
catkin build
source devel/setup.bash
```

## 机器人启动流程

### 首次建图

1. 启动所有传感器驱动节点
2. 启动 SLAM 建图节点
3. 使用键盘遥控机器人在目标区域完整走一遍
4. 保存地图文件

详细命令参见 [max_ws/readme.md](../max_ws/readme.md)

### 日常使用

1. 启动定位和导航节点
2. 启动语音交互节点
3. 说出唤醒词启动对话交互

## 常见问题

### Q: 激光雷达无法识别？
A: 检查 USB 权限：`sudo chmod 666 /dev/ttyUSB*`

### Q: Snowboy 唤醒无响应？
A: 确认 .pmdl 模型文件路径正确，灵敏度参数可适当调低 (0.4-0.5)

### Q: 百度 TTS 合成失败？
A: 检查 API Key 和 Secret Key 是否过期，网络是否可访问 `tsn.baidu.com`

### Q: 导航定位漂移？
A: 检查 IMU 数据是否正常，TF 树是否完整：
```bash
rosrun tf view_frames
# 在浏览器查看生成的 frames.pdf
```

### Q: move_base 找不到 Action Server？
A: 确保已 `source devel/setup.bash`，检查 launch 文件中所有必要节点是否已启动。

### Q: 麦克风没有声音输入？
A: 检查默认音频设备：
```bash
arecord -l              # 列出录音设备
pyaudio_test.py         # 测试 PyAudio
```

## 性能优化建议

1. **Orange Pi 5**: 建议开启风扇散热，LLM 推理时 CPU 负载较高
2. **建图时**: 建议降低移动速度 (0.2-0.3 m/s)，保证点云质量
3. **语音交互**: 在嘈杂环境建议使用阵列麦克风 + 降噪处理
4. **网络**: LLM API 调用需要稳定的互联网连接，建议使用有线网络
5. **电源**: 确保供电充足 (5V/3A 以上)，避免电机和主板共用电源导致电压不稳
