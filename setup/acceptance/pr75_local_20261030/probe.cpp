// Offline diagnostic only. No ROS actuator clients or simulator are created.
#include <rclcpp/rclcpp.hpp>
#include <moveit/robot_model_loader/robot_model_loader.hpp>
#include <moveit/constraint_samplers/default_constraint_samplers.hpp>
#include <moveit/kinematic_constraints/kinematic_constraint.hpp>
#include "position_only_planner.hpp"
#include <iomanip>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<rclcpp::Node>("pr75_ik_probe", rclcpp::NodeOptions()
      .automatically_declare_parameters_from_overrides(true));
  robot_model_loader::RobotModelLoader loader(node, "robot_description");
  auto model = loader.getModel();
  if (!model) throw std::runtime_error("robot model unavailable");
  auto scene = std::make_shared<planning_scene::PlanningScene>(model);
  auto reference = scene->getCurrentState();
  reference.setToDefaultValues();
  reference.setVariablePositions(node->get_parameter("probe.names").as_string_array(),
                                 node->get_parameter("probe.positions").as_double_array());
  reference.update();
  scene->setCurrentState(reference);
  const auto* group = model->getJointModelGroup("arm");
  auto solver = group ? group->getSolverInstance() : nullptr;
  if (!solver) throw std::runtime_error("loaded arm IK solver unavailable");
  const std::string link = "end_effector_link";
  const auto& world_link = reference.getGlobalLinkTransform(link);
  auto box = node->get_parameter("probe.box_pose").as_double_array();
  const Eigen::Vector3d box_position(box[0], box[1], box[2]);
  Eigen::Isometry3d offset = Eigen::Isometry3d::Identity();
  offset.translation() = world_link.inverse() * box_position;
  std::vector<double> seed;
  for (const auto& name : solver->getJointNames()) seed.push_back(reference.getVariablePosition(name));
  const auto world_base = reference.getFrameTransform(solver->getBaseFrame());
  const auto link_tip = world_link.inverse() * reference.getGlobalLinkTransform(solver->getTipFrame());
  std::cout << std::setprecision(17);
  std::cout << "{\"kind\":\"geometry\",\"base\":\"" << solver->getBaseFrame()
            << "\",\"tip\":\"" << solver->getTipFrame() << "\",\"offset\":["
            << offset.translation().x() << ',' << offset.translation().y() << ','
            << offset.translation().z() << "]}\n";
  int controls = 0, nonzero_valid = 0, nonzero_ik = 0;
  for (int mode = 0; mode < 3; ++mode) {
    const char* label = mode == 0 ? "zero_offset_control" : mode == 1 ? "known_reachable_offset" : "place_hover_offset";
    auto frame = offset;
    if (mode == 0) frame.setIdentity();
    Eigen::Isometry3d target = Eigen::Isometry3d::Identity();
    target.translation() = mode == 0 ? world_link.translation() : box_position;
    if (mode == 2) {
      auto hover = node->get_parameter("probe.hover").as_double_array();
      target.translation() = Eigen::Vector3d(hover[0], hover[1], hover[2]);
    }
    const auto constraints = flexcell::positionGoal("world", link, frame, target, 1e-4);
    kinematic_constraints::PositionConstraint check(model);
    if (!check.configure(constraints.position_constraints.front(), scene->getTransforms()))
      throw std::runtime_error("position constraint not configured");
    constraint_samplers::IKConstraintSampler sampler(scene, "arm", 75);
    if (!sampler.configure(constraints)) throw std::runtime_error("upstream sampler not configured");
    std::cout << "{\"kind\":\"reference\",\"case\":\"" << label << "\",\"constraint_satisfied\":"
              << (check.decide(reference).satisfied ? "true" : "false") << "}\n";
    for (int i = 0; i < 16; ++i) {
      Eigen::Vector3d position;
      Eigen::Quaterniond sampled_rotation;
      if (!sampler.samplePose(position, sampled_rotation, reference, 1))
        throw std::runtime_error("upstream could not sample a pose");
      Eigen::Isometry3d query = Eigen::Isometry3d::Identity();
      query.translation() = position;
      query.linear() = sampled_rotation.toRotationMatrix();
      query = world_base.inverse() * query * link_tip;
      geometry_msgs::msg::Pose pose;
      pose.position.x = query.translation().x(); pose.position.y = query.translation().y(); pose.position.z = query.translation().z();
      const Eigen::Quaterniond rotation(query.linear());
      pose.orientation.x = rotation.x(); pose.orientation.y = rotation.y();
      pose.orientation.z = rotation.z(); pose.orientation.w = rotation.w();
      std::vector<double> solution;
      moveit_msgs::msg::MoveItErrorCodes error;
      const bool ik = solver->searchPositionIK(pose, seed, .005, solution, error);
      std::cout << "{\"kind\":\"attempt\",\"case\":\"" << label << "\",\"index\":" << i
                << ",\"ik_success\":" << (ik ? "true" : "false");
      if (ik) {
        auto state = reference;
        state.setVariablePositions(solver->getJointNames(), solution); state.update();
        const auto& actual = state.getGlobalLinkTransform(link);
        const double point_error = (actual * frame.translation() - target.translation()).norm();
        const double link_error = (actual.translation() - position).norm();
        const bool valid = check.decide(state).satisfied;
        std::cout << ",\"link_position_error_m\":" << link_error << ",\"point_error_m\":" << point_error
                  << ",\"constraint_satisfied\":" << (valid ? "true" : "false");
        if (mode == 0 && valid) ++controls;
        if (mode == 1) { ++nonzero_ik; if (valid) ++nonzero_valid; }
      }
      std::cout << "}\n";
    }
    auto state = reference;
    constraint_samplers::IKConstraintSampler complete(scene, "arm", 75);
    if (!complete.configure(constraints)) throw std::runtime_error("complete sampler not configured");
    const bool sampled = complete.sample(state, reference, 16);
    std::cout << "{\"kind\":\"complete_sampler\",\"case\":\"" << label
              << "\",\"success\":" << (sampled ? "true" : "false") << "}\n";
  }
  std::cout << "{\"kind\":\"summary\",\"control_valid\":" << controls
            << ",\"reachable_offset_ik_solutions\":" << nonzero_ik
            << ",\"reachable_offset_valid\":" << nonzero_valid << "}\n";
  rclcpp::shutdown();
  return controls > 0 && nonzero_ik > 0 && nonzero_valid == 0 ? 0 : 2;
}
