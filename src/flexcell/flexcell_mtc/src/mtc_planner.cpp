// No actuator client here. MTC plans; skills own execution and physics.
#include <rclcpp/rclcpp.hpp>
#include <flexcell_interfaces/srv/plan_manipulation.hpp>
#include <moveit_msgs/srv/get_planning_scene.hpp>
#include <moveit/task_constructor/task.h>
#include <moveit/task_constructor/stages/fixed_state.h>
#include <moveit/task_constructor/stages/move_to.h>
#include <moveit/task_constructor/stages/move_relative.h>
#include <moveit/task_constructor/stages/modify_planning_scene.h>
#include <moveit/task_constructor/solvers/pipeline_planner.h>
#include <moveit/task_constructor/solvers/joint_interpolation.h>
#include <moveit/planning_scene/planning_scene.hpp>
#include <moveit_task_constructor_msgs/msg/solution.hpp>
#include <shape_msgs/msg/solid_primitive.hpp>
#include <geometry_msgs/msg/point_stamped.hpp>
#include <geometry_msgs/msg/vector3_stamped.hpp>
#include <moveit/robot_state/attached_body.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <mutex>
#include <sstream>
#include "position_only_planner.hpp"
#include "attached_object_goal.hpp"
#include "attached_point_model.hpp"
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
        !profiles.count(q.motion_profile_id) || q.deadline_ms < 1000 || q.deadline_ms > 60000 ||
        (q.attached_object_targets && pick))
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
    // Keep the private model's plugin loader alive through task destruction.
    robot_model_loader::RobotModelLoaderPtr point_model;
    mtc::Task task;
    task.setName("FlexCell " + q.operation); task.enableIntrospection(false);
    task.loadRobotModel(shared_from_this());
    auto scene = std::make_shared<planning_scene::PlanningScene>(task.getRobotModel());
    const auto measured = future.get();
    scene->setPlanningSceneMsg(measured->scene);
    const auto* arm = task.getRobotModel()->getJointModelGroup("arm");
    if (!arm) throw std::runtime_error("arm group missing");
    const auto measured_state = scene->getCurrentState();
    if (!pick && !measured_state.hasAttachedBody(q.object_name))
      throw std::runtime_error("PLACE object not attached in measured scene");
    if (q.attached_object_targets) {
      const auto* body = measured_state.getAttachedBody(q.object_name);
      if (body->getAttachedLinkName() != "end_effector_link" || body->getShapes().size() != 1 ||
          body->getShapePosesInLinkFrame().size() != 1)
        throw std::runtime_error("joint PLACE requires one measured end-effector-attached shape");
      const auto shape_frame = body->getShapePosesInLinkFrame().front();
      flexcell::checkAttachedObjectPose(measured_state.getGlobalLinkTransform("end_effector_link"), shape_frame, q.object_pose);
      point_model = flexcell::attachedPointModel(shared_from_this(), shape_frame.translation());
      task.setRobotModel(point_model->getModel());
      scene = std::make_shared<planning_scene::PlanningScene>(task.getRobotModel());
      scene->setPlanningSceneMsg(measured->scene);
    }
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
    }
    auto pipeline = std::make_shared<flexcell::PositionOnlyPlanner>(shared_from_this(), "ompl");
    pipeline->setMaxVelocityScalingFactor(profiles.at(q.motion_profile_id));
    pipeline->setMaxAccelerationScalingFactor(profiles.at(q.motion_profile_id));
    const char* pick_names[] = {"hover", "grasp", "lift"};
    const char* place_names[] = {"hover", "descend", "retreat"};
    for (size_t i = 0; i < 3; ++i) {
      if (q.attached_object_targets && i == 2) {
        // Once detached, retreat the EE from its propagated descend endpoint.
        // Reuse MTC's relative stage with the same position-only planner.
        geometry_msgs::msg::Vector3Stamped direction;
        direction.header.frame_id = "world";
        direction.vector.x = q.targets[2].pose.position.x - q.targets[1].pose.position.x;
        direction.vector.y = q.targets[2].pose.position.y - q.targets[1].pose.position.y;
        direction.vector.z = q.targets[2].pose.position.z - q.targets[1].pose.position.z;
        if (std::abs(direction.vector.x) > 1e-9 || std::abs(direction.vector.y) > 1e-9 ||
            direction.vector.z <= 0. || direction.vector.z > .3)
          throw std::runtime_error("joint PLACE retreat must be a positive world-vertical displacement");
        auto retreat = std::make_unique<mtc::stages::MoveRelative>("retreat", pipeline);
        retreat->setGroup("arm"); retreat->setIKFrame("end_effector_link"); retreat->setDirection(direction);
        retreat->setTimeout(std::min(5.0, q.deadline_ms / 3000.0)); task.add(std::move(retreat));
        continue;
      }
      // PointStamped is MTC's native position-only goal: keep the four-DOF
      // contract while letting the planner sample collision-valid IK in each
      // propagated stage scene. Do not freeze one unchecked IK joint solution.
      geometry_msgs::msg::PointStamped target;
      target.header = q.targets[i].header;
      target.point = q.targets[i].pose.position;
      auto move = std::make_unique<mtc::stages::MoveTo>(pick ? pick_names[i] : place_names[i], pipeline);
      move->setGroup(q.attached_object_targets ? flexcell::pointGroup : "arm");
      move->setIKFrame(q.attached_object_targets ? flexcell::pointLink : "end_effector_link");
      move->setGoal(target);
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
    if (!task.plan(1) || task.solutions().empty()) {
      std::ostringstream detail;
      detail << "no complete MTC solution; operation=" << q.operation << "; object=" << q.object_name << '\n';
      task.printState(detail);
      task.explainFailure(detail);
      task.stages()->traverseRecursively([&](const mtc::Stage& stage, unsigned int) {
        for (const auto& failure : stage.failures())
          detail << stage.name() << ": " << failure->comment() << '\n';
        return true;
      });
      const auto report = detail.str();
      RCLCPP_ERROR(get_logger(), "%s", report.c_str());
      throw std::runtime_error(report.substr(0, 8192));
    }
    moveit_task_constructor_msgs::msg::Solution solution;
    task.solutions().front()->toMsg(solution);
    for (const auto& part : solution.sub_trajectory) {
      const auto& names = part.trajectory.joint_trajectory.joint_names;
      if (names.size() == 4 && std::find(names.begin(), names.end(), "joint1") != names.end()) {
        if (part.trajectory.joint_trajectory.points.empty()) throw std::runtime_error("empty arm stage");
        const auto& endpoint = part.trajectory.joint_trajectory.points.back().positions;
        if (endpoint.size() != names.size()) throw std::runtime_error("invalid arm endpoint");
        state.setVariablePositions(names, endpoint); state.update();
        const auto& transform = state.getGlobalLinkTransform("end_effector_link");
        geometry_msgs::msg::PoseStamped target;
        target.header.frame_id = "world";
        target.pose.position.x = transform.translation().x();
        target.pose.position.y = transform.translation().y();
        target.pose.position.z = transform.translation().z();
        const Eigen::Quaterniond rotation(transform.linear());
        target.pose.orientation.x = rotation.x(); target.pose.orientation.y = rotation.y();
        target.pose.orientation.z = rotation.z(); target.pose.orientation.w = rotation.w();
        r.executor_targets.push_back(target);
        r.trajectories.push_back(part.trajectory);
      }
    }
    if (r.trajectories.size() != 3) throw std::runtime_error("ambiguous arm stage extraction");
    r.success = true;
    r.detail = q.attached_object_targets ?
        "MTC planned attached shape-center hover/descend and relative EE retreat; explicit EE endpoints; execution remains skill-owned" :
        "MTC planned three position-only stages; execution and physics remain skill-owned";
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
