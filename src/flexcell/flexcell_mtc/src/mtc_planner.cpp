// No actuator client here. MTC plans; skills own execution and physics.
#include <rclcpp/rclcpp.hpp>
#include <flexcell_interfaces/srv/plan_manipulation.hpp>
#include <moveit_msgs/srv/get_planning_scene.hpp>
#include <moveit/task_constructor/task.h>
#include <moveit/task_constructor/stages/fixed_state.h>
#include <moveit/task_constructor/stages/move_to.h>
#include <moveit/task_constructor/stages/modify_planning_scene.h>
#include <moveit/task_constructor/solvers/pipeline_planner.h>
#include <moveit/task_constructor/solvers/joint_interpolation.h>
#include <moveit/planning_scene/planning_scene.hpp>
#include <moveit_task_constructor_msgs/msg/solution.hpp>
#include <shape_msgs/msg/solid_primitive.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <mutex>
namespace mtc = moveit::task_constructor;
using Service = flexcell_interfaces::srv::PlanManipulation;
using namespace std::chrono_literals;

class Planner : public rclcpp::Node {
 public:
  Planner() : Node("flexcell_mtc_planner", rclcpp::NodeOptions()
      .automatically_declare_parameters_from_overrides(true)) {
    group_ = create_callback_group(rclcpp::CallbackGroupType::Reentrant);
    scene_ = create_client<moveit_msgs::srv::GetPlanningScene>(
        "/get_planning_scene", rmw_qos_profile_services_default, group_);
    service_ = create_service<Service>("/flexcell/mtc/plan",
      [this](Service::Request::SharedPtr q, Service::Response::SharedPtr r) {
        std::unique_lock<std::mutex> lock(mutex_, std::try_to_lock);
        if (!lock.owns_lock()) { r->detail = "planner busy"; return; }
        try { plan(*q, *r); }
        catch (const std::exception& e) { r->success = false; r->detail = e.what(); }
      }, rmw_qos_profile_services_default, group_);
  }
 private:
  void plan(const Service::Request& q, Service::Response& r) {
    const bool pick = q.operation == "PICK";
    const std::map<std::string, double> profiles{{"demo_veryslow", .05},
                                               {"demo_slow", .2}, {"demo_default", .5}};
    if ((!pick && q.operation != "PLACE") || q.targets.size() != 3 ||
        (q.object_name != "target_box_a" && q.object_name != "target_box_b") ||
        !profiles.count(q.motion_profile_id) || q.deadline_ms < 1000 || q.deadline_ms > 60000)
      throw std::runtime_error("invalid operation, object, profile or stage count");
    for (const auto& t : q.targets) {
      const auto& p = t.pose.position;
      if (t.header.frame_id != "world" || !std::isfinite(p.x) || !std::isfinite(p.y) ||
          !std::isfinite(p.z) || std::abs(p.x) > .45 || std::abs(p.y) > .45 || p.z < -.15 || p.z > .75)
        throw std::runtime_error("target outside fixed workspace");
    }
    if (!scene_->wait_for_service(2s)) throw std::runtime_error("planning scene unavailable");
    auto query = std::make_shared<moveit_msgs::srv::GetPlanningScene::Request>();
    query->components.components = 1023;
    auto future = scene_->async_send_request(query);
    if (future.wait_for(3s) != std::future_status::ready) {
      scene_->remove_pending_request(future);
      throw std::runtime_error("planning scene timeout");
    }
    mtc::Task task;
    task.setName("FlexCell " + q.operation); task.enableIntrospection(false);
    task.loadRobotModel(shared_from_this());
    auto scene = std::make_shared<planning_scene::PlanningScene>(task.getRobotModel());
    scene->setPlanningSceneMsg(future.get()->scene);
    const auto* arm = task.getRobotModel()->getJointModelGroup("arm");
    if (!arm) throw std::runtime_error("arm group missing");
    auto state = scene->getCurrentState();
    task.add(std::make_unique<mtc::stages::FixedState>("measured scene", scene));
    auto gripper = std::make_shared<mtc::solvers::JointInterpolationPlanner>();
    gripper->setMaxVelocityScalingFactor(profiles.at(q.motion_profile_id));
    gripper->setMaxAccelerationScalingFactor(profiles.at(q.motion_profile_id));
    auto gripper_stage = [&](const std::string& name, double position) {
      auto stage = std::make_unique<mtc::stages::MoveTo>(name, gripper);
      stage->setGroup("gripper");
      stage->setGoal(std::map<std::string, double>{{"gripper_left_joint", position}});
      task.add(std::move(stage));
    };
    if (pick) {
      if (q.object_pose.header.frame_id != "world") throw std::runtime_error("invalid object frame");
      auto add = std::make_unique<mtc::stages::ModifyPlanningScene>("observed box");
      moveit_msgs::msg::CollisionObject box;
      box.id = q.object_name; box.header.frame_id = "world";
      box.operation = moveit_msgs::msg::CollisionObject::ADD;
      shape_msgs::msg::SolidPrimitive shape;
      shape.type = shape_msgs::msg::SolidPrimitive::BOX; shape.dimensions = {.035, .035, .035};
      box.primitives.push_back(shape); box.primitive_poses.push_back(q.object_pose.pose);
      add->addObject(box); task.add(std::move(add));
      gripper_stage("open gripper", .02);
    } else if (!state.hasAttachedBody(q.object_name)) {
      throw std::runtime_error("PLACE object not attached in measured scene");
    }
    auto pipeline = std::make_shared<mtc::solvers::PipelinePlanner>(shared_from_this(), "ompl");
    pipeline->setMaxVelocityScalingFactor(profiles.at(q.motion_profile_id));
    pipeline->setMaxAccelerationScalingFactor(profiles.at(q.motion_profile_id));
    const char* pick_names[] = {"hover", "grasp", "lift"};
    const char* place_names[] = {"hover", "descend", "retreat"};
    for (size_t i = 0; i < 3; ++i) {
      // The configured four-DOF IK is position-only. Plan collision-checked
      // joint goals rather than asking a four-DOF arm for a six-DOF pose goal.
      const auto& p = q.targets[i].pose.position;
      Eigen::Isometry3d target = state.getGlobalLinkTransform("end_effector_link");
      target.translation() = Eigen::Vector3d(p.x, p.y, p.z);
      if (!state.setFromIK(arm, target, "end_effector_link", 1.0))
        throw std::runtime_error("IK failed at stage " + std::to_string(i));
      std::map<std::string, double> joints;
      for (const auto& name : arm->getVariableNames()) joints[name] = state.getVariablePosition(name);
      auto move = std::make_unique<mtc::stages::MoveTo>(pick ? pick_names[i] : place_names[i], pipeline);
      move->setGroup("arm"); move->setGoal(joints);
      move->setTimeout(std::min(5.0, q.deadline_ms / 3000.0)); task.add(std::move(move));
      if (i == 1) {
        if (pick) gripper_stage("close gripper", -.011);
        auto attach = std::make_unique<mtc::stages::ModifyPlanningScene>(
            pick ? "planning scene attach" : "planning scene detach");
        if (pick) attach->attachObject(q.object_name, "end_effector_link");
        else attach->detachObject(q.object_name, "end_effector_link");
        task.add(std::move(attach));
        if (!pick) gripper_stage("open gripper", .02);
      }
    }
    task.setTimeout(q.deadline_ms / 1000.0); task.init();
    if (!task.plan(1) || task.solutions().empty()) throw std::runtime_error("no complete MTC solution");
    moveit_task_constructor_msgs::msg::Solution solution;
    task.solutions().front()->toMsg(solution);
    for (const auto& part : solution.sub_trajectory) {
      const auto& names = part.trajectory.joint_trajectory.joint_names;
      if (names.size() == 4 && std::find(names.begin(), names.end(), "joint1") != names.end())
        r.trajectories.push_back(part.trajectory);
    }
    if (r.trajectories.size() != 3) throw std::runtime_error("ambiguous arm stage extraction");
    r.success = true; r.detail = "MTC planned three stages; execution and physics remain skill-owned";
  }
  std::mutex mutex_;
  rclcpp::CallbackGroup::SharedPtr group_;
  rclcpp::Client<moveit_msgs::srv::GetPlanningScene>::SharedPtr scene_;
  rclcpp::Service<Service>::SharedPtr service_;
};
int main(int argc, char** argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<Planner>();
  rclcpp::executors::MultiThreadedExecutor executor(rclcpp::ExecutorOptions(), 4);
  executor.add_node(node); executor.spin(); rclcpp::shutdown(); return 0;
}
