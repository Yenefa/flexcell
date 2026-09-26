# One object tracked in the FlexCell world state.
string name
geometry_msgs/Pose pose      # pose in the world frame (ground truth)
float64[3] size              # bounding box size [x y z] in metres
bool available               # true if the object was observed in this snapshot
