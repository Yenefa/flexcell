#pragma once
#include <moveit/task_constructor/solvers/pipeline_planner.h>
#include <moveit/kinematic_constraints/utils.hpp>
#include <moveit/robot_state/robot_state.h>
#include <moveit/planning_scene/planning_scene.hpp>
#include <cmath>
#include <limits>
#include <random>
#include <string>
#include <vector>

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

// Issue #121. The four-DOF arm (joint1 about Z, joint2/3/4 about parallel Y)
// leaves exactly one redundant degree of freedom: the end-effector pitch
// phi = j2+j3+j4. position_only_ik never constrains phi, so the carried box can
// be released tilted, land on an edge and tip over (measured: h*(1-cos+sin),
// RMSE 1.12 mm, 72/72 shifts aligned with the tilt direction).
//
// This adapter samples several IK seeds, keeps the collision-free solution with
// the smallest |phi|, and hands that single goal configuration to the upstream
// PipelinePlanner, which still plans and validates the whole trajectory against
// the propagated scene. It does not freeze an unchecked IK solution: the goal
// state is collision-checked here and the path is collision-checked upstream.
// Opt-in only - max_pitch_rad < 0 reproduces PositionOnlyPlanner exactly.
class LevelPitchPlanner : public moveit::task_constructor::solvers::PipelinePlanner {
 public:
  using PipelinePlanner::PipelinePlanner;
  using PipelinePlanner::plan;

  double max_pitch_rad = -1.0;      // < 0 disables; otherwise the |phi| ceiling
  int seed_count = 16;              // deterministic seeds, seed 0 = current state
  double joint_tolerance = 1e-3;    // rad, goal joint band around the chosen IK

  double last_pitch_rad() const { return last_pitch_rad_; }
  bool last_was_level_seed() const { return last_level_; }
  int last_sampled_seeds() const { return last_sampled_; }

  Result plan(const planning_scene::PlanningSceneConstPtr& scene, const moveit::core::LinkModel& link,
      const Eigen::Isometry3d& offset, const Eigen::Isometry3d& target,
      const moveit::core::JointModelGroup* group, double timeout,
      robot_trajectory::RobotTrajectoryPtr& result,
      const moveit_msgs::msg::Constraints& path_constraints) override {
    last_pitch_rad_ = std::numeric_limits<double>::quiet_NaN();
    last_level_ = false;
    last_sampled_ = 0;
    if (!(max_pitch_rad >= 0.0) || !std::isfinite(max_pitch_rad))
      return PipelinePlanner::plan(scene, group, positionGoal(scene->getPlanningFrame(), link.getName(),
          offset, target, properties().get<double>("goal_position_tolerance")), timeout, result, path_constraints);

    const auto& names = group->getVariableNames();
    int i2 = -1, i3 = -1, i4 = -1;
    for (size_t i = 0; i < names.size(); ++i) {
      if (names[i] == "joint2") i2 = static_cast<int>(i);
      else if (names[i] == "joint3") i3 = static_cast<int>(i);
      else if (names[i] == "joint4") i4 = static_cast<int>(i);
    }
    // Not the four-DOF arm this rule was derived for: keep previous behaviour.
    if (i2 < 0 || i3 < 0 || i4 < 0)
      return PipelinePlanner::plan(scene, group, positionGoal(scene->getPlanningFrame(), link.getName(),
          offset, target, properties().get<double>("goal_position_tolerance")), timeout, result, path_constraints);

    moveit::core::RobotState base(scene->getCurrentState());
    Eigen::Isometry3d link_target = base.getGlobalLinkTransform(link.getName());
    link_target.translation() = target.translation() - offset.translation();

    double best_abs = std::numeric_limits<double>::infinity();
    std::vector<double> best;
    std::mt19937 rng(0x121u);  // deterministic: same input, same seed sequence
    for (int k = 0; k < seed_count; ++k) {
      moveit::core::RobotState candidate(base);
      if (k > 0) {
        for (size_t i = 0; i < names.size(); ++i) {
          const auto& bounds = candidate.getRobotModel()->getVariableBounds(names[i]);
          if (!std::isfinite(bounds.min_position_) || !std::isfinite(bounds.max_position_)) continue;
          std::uniform_real_distribution<double> uniform(bounds.min_position_, bounds.max_position_);
          candidate.setVariablePosition(i, uniform(rng));
        }
      }
      candidate.update();
      if (!candidate.setFromIK(group, link_target, link.getName(), timeout)) continue;
      ++last_sampled_;
      const double pitch = candidate.getVariablePosition(i2) + candidate.getVariablePosition(i3) +
                           candidate.getVariablePosition(i4);
      if (std::abs(pitch) >= best_abs) continue;
      if (scene->isStateColliding(candidate, group->getName())) continue;
      best_abs = std::abs(pitch);
      best.assign(candidate.getVariablePositions(), candidate.getVariablePositions() + candidate.getVariableCount());
    }

    if (best.empty())  // no collision-free candidate: fall back, never guess
      return PipelinePlanner::plan(scene, group, positionGoal(scene->getPlanningFrame(), link.getName(),
          offset, target, properties().get<double>("goal_position_tolerance")), timeout, result, path_constraints);

    last_pitch_rad_ = best[i2] + best[i3] + best[i4];
    last_level_ = best_abs <= max_pitch_rad;
    moveit_msgs::msg::Constraints goal;
    for (size_t i = 0; i < names.size(); ++i) {
      moveit_msgs::msg::JointConstraint joint;
      joint.joint_name = names[i];
      joint.position = best[i];
      joint.tolerance_above = joint_tolerance;
      joint.tolerance_below = joint_tolerance;
      joint.weight = 1.0;
      goal.joint_constraints.push_back(joint);
    }
    return PipelinePlanner::plan(scene, group, goal, timeout, result, path_constraints);
  }

 private:
  double last_pitch_rad_ = std::numeric_limits<double>::quiet_NaN();
  bool last_level_ = false;
  int last_sampled_ = 0;
};
}
