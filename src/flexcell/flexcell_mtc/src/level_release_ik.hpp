#pragma once

// The closed-form geometry used by LevelPitchPlanner. Keep this independent of
// ROS so regressions exercise the production solver against independent FK.
#include <algorithm>
#include <array>
#include <cmath>
#include <vector>

namespace flexcell::level_release {
constexpr double kPi = 3.14159265358979323846;
using Point = std::array<double, 3>;
using Joints = std::array<double, 4>;

inline std::vector<Joints> attachedPointCandidates(const Point& goal,
    const Point& attachment, double phi) {
  const double psi = std::atan2(goal[1], goal[0] - 0.012);
  const double g = std::hypot(goal[0] - 0.012, goal[1]);
  if (!std::isfinite(g) || !std::isfinite(phi) || !std::isfinite(attachment[1]) ||
      std::abs(attachment[1]) > g) return {};
  const double lateral = g > 0.0 ? attachment[1] / g : 0.0;
  // Rz(-j1)*goal has y = -g*sin(j1-psi) = attachment.y.
  // Retain both yaw branches: a reachable box can lie behind the arm plane.
  const double correction = std::asin(std::clamp(lateral, -1.0, 1.0));
  std::vector<Joints> result;
  for (double j1 : {psi - correction, psi + correction - kPi}) {
    j1 = std::remainder(j1, 2.0 * kPi);
    const double r = g * std::cos(j1 - psi);
    const double cp = std::cos(phi), sp = std::sin(phi);
    const double wx = r - (attachment[0] + 0.126) * cp - attachment[2] * sp;
    const double wz = goal[2] + (attachment[0] + 0.126) * sp - attachment[2] * cp - 0.0595;
    const double l1 = std::hypot(0.024, 0.128), l2 = 0.124;
    const double cosk = (wx * wx + wz * wz - l1 * l1 - l2 * l2) / (2.0 * l1 * l2);
    if (!std::isfinite(cosk) || std::abs(cosk) > 1.0 + 1e-12) continue;
    for (const double sign : {1.0, -1.0}) {
      const double j3 = sign * std::acos(std::clamp(cosk, -1.0, 1.0)) - std::atan2(0.128, 0.024);
      const double j2 = std::remainder(
          std::atan2(0.128 - l2 * std::sin(j3), 0.024 + l2 * std::cos(j3)) -
          std::atan2(wz, wx), 2.0 * kPi);
      result.push_back({j1, j2, j3, phi - j2 - j3});
    }
  }
  return result;
}

inline std::vector<double> pitchCandidates(double lower, double upper, int step_deg,
    double up_x, double up_z) {
  if (!std::isfinite(lower) || !std::isfinite(upper) || lower > upper ||
      !std::isfinite(up_x) || !std::isfinite(up_z)) return {};
  const double step = std::max(1, step_deg) * kPi / 180.0;
  std::vector<double> result{lower, upper};
  for (double phi = std::ceil(lower / step) * step; phi <= upper; phi += step)
    result.push_back(phi);
  // Maximise (Ry(phi)*R_attach*z).z. Sampling only +/-30 degrees about
  // zero excludes level releases for large measured attachment rotations.
  const double ideal = std::atan2(-up_x, up_z);
  for (double phi = ideal + std::ceil((lower - ideal) / (2.0 * kPi)) * 2.0 * kPi;
       phi <= upper; phi += 2.0 * kPi)
    result.push_back(phi);
  // Try the best box attitudes first within the stage's bounded time budget.
  std::sort(result.begin(), result.end(), [=](double a, double b) {
    const double za = up_z * std::cos(a) - up_x * std::sin(a);
    const double zb = up_z * std::cos(b) - up_x * std::sin(b);
    return za == zb ? a < b : za > zb;
  });
  result.erase(std::unique(result.begin(), result.end()), result.end());
  return result;
}
}  // namespace flexcell::level_release
