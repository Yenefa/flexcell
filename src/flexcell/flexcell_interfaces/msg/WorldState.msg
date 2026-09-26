# Canonical world snapshot (Week 1: ground-truth poses + robot EE).
std_msgs/Header header
uint64 revision                       # bumps when tracked objects move past epsilon
flexcell_interfaces/WorldObject[] objects
string[] notes                        # e.g. "target_box: in_motion"
