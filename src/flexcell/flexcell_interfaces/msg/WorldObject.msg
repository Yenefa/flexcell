# One object tracked in the FlexCell world state (v2 adds class + freshness).
string name
geometry_msgs/Pose pose      # pose in the world frame (ground truth)
float64[3] size              # bounding box size [x y z] in metres
bool available               # true if the object was observed in this snapshot
string klass                 # semantic class (v2: always "box")
float64 pose_age_s           # age of this sample relative to the snapshot (>= 0)
