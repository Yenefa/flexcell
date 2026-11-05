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
// The redundant coordinate phi = j2+j3+j4 is enumerated EXPLICITLY with a
// closed-form planar 3R IK (v1=(0.024,0.128), v2=(0.124,0), v3=(0.126,0);
// pe = box_local - Ry(phi)*attach_translation; pj4 = pe - Ry(phi)*v3;
// cos(a1+j3) = (|pj4-(0,0,0.0595)|^2 - L1^2 - L2^2)/(2 L1 L2);
// j2 from the two-link closure; j4 = phi - j2 - j3). This is deterministic:
// setFromIK was tried first and proved unreliable (identical seeds produced
// 19.7 / 0.25 / 2.0 deg of box tilt across runs because KDL restarts
// randomly and the per-call timeout truncation is load-sensitive).
// Every closed-form candidate is FK-verified against the box target,
// joint-limit-checked and collision-checked, and the best one is handed to
// the upstream PipelinePlanner, which still plans and validates the whole
// trajectory. Opt-in only - max_box_tilt_rad < 0 reproduces
// PositionOnlyPlanner exactly. One elapsed-time budget covers enumeration
// AND path planning so one stage can never occupy the planner mutex longer
// than its stage timeout.
class LevelPitchPlanner : public moveit::task_constructor::solvers::PipelinePlanner {
 public:
  using PipelinePlanner::PipelinePlanner;
  using PipelinePlanner::plan;

  static constexpr const char* kJointNames[4] = {"joint1", "joint2", "joint3", "joint4"};

  double max_box_tilt_rad = -1.0;   // < 0 disables; otherwise the box-tilt ceiling
  Eigen::Matrix3d attach_rotation = Eigen::Matrix3d::Identity();  // box frame relative to EE
  Eigen::Vector3d attach_translation = Eigen::Vector3d::Zero();   // box centre relative to EE
  int phi_step_deg = 1;             // null-space enumeration step
  double joint_tolerance = 1e-3;    // rad, goal joint band around the chosen IK
  double sampling_share = 0.5;      // fraction of the stage timeout for enumeration

  double last_box_tilt_rad() const { return last_box_tilt_rad_; }
  bool last_was_level() const { return last_level_; }
  int last_enumerated() const { return last_enumerated_; }
  double last_min_position_error_m() const { return last_min_position_error_m_; }

