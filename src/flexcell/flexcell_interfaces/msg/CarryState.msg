# Carry backend state (Week-1.5). This is BACKEND state, not physical evidence:
# it says what the carry servo believes, never that a grasp succeeded.
# Physical/simulation evidence always comes from Gazebo observation (verify skill).
std_msgs/Header header
bool engaged
string object_id
string reference_frame
float64[3] offset
