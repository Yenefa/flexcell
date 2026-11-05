#include <gtest/gtest.h>
#include "level_release_ik.hpp"
#include <limits>
#include <random>

namespace {
using flexcell::level_release::Point;
using flexcell::level_release::Joints;
using flexcell::level_release::kPi;
using flexcell::level_release::attachedPointCandidates;
using flexcell::level_release::pitchCandidates;
constexpr Joints lower{-kPi, -1.5, -1.5, -1.7};
constexpr Joints upper{kPi, 1.5, 1.4, 1.97};

Point ry(Point p, double angle) {
  return {std::cos(angle) * p[0] + std::sin(angle) * p[2], p[1],
          -std::sin(angle) * p[0] + std::cos(angle) * p[2]};
}

// Independent serial-chain FK, applying the upstream URDF link origins and
// axes one joint at a time; no inverse-kinematics equations are reused here.
Point fk(const Joints& q, Point attachment) {
  attachment[0] += 0.126;
  auto p = ry(attachment, q[3]);
  p[0] += 0.124;
  p = ry(p, q[2]);
  p[0] += 0.024;
  p[2] += 0.128;
  p = ry(p, q[1]);
  p[2] += 0.0595;
  return {0.012 + std::cos(q[0]) * p[0] - std::sin(q[0]) * p[1],
          std::sin(q[0]) * p[0] + std::cos(q[0]) * p[1], p[2]};
}

bool inLimits(const Joints& q) {
  for (int i = 0; i < 4; ++i)
    if (q[i] < lower[i] - 1e-10 || q[i] > upper[i] + 1e-10) return false;
  return true;
}

double error(const Point& a, const Point& b) {
  return std::hypot(a[0] - b[0], std::hypot(a[1] - b[1], a[2] - b[2]));
}

TEST(LevelReleaseIK, LateralOffsetRoundTripsInBothDirections) {
  const Joints original{-0.8, -0.5, 0.4, 0.1};
  for (double y : {-0.01, 0.0, 0.01}) {
    const Point attachment{0.008, y, -0.06};
    const Point goal = fk(original, attachment);
    bool found = false;
    for (const auto& q : attachedPointCandidates(goal, attachment, 0.0)) {
      EXPECT_LT(error(fk(q, attachment), goal), 1e-10);
      found = found || inLimits(q);
    }
    EXPECT_TRUE(found) << "lateral offset " << y;
  }
}

TEST(LevelReleaseIK, LargeAttachmentRotationsCanBeLevelled) {
  for (double offset : {-60.0, 60.0, 170.0}) {
    const double ideal = -offset * kPi / 180.0;
    const Joints original{-0.8, ideal / 3.0, ideal / 3.0, ideal / 3.0};
    ASSERT_TRUE(inLimits(original));
    const Point attachment{0.0, 0.0, -0.06};
    const Point goal = fk(original, attachment);
    const Point up = ry({0.0, 0.0, 1.0}, offset * kPi / 180.0);
    const auto pitches = pitchCandidates(lower[1] + lower[2] + lower[3],
        upper[1] + upper[2] + upper[3], 1, up[0], up[2]);
    ASSERT_FALSE(pitches.empty());
    EXPECT_NEAR(ry(up, pitches.front())[2], 1.0, 1e-12);
    bool found = false;
    for (const double phi : pitches) {
      for (const auto& q : attachedPointCandidates(goal, attachment, phi)) {
        if (inLimits(q) && ry(up, phi)[2] > 1.0 - 1e-12 &&
            error(fk(q, attachment), goal) < 1e-10) found = true;
      }
    }
    EXPECT_TRUE(found) << "attachment pitch " << offset;
  }
}

TEST(LevelReleaseIK, ReviewSixtyDegreeCounterexampleIsReachable) {
  const Point attachment{0.0, 0.0, -0.06};
  const Joints original{-0.8, 0.3, -0.3, kPi / 3.0};
  const auto goal = fk(original, attachment);
  bool found = false;
  for (const auto& q : attachedPointCandidates(goal, attachment, kPi / 3.0))
    found = found || (inLimits(q) && error(fk(q, attachment), goal) < 1e-10);
  EXPECT_TRUE(found);
}

TEST(LevelReleaseIK, FeasibleJointVectorsRoundTripAtTheirActualPitch) {
  std::mt19937 rng(121);
  for (int sample = 0; sample < 2000; ++sample) {
    Joints original;
    for (int i = 0; i < 4; ++i)
      original[i] = std::uniform_real_distribution<double>(lower[i], upper[i])(rng);
    const Point attachment{std::uniform_real_distribution<double>(-0.03, 0.03)(rng),
                           std::uniform_real_distribution<double>(-0.03, 0.03)(rng),
                           std::uniform_real_distribution<double>(-0.16, -0.02)(rng)};
    const auto goal = fk(original, attachment);
    bool found = false;
    for (const auto& q : attachedPointCandidates(goal, attachment,
             original[1] + original[2] + original[3])) {
      EXPECT_LT(error(fk(q, attachment), goal), 1e-9) << "sample " << sample;
      found = found || inLimits(q);
    }
    ASSERT_TRUE(found) << "sample " << sample;
  }
}

TEST(LevelReleaseIK, PitchSearchIncludesLimitsAndRanksActualBoxAttitude) {
  const double lo = -4.7, hi = 4.87;
  const auto pitches = pitchCandidates(lo, hi, 1, 0.6, 0.7);
  EXPECT_NE(std::find(pitches.begin(), pitches.end(), lo), pitches.end());
  EXPECT_NE(std::find(pitches.begin(), pitches.end(), hi), pitches.end());
  EXPECT_EQ(pitches, pitchCandidates(lo, hi, 1, 0.6, 0.7));
  double last = std::numeric_limits<double>::infinity();
  for (double phi : pitches) {
    EXPECT_GE(phi, lo);
    EXPECT_LE(phi, hi);
    const double z = 0.7 * std::cos(phi) - 0.6 * std::sin(phi);
    EXPECT_LE(z, last);
    last = z;
  }
}

TEST(LevelReleaseIK, ImpossibleLateralDisplacementReturnsNoCandidates) {
  EXPECT_TRUE(attachedPointCandidates({0.022, 0.0, 0.1}, {0.0, 0.02, -0.06}, 0.0).empty());
}
}  // namespace