  Result plan(const planning_scene::PlanningSceneConstPtr& scene, const moveit::core::LinkModel& link,
      const Eigen::Isometry3d& offset, const Eigen::Isometry3d& target,
      const moveit::core::JointModelGroup* group, double timeout,
      robot_trajectory::RobotTrajectoryPtr& result,
      const moveit_msgs::msg::Constraints& path_constraints) override {
    last_box_tilt_rad_ = std::numeric_limits<double>::quiet_NaN();
    last_level_ = false;
    last_enumerated_ = 0;
    last_min_position_error_m_ = std::numeric_limits<double>::infinity();
    const auto fallback = [&]() {
      return PipelinePlanner::plan(scene, group, positionGoal(scene->getPlanningFrame(), link.getName(),
          offset, target, properties().get<double>("goal_position_tolerance")), timeout, result, path_constraints);
    };
    if (!(max_box_tilt_rad >= 0.0) || !std::isfinite(max_box_tilt_rad)) return fallback();

    const auto& names = group->getVariableNames();
    const bool four_dof = names.size() == 4 &&
                          std::count(names.begin(), names.end(), "joint1") &&
                          std::count(names.begin(), names.end(), "joint2") &&
                          std::count(names.begin(), names.end(), "joint3") &&
                          std::count(names.begin(), names.end(), "joint4");
    // Not the four-DOF arm this rule was derived for: keep previous behaviour.
    if (!four_dof) return fallback();

    const auto started = std::chrono::steady_clock::now();
    const auto elapsed = [&] {
      return std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    };

    // goal == attached box centre in world: the stage constrains the private
    // point link, a fixed child of end_effector_link at attach_translation
    // with identity rotation, so the point origin IS the box centre. The EE
    // sits at goal - R_ee * attach_translation, with R_ee = Rz(j1)*Ry(phi).
    const Eigen::Vector3d goal = target.translation();
    const double j1 = std::atan2(goal.y(), goal.x() - 0.012);
    const double r = std::hypot(goal.x() - 0.012, goal.y());
    const Eigen::Matrix3d rot_attach = attach_rotation;
    const Eigen::Vector3d up_ee = rot_attach * Eigen::Vector3d::UnitZ();

    double best_tilt = std::numeric_limits<double>::infinity();
    std::vector<double> best;
    moveit::core::RobotState candidate(scene->getCurrentState());
    const int span = 30;
    for (int deg = -span; deg <= span; deg += std::max(1, phi_step_deg)) {
      // Leave the remaining share for the upstream path planning.
      if (elapsed() >= timeout * sampling_share) break;
      const double phi = deg * 3.14159265358979323846 / 180.0;
      const double cp = std::cos(phi), sp = std::sin(phi);
      // EE position (local) that puts the box centre on target.
      const double pex = r - (attach_translation.x() * cp + attach_translation.z() * sp);
      const double pez = goal.z() - (-attach_translation.x() * sp + attach_translation.z() * cp);
      // joint4 position (local), then the two-link closure to joint2.
      const double pj4x = pex - (0.126 * cp);
      const double pj4z = pez - (-0.126 * sp);
      const double wx = pj4x;
      const double wz = pj4z - 0.0595;
      const double d2 = wx * wx + wz * wz;
      const double cosk = (d2 - 0.01696 - 0.015376) / (2 * 0.130223 * 0.124);
      if (std::abs(cosk) > 1.0) continue;
      for (const double sign : {1.0, -1.0}) {
        const double j3 = sign * std::acos(std::clamp(cosk, -1.0, 1.0)) - 1.385448;
        const double j2 = std::atan2(0.128 - 0.124 * std::sin(j3),
                                     0.024 + 0.124 * std::cos(j3)) - std::atan2(wz, wx);
        const double j4 = phi - j2 - j3;
        const std::vector<double> q{j1, j2, j3, j4};
        bool inside = true;
        for (int i = 0; i < 4; ++i) {
          const auto& bounds = candidate.getRobotModel()->getVariableBounds(kJointNames[i]);
          if (!std::isfinite(bounds.min_position_) || !std::isfinite(bounds.max_position_)) continue;
          if (q[i] < bounds.min_position_ || q[i] > bounds.max_position_) { inside = false; break; }
        }
        if (!inside) continue;
        // Map by NAME, never by group-variable order: the closed form is
        // defined on (joint1..joint4).
        for (int i = 0; i < 4; ++i) candidate.setVariablePosition(kJointNames[i], q[i]);
        candidate.update();
        // FK-verify against TRUE model FK. The IK frame is the private point
        // link: a fixed child of the EE at attach_translation with identity
        // rotation, so the link origin IS the attached box centre. (An earlier
        // version added attach_translation to the point-link pose again,
        // double-counted the ~0.158 m offset and rejected every candidate.)
        const auto& tip = candidate.getGlobalLinkTransform(link.getName());
        const double position_error = (tip.translation() - goal).norm();
        if (position_error < last_min_position_error_m_) last_min_position_error_m_ = position_error;
        if (position_error > 0.001) continue;
        ++last_enumerated_;
        // tip.linear() == R_ee (identity fixed joint), so this is the
        // world-frame box up-vector.
        const Eigen::Vector3d box_up = tip.linear() * rot_attach * Eigen::Vector3d::UnitZ();
        if (!box_up.allFinite() || std::abs(box_up.norm() - 1.0) > 1e-3) continue;
        const double tilt = std::acos(std::clamp(box_up.z(), -1.0, 1.0));
        if (!(tilt < best_tilt)) continue;
        if (scene->isStateColliding(candidate, group->getName())) continue;
        best_tilt = tilt;
        best.clear();
        for (const auto& name : names) best.push_back(candidate.getVariablePosition(name));
      }
    }

    if (best.empty())  // no collision-free candidate: fall back, never guess
      return fallback();

    last_box_tilt_rad_ = best_tilt;
    last_level_ = best_tilt <= max_box_tilt_rad;
    moveit_msgs::msg::Constraints goal_constraints;
    for (size_t i = 0; i < names.size(); ++i) {
      moveit_msgs::msg::JointConstraint joint;
      joint.joint_name = names[i];
      joint.position = best[i];
      joint.tolerance_above = joint_tolerance;
      joint.tolerance_below = joint_tolerance;
      joint.weight = 1.0;
      goal_constraints.joint_constraints.push_back(joint);
    }
    const double plan_timeout = std::max(0.5, timeout - elapsed());
    return PipelinePlanner::plan(scene, group, goal_constraints, plan_timeout, result, path_constraints);
  }

 private:
  double last_box_tilt_rad_ = std::numeric_limits<double>::quiet_NaN();
  bool last_level_ = false;
  int last_enumerated_ = 0;
  double last_min_position_error_m_ = std::numeric_limits<double>::infinity();
};
}
