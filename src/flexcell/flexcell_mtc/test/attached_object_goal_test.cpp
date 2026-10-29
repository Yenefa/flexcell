#include <gtest/gtest.h>
#include "attached_object_goal.hpp"
#include "position_only_planner.hpp"

static geometry_msgs::msg::PoseStamped sample(const Eigen::Isometry3d& pose) {
  geometry_msgs::msg::PoseStamped value;
  value.header.frame_id = "world";
  value.pose.position.x = pose.translation().x();
  value.pose.position.y = pose.translation().y();
  value.pose.position.z = pose.translation().z();
  const Eigen::Quaterniond q(pose.linear());
  value.pose.orientation.x = q.x(); value.pose.orientation.y = q.y();
  value.pose.orientation.z = q.z(); value.pose.orientation.w = q.w();
  return value;
}

TEST(AttachedObjectGoal, RotatingWristPreservesLinkOffsetInsteadOfWorldVerticalOffset) {
  Eigen::Isometry3d link = Eigen::Isometry3d::Identity();
  link.translation() = Eigen::Vector3d(.12, -.15, .2275);
  link.linear() = Eigen::AngleAxisd(.8, Eigen::Vector3d::UnitY()).toRotationMatrix();
  Eigen::Isometry3d shape = Eigen::Isometry3d::Identity();
  shape.translation() = Eigen::Vector3d(.02, 0., -.159);
  const Eigen::Isometry3d world_shape = link * shape;
  EXPECT_NO_THROW(flexcell::checkAttachedObjectPose(link, shape, sample(world_shape)));
  const Eigen::Vector3d legacy = link.translation() + Eigen::Vector3d(0., 0., -.16);
  EXPECT_GT((world_shape.translation() - legacy).norm(), .1);
  const auto goal = flexcell::positionGoal("world", "end_effector_link", shape, world_shape, 1e-4);
  EXPECT_DOUBLE_EQ(goal.position_constraints.front().target_point_offset.x, .02);
  EXPECT_DOUBLE_EQ(goal.position_constraints.front().target_point_offset.z, -.159);
  EXPECT_TRUE(goal.orientation_constraints.empty());
}

TEST(AttachedObjectGoal, RejectsScenePhysicalMismatchBeforePlanning) {
  const Eigen::Isometry3d identity = Eigen::Isometry3d::Identity();
  auto value = sample(identity);
  value.pose.position.x = .0021;
  EXPECT_THROW(flexcell::checkAttachedObjectPose(identity, identity, value), std::runtime_error);
  value = sample(identity); value.header.frame_id = "camera";
  EXPECT_THROW(flexcell::checkAttachedObjectPose(identity, identity, value), std::runtime_error);
  value = sample(identity); value.pose.orientation.w = 0.;
  EXPECT_THROW(flexcell::checkAttachedObjectPose(identity, identity, value), std::runtime_error);
  Eigen::Isometry3d rotated = identity;
  rotated.linear() = Eigen::AngleAxisd(.02, Eigen::Vector3d::UnitX()).toRotationMatrix();
  EXPECT_THROW(flexcell::checkAttachedObjectPose(identity, identity, sample(rotated)), std::runtime_error);
}
