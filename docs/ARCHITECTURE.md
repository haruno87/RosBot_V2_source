# RosBot V2 系统架构详解

## 整体架构

RosBot V2 采用分层架构设计，自上而下分为 **语音交互层 → 感知决策层 → 执行控制层**，通过 ROS 消息总线实现各层解耦通信。

```
                        ┌─────────────────┐
                        │   用户 (老人)     │
                        └────────┬────────┘
                                 │ 语音 / 动作
                                 ▼
┌──────────────────────────────────────────────────────────────┐
│                     语音交互层 (Voice Layer)                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ 麦克风输入 │──▶│Snowboy唤醒│──▶│ 百度ASR  │──▶│ 文本输入  │  │
│  │          │   │(hotword) │   │(speech→ │   │          │  │
│  │          │   │          │   │ text)   │   │          │  │
│  └──────────┘   └──────────┘   └──────────┘   └────┬─────┘  │
│                                                     │        │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐        │        │
│  │ 扬声器输出 │◀──│ 百度TTS  │◀──│ LLM 响应  │◀───────┘        │
│  │          │   │(text→   │   │(文本生成) │                 │
│  │          │   │ speech) │   │          │                 │
│  └──────────┘   └──────────┘   └──────────┘                 │
└──────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────┐
│                    感知决策层 (Decision Layer)                  │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              LLM 推理引擎 (ERNIE / Qwen)               │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │    │
│  │  │  意图理解    │  │  函数调用    │  │  回复生成    │  │    │
│  │  │ "帮我找遥控器"│──▶│ find_item() │──▶│ "好的，我马  │  │    │
│  │  │             │  │             │  │  上帮您找"  │  │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │ Point-LIO │   │ OctoMap  │   │ 摄像头捕捉 │   │ MQTT 传感器│  │
│  │ 激光SLAM  │   │ 3D 建图  │   │ 物体检测  │   │ 摔倒检测  │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
└──────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────┐
│                    执行控制层 (Execution Layer)                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │move_base │   │  电机控制  │   │  电话呼叫  │   │  短信发送  │  │
│  │ 路径规划  │   │ 底盘驱动  │   │ 阿里云CCC │   │ SMS宝    │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## ROS 话题通信

### 核心话题 (Topics)

| 话题名称 | 消息类型 | 方向 | 用途 |
|----------|----------|------|------|
| `/voice_keyword` | `std_msgs/String` | Pub → | LLM 工具调用 → 导航/控制节点 |
| `/mqtt_data` | `std_msgs/String` | → Sub | MQTT 传感器数据 (摔倒检测) |
| `/pointlio/cloud_registered` | `sensor_msgs/PointCloud2` | Pub → | Point-LIO 配准点云 |
| `/scan` | `sensor_msgs/LaserScan` | Pub → | 激光雷达扫描数据 |
| `/imu/data` | `sensor_msgs/Imu` | Pub → | IMU 姿态数据 |
| `/cmd_vel` | `geometry_msgs/Twist` | → Sub | 底盘速度控制指令 |
| `/move_base/goal` | `move_base_msgs/MoveBaseActionGoal` | → Action | 导航目标点 |
| `/initialpose` | `geometry_msgs/PoseWithCovarianceStamped` | Pub → | AMCL 初始位姿 |

### 关键服务 (Services)

| 服务名称 | 类型 | 用途 |
|----------|------|------|
| `/octomap_binary` | `octomap_msgs/GetOctomap` | 保存/加载 3D 地图 |
| `/octomap_full` | `octomap_msgs/GetOctomap` | 完整 OctoMap 操作 |

### JSON 消息格式

`/voice_keyword` 话题使用 JSON 封装指令：

```json
{ "keyword": "go to point a" }
```

```json
{ "keyword": "follow" }
```

```json
{ "keyword": "Go to charge" }
```

```json
{ "keyword": "stop" }
```

## LLM 双引擎架构

### 方案一：百度 ERNIE (`main.py`)

```
语音输入 → Snowboy 唤醒 → AudioRecorder 录音 → 百度 ASR →
ERNIE-Lite-Pro-128K 推理 → 函数调用分发 → 百度 TTS 播报
```

- **模型**: ERNIE-Lite-Pro-128K (128K 上下文)
- **视觉模型**: ERNIE-4.5-VL-28B (物品识别)
- **ASR/TTS**: 百度语音 API
- **唤醒**: Snowboy + 自定义唤醒词模型 (.pmdl)
- **API 端点**: `qianfan.baidubce.com`

### 方案二：阿里 Qwen (`llm_to_vlm.py`)

```
语音输入 → DashScope ASR (实时流式) → Qwen-Plus 推理 →
函数调用分发 → CosyVoice TTS 播报
```

- **模型**: Qwen-Plus
- **ASR**: DashScope TranslationRecognizerRealtime (流式识别)
- **TTS**: CosyVoice-V1 (阿里自研语音合成)
- **唤醒**: 关键词 "你好" 实时检测
- **API 端点**: `dashscope.aliyuncs.com`

## 导航系统架构

### SLAM 建图管线

```
Unitree LiDAR → Point-LIO (激光惯性里程计) → 去畸变点云 →
OctoMap Server → 3D 占据栅格地图 → pcd2pgm → 2D 栅格地图 (.pgm + .yaml)
```

### 自主导航管线

```
AMCL 定位 ← 2D 地图 + 激光扫描
        ↓
全局路径规划 (Global Planner)
        ↓
局部路径规划 (DWA / TEB) ← 激光扫描 (避障)
        ↓
    cmd_vel → 电机控制 → 底盘运动
```

支持的局部规划器：
- **DWA** (Dynamic Window Approach): 速度采样 + 轨迹评分，适合室内平坦环境
- **TEB** (Timed Elastic Band): 时空优化，适合动态环境和窄通道

## 摔倒检测响应流程

```
MQTT 传感器 → /mqtt_data 话题 → fall_callback → handle_fall_event()
    │
    ├── 1. 语音播报关怀语 (CosyVoice TTS / 百度 TTS)
    ├── 2. 发送紧急短信 (SMS宝 平台)
    ├── 3. 拨打紧急电话 (阿里云呼叫中心 CCC)
    └── 4. 发布 /voice_keyword 通知其他 ROS 节点
```

## 技术依赖关系

```
Python 依赖:
├── openai (阿里 DashScope 兼容接口)
├── dashscope (阿里语音 ASR/TTS)
├── pyaudio (音频输入输出)
├── snowboydetect (热词唤醒)
├── opencv-python (摄像头)
├── requests (HTTP 请求)
├── rospy (ROS Python 接口)
├── alibabacloud_ccc20200701 (阿里云呼叫中心)
├── alibabacloud_tea_openapi (阿里云 OpenAPI)
└── actionlib (ROS Action 客户端)

ROS 依赖:
├── move_base (导航框架)
├── octomap_server (3D 建图)
├── point_lio_unilidar (激光 SLAM)
├── pcl_ros (点云处理库)
├── rplidar_ros (思岚雷达驱动)
├── unitree_lidar_ros (宇树雷达驱动)
├── amcl (自适应定位)
└── tf / tf2 (坐标变换)
```
