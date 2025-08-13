# main terminal conmain 

## remember to source each terminal
source devel/setup.bash


roslaunch unitree_lidar_ros run_without_rviz.launch
roslaunch point_lio_unilidar mapping_unilidar_l2.launch  #pointlio mapping node

rosservice call /octomap_binary "filename: '/home/orangepi/max_ws/src/nav/map/drone_map.bt'"
rosservice call /octomap_full "load_map: true filename: '/home/orangepi/max_ws/src/nav/map/drone_map.bt'"               # the way to save octomap

rosrun pcl_ros pcd_to_pointcloud /home/orangepi/max_ws/src/point_lio_unilidar/PCD/scans.pcd _frame_id:=map _rate:=1.0 _topic:=/pointlio/cloud_registered _latch:=true               # to translata .pcd(map) to pointcloud

roslaunch octomap_server octomap_mapping.launch  # mapping based on octomap

rosrun service tf_trans.py  # publish tf from map to odom

# Mapping!

## how to start
    source devel/setup.bash
    
    roslaunch nav lio_mapping.launch    # mapping and translate to octomap

    rosrun service motor_control.py
    rosrun service key_scans.py         # to move robot based on keyboard

    roslaunch pcd2pgm run.launch

    roslaunch nav map_saver.launch      # check the quailty of map and save map

     

### remember to change the name of .png , .yaml and .pcd Map


# Moving!

## how to start
    source devel/setup.bash

    roslaunch nav point_loc.launch      # relocalication node
    rosrun service Trans_TF_2d      
    roslaunch service motor_control.py  # motor control node
    roslaunch nav move_base.launch









