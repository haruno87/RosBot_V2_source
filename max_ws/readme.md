# RosBot V2 — ROS 工作空间操作手册

## ⚡ 环境配置

每个新终端启动 ROS 命令前都需要执行：

```bash
source devel/setup.bash
```

---

## 🗺️ 建图模式

### 启动建图

```bash
# 终端 1: 启动激光雷达驱动
roslaunch unitree_lidar_ros run_without_rviz.launch

# 终端 2: 启动 Point-LIO SLAM
roslaunch point_lio_unilidar mapping_unilidar_l2.launch

# 终端 3: 启动融合建图 + OctoMap
roslaunch nav lio_mapping.launch

# 终端 4: 启动电机控制和键盘遥控
rosrun service motor_control.py
rosrun service key_scans.py
```

### 保存地图

```bash
# 保存 OctoMap (3D)
rosservice call /octomap_binary "filename: '/home/orangepi/max_ws/src/nav/map/drone_map.bt'"
rosservice call /octomap_full "load_map: true filename: '/home/orangepi/max_ws/src/nav/map/drone_map.bt'"

# 将 PCD 文件发布为 PointCloud2 话题
rosrun pcl_ros pcd_to_pointcloud /home/orangepi/max_ws/src/point_lio_unilidar/PCD/scans.pcd \
    _frame_id:=map _rate:=1.0 _topic:=/pointlio/cloud_registered _latch:=true

# 启动 OctoMap 建图服务
roslaunch octomap_server octomap_mapping.launch

# 发布 TF (map → odom)
rosrun service tf_trans.py

# 转换点云为 2D 栅格地图
roslaunch pcd2pgm run.launch

# 保存 2D 地图（先检查质量再保存）
roslaunch nav map_saver.launch
```

> ⚠️ **重要**: 每次建图完成后记得修改 .png / .yaml / .pcd 文件名以区分不同地图！

---

## 🧭 导航模式

### 启动导航

```bash
# 终端 1: 启动重定位
roslaunch nav point_loc.launch

# 终端 2: 发布 2D TF 变换
rosrun service Trans_TF_2d

# 终端 3: 启动导航框架
roslaunch nav move_base.launch

# 终端 4: 电机控制
rosrun service motor_control.py
```

---

## 🗣️ 语音交互模式

### 百度 ERNIE 方案

适用于需要深度语义理解的场景（日常聊天、健康咨询等）。

```bash
cd max_ws/src/baidu_model_chat_linux_0812
python main.py
```

### 阿里 Qwen 方案

适用于需要精确函数调用的场景（导航指令、操作执行等）。

```bash
cd max_ws/src/baidu_model_chat_linux_0812
python llm_to_vlm.py
```

---

## 📁 ROS 功能包说明

| 功能包 | 说明 |
|--------|------|
| `baidu_model_chat_linux_0812` | LLM 语音交互核心 (语音唤醒/ASR/TTS/LLM) |
| `nav` | 导航功能包 (建图/定位/路径规划) |
| `service` | 基础服务 (电机驱动/键盘遥控/TF变换) |
| `point_lio_unilidar` | Point-LIO 激光惯性 SLAM |
| `unitree_lidar_ros` | 宇树激光雷达 ROS 驱动 |
| `rplidar_ros` | 思岚激光雷达 ROS 驱动 |
| `wit_ros_imu` | WIT 维特 IMU 驱动 |
| `octomap_mapping` | OctoMap 3D 概率占据栅格建图 |
| `pcd2pgm_package` | 3D 点云转 2D 栅格地图 |
| `jie_ware` | 自定义固件/工具箱 |

---

## 🔧 调试工具

```bash
# 查看 TF 坐标树
rosrun tf view_frames
# 在浏览器中查看生成的 frames.pdf

# 列出所有话题
rostopic list

# 查看节点图
rosrun rqt_graph rqt_graph

# 实时查看话题数据
rostopic echo /voice_keyword
rostopic echo /scan
rostopic echo /cmd_vel

# 可视化界面
rviz -d max_ws/src/nav/rviz/rviz/nav.rviz

# 查看节点列表
rosnode list

# 查看节点详细信息
rosnode info /voice_interaction_node
```
