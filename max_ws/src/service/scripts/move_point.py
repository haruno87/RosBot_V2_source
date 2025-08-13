#!/usr/bin/env python3
import rospy
import json
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
import threading


# - Translation: [4.199, -1.294, -0.017]    饮水机
# - Rotation: in Quaternion [0.003, -0.007, -0.769, 0.639]
#             in RPY (radian) [0.015, -0.004, -1.755]
#             in RPY (degree) [0.860, -0.213, -100.527]

# At time 1754976359.304        维修台
# - Translation: [-0.571, -0.969, -0.036]
# - Rotation: in Quaternion [-0.004, 0.006, 0.999, -0.047]
#             in RPY (radian) [0.013, 0.007, -3.047]
#             in RPY (degree) [0.739, 0.388, -174.596]


# At time 1754976631.050
# - Translation: [2.443, 3.833, -0.029]
# - Rotation: in Quaternion [-0.003, -0.001, 0.707, 0.707]
#             in RPY (radian) [-0.006, 0.004, 1.571]
#             in RPY (degree) [-0.361, 0.201, 90.021]

class KeywordNavigator:
    def __init__(self):
        rospy.init_node('keyword_navigator', anonymous=True)
        
        # 订阅关键词话题
        rospy.Subscriber('/voice_keyword', String, self.keyword_callback)
        
        # 订阅摔倒话题
        rospy.Subscriber('/mqtt_data', String, self.fall_callback)
        
        # 创建move_base动作客户端
        self.move_base = actionlib.SimpleActionClient('move_base', MoveBaseAction)
        rospy.loginfo("等待move_base动作服务器连接...")
        self.move_base.wait_for_server()
        rospy.loginfo("move_base动作服务器已连接")
        
        self.keyword_goals = {
            "go to point a": [4.199, -1.294, 0.000, 0.000, 0.000, -0.769, 0.639],
            "go to point b": [-0.571, -0.969, -0.036, 0.000, 0.000, 0.999, -0.047],
            "go to point c": [2.443, 3.833, 0.000, 0.000, 0.000, 0.707, 0.707],
            "Go to the table": [5.398, -1.921, 0.000, 0.000, 0.000, 0.012, 1.000],
            "fall": [-0.001, -0.031, 0.000, 0.000, 0.000, -1.000, 0.009]
        }
        
        # 线程锁，用于线程安全
        self.lock = threading.Lock()
    
    def keyword_callback(self, msg):
        try:
            # 记录收到的消息
            rospy.logdebug("收到的消息: %s", msg.data)
            
            # 解析JSON格式的消息
            keyword_data = json.loads(msg.data)
            
            # 检查是否包含 "keyword" 字段
            if "keyword" not in keyword_data:
                rospy.logwarn("消息中不包含 'keyword' 字段")
                return
            
            keyword = keyword_data.get("keyword")
            rospy.loginfo("收到关键词: %s", keyword)
            
            # 根据关键词执行相应操作
            if keyword in self.keyword_goals:
                goal_params = self.keyword_goals[keyword]
                self.send_goal(goal_params)
            else:
                rospy.logwarn("未知的关键词: %s", keyword)
        
        except json.JSONDecodeError:
            rospy.logerr("收到的消息不是有效的JSON格式: %s", msg.data)
        except Exception as e:
            rospy.logerr("处理关键词时出错: %s", str(e))
    
    def fall_callback(self, msg):
        try:
            # 记录收到的消息
            rospy.logdebug("收到的消息: %s", msg.data)
            
            # 解析JSON格式的消息
            data = json.loads(msg.data)
            
            # 检查是否是摔倒信息
            if data.get("FallState", 0) == 1:
                rospy.loginfo("收到摔倒信息，准备导航到目标点")
                
                # 使用线程安全的方式发送目标点
                with self.lock:
                    self.send_goal(self.keyword_goals["fall"])
        
        except json.JSONDecodeError:
            rospy.logerr("收到的消息不是有效的JSON格式: %s", msg.data)
        except Exception as e:
            rospy.logerr("处理摔倒信息时出错: %s", str(e))
    
    def send_goal(self, goal_params):
        # 创建MoveBaseGoal对象
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        
        # 设置目标点位置和朝向
        goal.target_pose.pose.position.x = goal_params[0]
        goal.target_pose.pose.position.y = goal_params[1]
        goal.target_pose.pose.position.z = goal_params[2]
        goal.target_pose.pose.orientation.x = goal_params[3]
        goal.target_pose.pose.orientation.y = goal_params[4]
        goal.target_pose.pose.orientation.z = goal_params[5]
        goal.target_pose.pose.orientation.w = goal_params[6]
        
        # 发送目标点到move_base动作服务器
        self.move_base.send_goal(goal)
        rospy.loginfo("目标点已发送，等待到达...")
        
        # 等待机器人到达目标点
        self.move_base.wait_for_result()
        
        # 检查结果
        if self.move_base.get_state() == actionlib.GoalStatus.SUCCEEDED:
            rospy.loginfo("机器人已到达目标点")
        else:
            rospy.logwarn("机器人未能到达目标点")
    
    def run(self):
        rospy.spin()

if __name__ == '__main__':
    try:
        navigator = KeywordNavigator()
        navigator.run()
    except rospy.ROSInterruptException:
        pass