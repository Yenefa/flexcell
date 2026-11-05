#pragma once
#include <moveit/task_constructor/solvers/pipeline_planner.h>
#include <moveit/kinematic_constraints/utils.hpp>
#include <moveit/robot_state/robot_state.h>
#include <moveit/planning_scene/planning_scene.hpp>
#include <algorithm>
#include <chrono>
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
class PositionOnlyPlanner : public moveit::task_constructor::solvers::PipelinePlanner {
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
// leaves exactly one redundant degree of freedom. position_only_ik never
// constrains it, so the carried box can be released tilted, land on an edge
// and tip over (measured: h*(1-cos+sin), RMSE 1.12 mm, 72/72 shifts aligned
// with the tilt direction).
//
// The quantity that matters is the ATTACHED BOX attitude in world frame, not
// the end-effector pitch: the measured attachment carries a rotational offset
// (about -7.25 deg of box pitch relative to the EE in the recorded fixture),
// so a level EE leaves the box tilted. Candidates are therefore ranked by the
// world-frame box up-vector tilt  acos((R_link * R_attach * z).z()).
//
// The adapter samples deterministic IK seeds, keeps the collision-free
// solution with the smallest box tilt, and hands that single goal
// configuration to the upstream PipelinePlanner, which still plans and
// validates the whole trajectory against the propagated scene; the goal state
// is collision-checked here, so no unchecked IK solution is frozen.
// Opt-in only - max_box_tilt_rad < 0 reproduces PositionOnlyPlanner exactly.
// One elapsed-time budget covers IK sampling AND path planning so one stage
// can never occupy the planner mutex longer than its stage timeout.
class LevelPitchPlanner : public moveit::task_constructor::solvers::PipelinePlanner {
 public:
  using PipelinePlanner::PipelinePlanner;
  using PipelinePlanner::plan;

  double max_box_tilt_rad = -1.0;   // < 0 disables; otherwise the box-tilt ceiling
  Eigen::Matrix3d attach_rotation = Eigen::Matrix3d::Identity();  // box frame relative to EE
  int seed_count = 16;              // deterministic seeds, seed 0 = current state
  double joint_tolerance = 1e-3;    // rad, goal joint band around the chosen IK
  double sampling_share = 0.5;      // fraction of the stage timeout for IK sampling

  double last_box_tilt_rad() const { return last_box_tilt_rad_; }
  bool last_was_level() const { return last_level_; }
  int last_sampled_seeds() const { return last_sampled_; }

  Result plan(const planning_scene::PlanningSceneConstPtr& scene, const moveit::core::LinkModel& link,
      const Eigen::Isometry3d& offset, const Eigen::Isometry3d& target,
      const moveit::core::JointModelGroup* group, double timeout,
      robot_trajectory::RobotTrajectoryPtr& result,
      const moveit_msgs::msg::Constraints& path_constraints) override {
    last_box_tilt_rad_ = std::numeric_limits<double>::quiet_NaN();
    last_level_ = false;
    last_sampled_ = 0;
    const auto fallback = [&]() {
      return PipelinePlanner::plan(scene, group, positionGoal(scene->getPlanningFrame(), link.getName(),
          offset, target, properties().get<double>("goal_position_tolerance")), timeout, result, path_constraints);
    };
    if (!(max_box_tilt_rad >= 0.0) || !std::isfinite(max_box_tilt_rad)) return fallback();

    const auto& names = group->getVariableNames();
    const bool four_dof = std::count(names.begin(), names.end(), "joint2") &&
                          std::count(names.begin(), names.end(), "joint3") &&
                          std::count(names.begin(), names.end(), "joint4");
    // Not the four-DOF arm this rule was derived for: keep previous behaviour.
    if (!four_dof) return fallback();

    const auto started = std::chrono::steady_clock::now();
    const auto elapsed = [&] {
      return std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    };
    const double ik_timeout = std::max(0.05, timeout * sampling_share / std::max(1, seed_count));

    moveit::core::RobotState base(scene->getCurrentState());
    Eigen::Isometry3d link_target = base.getGlobalLinkTransform(link.getName());
    link_target.translation() = target.translation() - offset.translation();

    double best_tilt = std::numeric_limits<double>::infinity();
    std::vector<double> best;
    std::mt19937 rng(0x121u);  // deterministic: same input, same seed sequence
    for (int k = 0; k < seed_count; ++k) {
      // Leave the remaining share for the upstream path planning.
      if (elapsed() >= timeout * sampling_share) break;
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
      if (!candidate.setFromIK(group, link_target, link.getName(), ik_timeout)) continue;
      ++last_sampled_;
      // Rank by the world-frame box up-vector tilt, not by the EE pitch: the
      // measured attachment carries a rotational offset (review finding).
      const Eigen::Matrix3d rotation = candidate.getGlobalLinkTransform(link.getName()).linear();
      const Eigen::Vector3d box_up = rotation * attach_rotation * Eigen::Vector3d::UnitZ();
      if (!box_up.allFinite() || std::abs(box_up.norm() - 1.0) > 1e-3) continue;
      const double tilt = std::acos(std::clamp(box_up.z(), -1.0, 1.0));
      if (!(tilt < best_tilt)) continue;
      if (scene->isStateColliding(candidate, group->getName())) continue;
      best_tilt = tilt;
      best.clear();
      for (const auto& name : names) best.push_back(candidate.getVariablePosition(name));
    }

    if (best.empty())  // no collision-free candidate: fall back, never guess
      return fallback();

    last_box_tilt_rad_ = best_tilt;
    last_level_ = best_tilt <= max_box_tilt_rad;
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
    const double plan_timeout = std::max(0.5, timeout - elapsed());
    return PipelinePlanner::plan(scene, group, goal, plan_timeout, result, path_constraints);
  }

 private:
  double last_box_tilt_rad_ = std::numeric_limits<double>::quiet_NaN();
  bool last_level_ = false;
  int last_sampled_ = 0;
};
}
