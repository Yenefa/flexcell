#include <gtest/gtest.h>
#include "position_only_planner.hpp"

TEST(PositionGoal, FourDofTargetHasNoOrientationOrFixedJointConstraint) {
  auto target = Eigen::Isometry3d::Identity();
  target.translation() = Eigen::Vector3d(.22, .03, .27);
  const auto goal = flexcell::positionGoal("world", "end_effector_link", Eigen::Isometry3d::Identity(), target, 1e-4);
  ASSERT_EQ(goal.position_constraints.size(), 1u);
  EXPECT_TRUE(goal.orientation_constraints.empty());
  EXPECT_TRUE(goal.joint_constraints.empty());
  const auto& point = goal.position_constraints.front();
  EXPECT_EQ(point.header.frame_id, "world");
  EXPECT_EQ(point.link_name, "end_effector_link");
  EXPECT_DOUBLE_EQ(point.constraint_region.primitive_poses.front().position.z, .27);
  EXPECT_DOUBLE_EQ(point.constraint_region.primitives.front().dimensions.front(), 1e-4);
}

TEST(PositionGoal, RotatingTargetDoesNotSilentlyConstrainFourDofOrientation) {
  auto target = Eigen::Isometry3d::Identity();
  target.translation() = Eigen::Vector3d(.22, 0., .18);
  auto offset = Eigen::Isometry3d::Identity(); offset.translation().x() = .126;
  const auto first = flexcell::positionGoal("world", "link5", offset, target, 1e-4);
  target.linear() = Eigen::AngleAxisd(2., Eigen::Vector3d::UnitY()).toRotationMatrix();
  const auto rotated = flexcell::positionGoal("world", "link5", offset, target, 1e-4);
  EXPECT_EQ(first, rotated);
  EXPECT_DOUBLE_EQ(first.position_constraints.front().target_point_offset.x, .126);
}
