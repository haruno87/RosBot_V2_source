#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import tf
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped

class Odom2DNode:
    def __init__(self):
        rospy.init_node('odom_2d_node', anonymous=True)

        # 订阅原始 odom 和 tf
        self.odom_sub = rospy.Subscriber('/pointlio/odom', Odometry, self.odom_callback)
        self.tf_listener = tf.TransformListener()
        self.tf_broadcaster = tf.TransformBroadcaster()

        # 发布修改后的 odom 和 tf
        self.odom_pub = rospy.Publisher('/odom_2d', Odometry, queue_size=10)

    def odom_callback(self, odom_msg):
        # 修改 odom 的 Z 轴数据
        odom_msg.pose.pose.position.z = 0.0
        odom_msg.twist.twist.linear.z = 0.0
        odom_msg.twist.twist.angular.x = 0.0
        odom_msg.twist.twist.angular.y = 0.0
        
        # 修改 frame_id 和 child_frame_id
        odom_msg.header.frame_id = 'odom'
        odom_msg.child_frame_id = 'base_link'

        # 发布修改后的 odom
        self.odom_pub.publish(odom_msg)

        # 修改 tf 的 Z 轴数据并发布新的 TF
        try:
            (trans, rot) = self.tf_listener.lookupTransform('camera_init', 'aft_mapped', rospy.Time(0))
            trans = (trans[0], trans[1], 0.0)  # Z 轴置为 0
            self.tf_broadcaster.sendTransform(trans, rot, rospy.Time.now(), 'base_link', 'odom')
        except (tf.LookupException, tf.ConnectivityException, tf.ExtrapolationException):
            rospy.logwarn("TF lookup failed")

if __name__ == "__main__":
    try:
        node = Odom2DNode()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
