#include <iostream>
#include <fstream>
#include <cstring>
#include <iterator>
#include <rclcpp/serialization.hpp>
#include <moveit/planning_scene/planning_scene.hpp>
#include <moveit_msgs/msg/attached_collision_object.hpp>
#include <moveit_msgs/msg/collision_object.hpp>
#include <rclcpp/rclcpp.hpp>
#include <shape_msgs/msg/solid_primitive.hpp>
#include <urdf_parser/urdf_parser.h>

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  const std::string xml = R"(<robot name="review">
    <link name="world"/><link name="end_effector_link"/>
    <joint name="fixed" type="fixed"><parent link="world"/>
    <child link="end_effector_link"/></joint></robot>)";
  auto urdf = urdf::parseURDF(xml);
  auto srdf = std::make_shared<srdf::Model>();
  srdf->initString(*urdf, "<robot name=\"review\"/>");
  auto robot = std::make_shared<moveit::core::RobotModel>(urdf, srdf);
  planning_scene::PlanningScene scene(robot);

  moveit_msgs::msg::CollisionObject box;
  box.header.frame_id = "world";
  box.id = "target_box_a";
  box.operation = box.ADD;
  shape_msgs::msg::SolidPrimitive primitive;
  primitive.type = primitive.BOX;
  primitive.dimensions = {0.035, 0.035, 0.035};
  box.primitives.push_back(primitive);
  geometry_msgs::msg::Pose pose;
  pose.position.x = 0.22;
  pose.position.z = 0.0175;
  pose.orientation.w = 1.0;
  box.primitive_poses.push_back(pose);
  if (!scene.processCollisionObjectMsg(box)) return 2;
  moveit_msgs::msg::AttachedCollisionObject attached;
  attached.link_name = "end_effector_link";
  attached.object.id = box.id;
  attached.object.operation = attached.object.ADD;
  if (!scene.processAttachedCollisionObjectMsg(attached)) return 3;

  std::ifstream input(argv[1], std::ios::binary);
  std::vector<char> bytes((std::istreambuf_iterator<char>(input)), {});
  if (bytes.empty()) return 5;
  rclcpp::SerializedMessage serialized(bytes.size());
  auto& raw = serialized.get_rcl_serialized_message();
  std::memcpy(raw.buffer, bytes.data(), bytes.size());
  raw.buffer_length = bytes.size();
  moveit_msgs::msg::PlanningScene cleanup;
  rclcpp::Serialization<moveit_msgs::msg::PlanningScene>().deserialize_message(&serialized, &cleanup);
  scene.setPlanningSceneDiffMsg(cleanup);
  const bool cleared = !scene.getCurrentState().hasAttachedBody(box.id) && !scene.getWorld()->hasObject(box.id);
  std::cout << "python_cleanup_diff: cleared_attached_and_world=" << cleared << std::endl;
  box.operation = box.ADD;
  scene.processCollisionObjectMsg(box);
  const bool collision = scene.isStateColliding(scene.getCurrentState());
  std::cout << "retry_add_box: attached=" << scene.getCurrentState().hasAttachedBody(box.id)
            << " start_state_collision=" << collision << std::endl;
  rclcpp::shutdown();
  return cleared && !collision ? 0 : 4;
}
