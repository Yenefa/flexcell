# Semantic demo zone (Week-1.5). Occupancy is DERIVED from ground-truth
# observation; if the projection is unavailable it must be NOT_AVAILABLE.
string id
geometry_msgs/Point center
float64 radius
int8 OCCUPANCY_NOT_AVAILABLE=-1
int8 OCCUPANCY_FREE=0
int8 OCCUPANCY_OCCUPIED=1
int8 occupancy
