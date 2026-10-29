#pragma once
#include <Eigen/Geometry>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <cmath>
#include <stdexcept>

namespace flexcell {
// The shape center can differ from the CollisionObject origin: existing
// scenes store box translation in primitive_poses. Use the actual shape frame.
inline void checkAttachedObjectPose(const Eigen::Isometry3d& world_to_link,
    const Eigen::Isometry3d& link_to_shape, const geometry_msgs::msg::PoseStamped& sample) {
  const auto& p = sample.pose.position;
  const auto& q = sample.pose.orientation;
  Eigen::Vector3d position(p.x, p.y, p.z);
  Eigen::Quaterniond rotation(q.w, q.x, q.y, q.z);
  if (sample.header.frame_id != "world" || !position.allFinite() || !rotation.coeffs().allFinite() ||
      std::abs(rotation.norm() - 1.) > .001)
    throw std::runtime_error("invalid attached object physical sample");
  const Eigen::Isometry3d expected = world_to_link * link_to_shape;
  if ((expected.translation() - position).norm() >= .002 ||
      Eigen::AngleAxisd(expected.linear().transpose() * rotation.normalized().toRotationMatrix()).angle() >=
          std::acos(-1.) / 180.)
    throw std::runtime_error("attached planning shape disagrees with physical sample; carry held for reconciliation");
}
}
