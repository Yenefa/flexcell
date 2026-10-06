cmake_minimum_required(VERSION 3.8)
project(flexcell_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "srv/EngageCarry.srv"
  "srv/QueryCarry.srv"
  "msg/Assignment.msg"
  "msg/ObjectPosition.msg"
  "msg/CompositeStage.msg"
  "msg/TaskConstraints.msg"
  "msg/HistoryEntry.msg"
  "msg/TaskContext.msg"
  "msg/WorldObject.msg"
  "msg/WorldState.msg"
  "msg/RobotStateSummary.msg"
  "msg/CarryState.msg"
  "msg/ZoneState.msg"
  "action/MoveToPose.action"
  "action/Observe.action"
  "action/PickObject.action"
  "action/PlaceObject.action"
  "action/VerifyObject.action"
  "action/RunPickPlace.action"
  "action/RunDemo.action"
  "action/RunComposite.action"
  DEPENDENCIES geometry_msgs std_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
