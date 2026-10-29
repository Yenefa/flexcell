#pragma once
#include <moveit/task_constructor/solvers/pipeline_planner.h>
#include <moveit/kinematic_constraints/utils.hpp>

namespace flexcell {
inline moveit_msgs::msg::Constraints positionGoal(const std::string& frame, const std::string& link,
    const Eigen::Isometry3d& offset, const Eigen::Isometry3d& target, double tolerance) {
  geometry_msgs::msg::Point reference;
  reference.x = offset.translation().x(); reference.y = offset.translation().y(); reference.z = offset.translation().z();
  geometry_msgs::msg::PointStamped goal;
  goal.header.frame_id = frame;
  goal.point.x = target.translation().x(); goal.point.y = target.translation().y(); goal.point.z = target.translation().z();
  return kinematic_constraints::constructGoalConstraints(link, reference, goal, tolerance);
}

// MTC's stock PointStamped path retains orientation when it builds a pose
// constraint. This four-DOF adapter instead uses MoveIt's official point-only
// constraint builder; all collision checking and stage-scene propagation stay
// in the upstream PipelinePlanner. No retry loop or fixed IK solution is added.
class PositionOnlyPlanner final : public moveit::task_constructor::solvers::PipelinePlanner {
 public:
  using PipelinePlanner::PipelinePlanner;
  using PipelinePlanner::plan;
  Result plan(const planning_scene::PlanningSceneConstPtr& scene, const moveit::core::LinkModel& link,
      const Eigen::Isometry3d& offset, const Eigen::Isometry3d& target,
      const moveit::core::JointModelGroup* group, double timeout,
      robot_trajectory::RobotTrajectoryPtr& result,
      const moveit_msgs::msg::Constraints& path_constraints) override {
    return PipelinePlanner::plan(scene, group, positionGoal(scene->getPlanningFrame(), link.getName(),
        offset, target, properties().get<double>("goal_position_tolerance")), timeout, result, path_constraints);
  }
};
}
