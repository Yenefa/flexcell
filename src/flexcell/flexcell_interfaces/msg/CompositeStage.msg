# One bounded native component of a RunComposite chain.
# Repeated object names are allowed.
string stage_id
string object_name
geometry_msgs/PoseStamped place_pose

# ============================================================================
# T08 push extension - BACKWARD COMPATIBLE BY CONSTRUCTION
#
# Every field below defaults to the legacy behaviour. A publisher that never
# sets them (every T01-T06 plan in this repository, every archived client)
# produces action == ACTION_PLACE and the stage is read exactly as before.
# Nothing in the place path consults the push fields.
# ============================================================================

# Which native skill executes this stage.
uint8 ACTION_PLACE = 0
uint8 ACTION_PUSH  = 1
uint8 action
# 0 (default) = PLACE, unchanged. Only ACTION_PUSH reads the fields below.

geometry_msgs/Vector3 push_direction
# World-frame push direction. Must be horizontal (z == 0) and non-zero for a
# push stage; normalised by the server, which refuses a zero or non-finite
# vector rather than inventing one. Ignored by place stages.

float64 push_distance_m
# Requested object displacement along push_direction, metres.
# Declared range 0.01 .. 0.15; outside that the stage is refused before motion.

float64 contact_height_m
# Height of the END-EFFECTOR TARGET (not the fingertip) that produces contact
# with the object. NaN means "use the push_server's declared
# contact_height_m parameter".
#
# WHY NaN AND NOT 0: 0.0 is a physically meaningful height (the table plane).
# A plan that simply omits the field must NOT silently mean "push at table
# height". The plan client is required to map absent -> NaN, so an omission
# lands on a declared, reviewable server parameter instead of a silent default.
# Measured reason this is per-run declarable at all: at EE z = 0.1775 the
# fingers passed 145 mm ABOVE the box and the box never moved; at z = 0.030
# the box moved 23 mm. A constant would have been wrong in both directions.

float64 overdrive_m
# Extra travel beyond the requested displacement, metres. NaN means "use the
# push_server default".
#
# WHY OVERDRIVE IS PART OF THE INTERFACE: the push is open loop. If the target
# is set exactly at the box's far face the arm can stop "within tolerance" both
# when the box yielded and when the box never moved, so the two cases become
# indistinguishable. Aiming past the box makes the arm's own measured
# position_error_m an honest signal: the box yielded and the arm arrived, or
# the box blocked the arm and the arm did not arrive.
