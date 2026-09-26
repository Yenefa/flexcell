# Robot summary inside the canonical WorldState (v2 adds the gripper aperture;
# everything else unchanged from Week-1.5).
string[] joint_names
float64[] positions
geometry_msgs/Pose ee_pose
string ee_frame
string gripper_joint_name             # first gripper* joint seen in /joint_states ("" = none)
float64 gripper_position              # aperture of that joint (rad)
bool has_gripper_state                # false when no gripper joint is present
