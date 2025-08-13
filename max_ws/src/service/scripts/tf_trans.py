#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import tf
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf.transformations import quaternion_from_euler

# 回调函数：从/pointlio/odom话题中获取里程计信息
def odom_callback(odom_msg):
    global odom_tf_broadcaster

    # 获取里程计信息中的位置和姿态
    position = odom_msg.pose.pose.position
    orientation = odom_msg.pose.pose.orientation

    # 将位置和姿态转换为tf格式
    translation = (position.x, position.y, position.z)
    rotation = (orientation.x, orientation.y, orientation.z, orientation.w)

    # 发布从map到odom的变换
    odom_tf_broadcaster.sendTransform(
        translation,
        rotation,
        rospy.Time.now(),
        "odom",  # 目标坐标系
        "map"    # 源坐标系
    )

if __name__ == '__main__':
    rospy.init_node('map_to_odom_tf_broadcaster', anonymous=True)
    odom_tf_broadcaster = tf.TransformBroadcaster()

    # 订阅/pointlio/odom话题
    rospy.Subscriber('/pointlio/odom', Odometry, odom_callback)

    rospy.spin()  # 保持节点运行
