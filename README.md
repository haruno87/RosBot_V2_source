#  RosBot V2 — 适老化智能康养机器人

<div align="center">

[![ROS](https://img.shields.io/badge/ROS-Noetic-blue?logo=ros)](https://www.ros.org/)
[![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20(Orange%20Pi)-orange)]()

**基于 ROS 的适老化交互设计健康管理智能终端**

[功能介绍](#-核心功能) · [系统架构](#-系统架构) · [硬件配置](#-硬件配置) · [快速开始](#-快速开始) · [演示视频](#-演示视频)

</div>

---

##  项目简介

**RosBot V2** 是一款面向高龄及行动不便老人的智能康养服务机器人。通过语音唤醒与大模型对话交互，机器人能够理解老人的自然语言指令，提供健康咨询、物品寻找、紧急求助、自主导航陪伴等一站式智能服务。

本项目在 RosBot V1 的基础上，全面升级了语音交互能力和自主导航系统，利用百度文心大模型（ERNIE）和阿里通义千问（Qwen）实现了多模态感知与智能决策。

>  **演示视频**: [Bilibili BV1ijP4zcEVN](https://www.bilibili.com/video/BV1ijP4zcEVN/?share_source=copy_web&vd_source=7f605a0a612167349f0bd705dfa891c8)

##  核心功能

###  智能语音交互
- **唤醒词检测**: 基于 [Snowboy](https://github.com/Kitt-AI/snowboy) 的热词唤醒，支持自定义唤醒词
- **语音识别 (ASR)**: 集成百度语音识别 API / 阿里云 DashScope，实时语音转文字
- **大模型对话**: 双 LLM 架构
  - **百度文心 ERNIE-Lite-Pro-128K** — 长上下文理解，适合复杂对话场景
  - **阿里通义千问 Qwen-Plus** — 函数调用能力强，适合指令执行场景
- **语音合成 (TTS)**: 百度语音合成 / 阿里 CosyVoice，自然流畅的语音播报
- **机器人表情**: 通过 HTTP 接口控制机器人面部表情（眨眼、聆听、休眠等）

###  自主导航系统
- **SLAM 建图**: 基于 Point-LIO + OctoMap 的实时 3D 点云建图
- **路径规划**: 支持 DWA / TEB 两种局部规划器，适配不同场景
- **自主定位**: AMCL 自适应蒙特卡洛定位，支持 2D 地图重定位
- **激光雷达**: 宇树 Unitree LiDAR + 思岚 RP LiDAR 双雷达方案
- **多点导航**: 语音指令导航到预设目标点（如饮水机、维修台等）

###  视觉感知
- **物品寻找**: 调用摄像头拍照 → VLM 视觉大模型分析 → 语音告知物品位置
- **环境感知**: 支持拍照理解周围环境，回答老人"这是什么"类问题

###  安全守护
- **摔倒检测**: 通过外部传感器（MQTT）实时监测老人状态
- **紧急响应**: 检测到摔倒后自动触发：
  -  语音播报关怀语
  -  发送紧急短信通知社区健康中心
  -  拨打预设紧急联系人电话

###  生活助手
- **天气查询**: 集成高德天气 API，支持全国城市天气实时查询
- **健康建议**: 针对老龄人特点提供饮食、运动、用药建议
- **信息记忆**: 记住老人的偏好和重要信息（用药时间、家人联系方式等）
- **跟随功能**: 激光雷达人体跟踪，实现机器人跟随老人移动
- **自动回充**: 低电量时自动返回充电桩

##  系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      RosBot V2 系统架构                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  语音交互层   │  │  感知决策层   │  │      执行控制层       │  │
│  ├─────────────┤  ├─────────────┤  ├─────────────────────┤  │
│  │ Snowboy 唤醒  │  │ ERNIE/Qwen │  │  move_base 路径规划   │  │
│  │ 百度 ASR/TTS │  │ LLM 推理    │  │  DWA/TEB 局部规划    │  │
│  │ 阿里 ASR/TTS │  │ 函数调用     │  │  motor_control 驱动  │  │
│  │ 语音合成输出  │  │ 工具编排     │  │  LiDAR 数据融合      │  │
│  └──────┬───────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                 │                     │             │
│         └────────┬────────┴──────────┬──────────┘             │
│                  │                   │                        │
│          ┌───────▼───────┐   ┌───────▼───────┐               │
│          │  ROS 消息总线   │   │  MQTT 传感器   │               │
│          │  /voice_keyword│   │  fall_detect  │               │
│          │  /move_base    │   │  imu_data     │               │
│          └───────────────┘   └───────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

##  项目结构

```
RosBot_V2/
├── README.md                     # 项目说明
├── LICENSE                       # MIT 开源协议
├── .gitignore                    # Git 忽略规则
├── .gitattributes                # Git 属性配置
├── requirements.txt              # Python 依赖
├── .env.example                  # API 密钥配置模板
├── docs/                         # 项目文档
│   ├── ARCHITECTURE.md           # 系统架构详解
│   └── SETUP.md                  # 部署与配置指南
│
└── max_ws/                       # ROS 工作空间 (Catkin)
    ├── readme.md                 # ROS 启动与操作说明
    └── src/                      # ROS 功能包
        ├── baidu_model_chat_linux_0812/  # LLM 语音交互核心
        │   ├── main.py                  # 主程序入口 (百度文心方案)
        │   ├── llm_to_vlm.py            # 主程序入口 (通义千问方案)
        │   ├── functions.py             # LLM 工具调用处理
        │   ├── function.json            # 函数调用定义
        │   ├── voice_capture.py         # 语音捕获与唤醒
        │   ├── text_voice.py            # ASR/TTS 语音服务
        │   ├── camera_capture.py        # 摄像头拍照
        │   ├── playaudio.py             # 音频播放
        │   ├── call_sms.py              # 电话与短信
        │   ├── robot_face_seting.py     # 机器人表情控制
        │   └── instructions.txt         # 系统提示词
        │
        ├── nav/                         # 导航功能包
        │   ├── launch/                  # 启停脚本 (建图/定位/导航)
        │   ├── map/                     # 地图文件 (.yaml, .pgm)
        │   ├── param/                   # 导航参数配置
        │   └── src/                     # 导航节点源码
        │
        ├── service/                     # 基础服务功能包
        │   ├── scripts/                 # 控制脚本
        │   │   ├── motor_control.py     # 电机控制
        │   │   ├── key_scans.py         # 键盘遥控
        │   │   └── tf_trans.py          # TF 坐标变换
        │   └── src/                     # 服务节点源码
        │
        ├── point_lio_unilidar/          # Point-LIO 激光 SLAM
        ├── unitree_lidar_ros/           # 宇树激光雷达驱动
        ├── unitree_lidar_sdk/           # 宇树雷达 SDK
        ├── rplidar_ros/                 # 思岚激光雷达驱动
        ├── wit_ros_imu/                 # WIT IMU 姿态传感器
        ├── octomap_mapping/             # OctoMap 3D 建图
        ├── pcd2pgm_package/             # 点云转 2D 栅格地图
        └── jie_ware/                    # 自定义固件/工具
```

## 硬件配置

| 组件 | 型号 | 用途 |
|------|------|------|
| 主控 | Orange Pi 5 / 树莓派 | ROS 主控与 AI 推理 |
| 激光雷达 | 宇树 Unitree LiDAR 4D | 3D SLAM 建图 |
| 激光雷达 | 思岚 RP LiDAR A1/A2 | 2D 避障导航 |
| IMU | WIT 维特智能 | 姿态感知与里程计 |
| 摄像头 | USB Camera | 物体识别与环境感知 |
| 麦克风 | USB 阵列麦克风 | 语音输入 |
| 扬声器 | 3.5mm 音箱 | 语音播报 |
| 底盘 | 差速驱动底盘 | 自主移动 |
| 电机 | 带编码器直流电机 | 里程计与运动控制 |

## 快速开始

### 环境要求

- **操作系统**: Ubuntu 20.04 (Orange Pi 5) / Raspberry Pi OS
- **ROS 版本**: ROS Noetic
- **Python**: 3.8+
- **编译工具**: catkin_tools

### 1. 克隆仓库

```bash
git clone https://github.com/trwang/RosBot_V2.git
cd RosBot_V2
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置 API 密钥

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入你的 API 密钥
# - 百度文心大模型 API Key
# - 阿里云 DashScope API Key
# - 阿里云呼叫中心 Access Key
# - 高德地图 API Key
# - 短信平台账号密码
```

### 4. 构建 ROS 工作空间

```bash
cd max_ws
catkin build
source devel/setup.bash
```

### 5. 启动机器人

详细启动步骤请参阅 [max_ws/readme.md](max_ws/readme.md)

#### 建图模式

```bash
# 终端 1: 启动激光雷达
roslaunch unitree_lidar_ros run_without_rviz.launch

# 终端 2: 启动 SLAM
roslaunch point_lio_unilidar mapping_unilidar_l2.launch

# 终端 3: 启动融合建图
roslaunch nav lio_mapping.launch

# 终端 4: 电机控制 + 键盘遥控
rosrun service motor_control.py
rosrun service key_scans.py
```

#### 导航模式

```bash
# 终端 1: 启动定位
roslaunch nav point_loc.launch

# 终端 2: 启动导航
roslaunch nav move_base.launch

# 终端 3: 电机控制
rosrun service motor_control.py
```

#### 语音交互

```bash
# 百度文心方案
cd max_ws/src/baidu_model_chat_linux_0812
python main.py

# 或使用阿里通义千问方案
python llm_to_vlm.py
```

### 6. 保存地图

```bash
# 保存 OctoMap
rosservice call /octomap_binary "filename: '/path/to/save/map.bt'"

# 转换并保存 2D 栅格地图
roslaunch pcd2pgm run.launch
roslaunch nav map_saver.launch
```

## LLM 工具调用能力

机器人通过 LLM Function Calling 实现以下工具能力：

| 函数名 | 功能 | 触发场景 |
|--------|------|----------|
| `get_image` | 拍照并分析图片 | "帮我看看这是什么" |
| `only_text` | 纯文本对话 | 日常聊天咨询 |
| `get_weather` | 查询天气 | "今天天气怎么样" |
| `go_to_location` | 导航到指定地点 | "带我去饮水机" |
| `find_item` | 寻找物品 | "帮我找一下遥控器" |
| `charge_back` | 返回充电桩 | "回去充电" |
| `follow_me` | 跟随用户 | "跟着我走" |
| `stop_following` | 停止跟随 | "停下别跟着我" |
| `make_phone_call` | 拨打电话 | "给我儿子打个电话" |
| `handle_fall_event` | 处理摔倒事件 | 传感器自动触发 |
| `remember_information` | 记忆信息 | "记住我女儿的电话" |

## 安全提醒

> **重要**: 请勿将 API 密钥、密码等敏感信息提交到 Git 仓库！

本项目已在 `.gitignore` 中配置了 `.env` 文件忽略。使用前请：
1. 将 `.env.example` 复制为 `.env`
2. 在 `.env` 中填入真实的 API 密钥
3. 修改代码中使用硬编码密钥的位置，改为从环境变量读取


## 开源协议

本项目基于 [MIT License](LICENSE) 开源。

## 致谢

- [ROS](https://www.ros.org/) — 机器人操作系统
- [Snowboy](https://github.com/Kitt-AI/snowboy) — 热词唤醒引擎
- [百度文心大模型](https://yiyan.baidu.com/) — ERNIE LLM
- [阿里通义千问](https://tongyi.aliyun.com/) — Qwen LLM & DashScope
- [百度语音](https://ai.baidu.com/tech/speech) — ASR/TTS 服务
- [Point-LIO](https://github.com/hku-mars/Point-LIO) — 鲁棒激光惯性里程计
- [OctoMap](https://octomap.github.io/) — 3D 概率占据栅格建图
- [高德地图](https://lbs.amap.com/) — 天气 API 服务

---

<div align="center">
  <sub>Made with for the elderly | by 王通润 trwang </sub>
</div>
