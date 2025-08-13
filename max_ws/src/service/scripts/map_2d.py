#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import rospy
import tf
import tf.transformations
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped, PoseWithCovarianceStamped
import numpy as np

class Map2DTransformer:
    def __init__(self):
        rospy.init_node('map_2d_transformer', anonymous=True)
        
        # TF broadcaster
        self.tf_broadcaster = tf.TransformBroadcaster()
        
        # TF listener for getting transformations
        self.tf_listener = tf.TransformListener()
        
        # Subscriber for odometry data
        self.odom_sub = rospy.Subscriber('/pointlio/odom', Odometry, self.odom_callback, queue_size=10)
        
        # Subscriber for initial pose
        self.initial_pose_sub = rospy.Subscriber('/initialpose', PoseWithCovarianceStamped, self.initial_pose_callback, queue_size=1)
        
        # Transformation from prior_map to camera_init
        self.T_prior_map_to_camera_init = None
        
        # Flag to indicate if transformation is initialized
        self.initialized = False
        
        rospy.loginfo("Map 2D Transformer node initialized")
    
    def initial_pose_callback(self, pose_msg):
        """Callback for initial pose estimation"""
        if not self.initialized:
            # Get the transformation from the initial pose
            position = pose_msg.pose.pose.position
            orientation = pose_msg.pose.pose.orientation
            
            # Create transformation matrix from prior_map to camera_init
            self.T_prior_map_to_camera_init = self.pose_to_transform(position, orientation)
            self.initialized = True
            
            rospy.loginfo("Initial transformation from prior_map to camera_init set")
    
    def odom_callback(self, odom_msg):
        """Callback for odometry data"""
        if not self.initialized:
            # If not initialized, use the first odometry message as initial transformation
            position = odom_msg.pose.pose.position
            orientation = odom_msg.pose.pose.orientation
            
            # Create transformation matrix from prior_map to camera_init
            self.T_prior_map_to_camera_init = self.pose_to_transform(position, orientation)
            self.initialized = True
            
            rospy.loginfo("Initial transformation from prior_map to camera_init set from odometry")
        
        # Publish the transformation from prior_map to camera_init
        if self.T_prior_map_to_camera_init is not None:
            self.publish_transformation()
    
    def pose_to_transform(self, position, orientation):
        """Convert pose to transformation matrix"""
        # Translation
        translation = [position.x, position.y, position.z]
        
        # Rotation (quaternion to matrix)
        quaternion = [orientation.x, orientation.y, orientation.z, orientation.w]
        
        return (translation, quaternion)
    
    def publish_transformation(self):
        """Publish the transformation from prior_map to camera_init"""
        if self.T_prior_map_to_camera_init is not None:
            translation, quaternion = self.T_prior_map_to_camera_init
            
            # Publish the transformation
            self.tf_broadcaster.sendTransform(
                translation,
                quaternion,
                rospy.Time.now(),
                "camera_init",    # child frame
                "prior_map"       # parent frame
            )
    
    def run(self):
        """Main loop"""
        rate = rospy.Rate(30)  # 30 Hz
        
        while not rospy.is_shutdown():
            if self.initialized and self.T_prior_map_to_camera_init is not None:
                self.publish_transformation()
            
            rate.sleep()

def main():
    try:
        transformer = Map2DTransformer()
        transformer.run()
    except rospy.ROSInterruptException:
        pass

if __name__ == '__main__':
    main()
