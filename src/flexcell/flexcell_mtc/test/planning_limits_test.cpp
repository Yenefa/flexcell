#include <gtest/gtest.h>
#include <limits>
#include "planning_limits.hpp"

namespace {
std::string physical() {
  std::string value = "<robot name='test'><link name='base'/>";
  for (int i = 1; i <= 4; ++i)
    value += "<joint name='joint" + std::to_string(i) +
      "' type='revolute'><origin xyz='.1 0 .2'/><limit lower='-1.5' upper='1.4' velocity='4.8' effort='1000'/></joint>";
  return value + "<joint name='gripper' type='prismatic'><limit lower='-.011' upper='.02'/></joint></robot>";
}
}

TEST(PlanningLimits, PrivateArmBoundsStayInsideMechanicalStops) {
  const auto original = physical();
  tinyxml2::XMLDocument guarded;
  ASSERT_EQ(guarded.Parse(flexcell::planningDescription(original).c_str()), tinyxml2::XML_SUCCESS);
  auto* joint = guarded.FirstChildElement("robot")->FirstChildElement("joint");
  for (int i = 0; i < 4; ++i, joint = joint->NextSiblingElement("joint")) {
    auto* limit = joint->FirstChildElement("limit");
    EXPECT_DOUBLE_EQ(limit->DoubleAttribute("lower"), -1.48);
    EXPECT_DOUBLE_EQ(limit->DoubleAttribute("upper"), 1.38);
    EXPECT_DOUBLE_EQ(limit->DoubleAttribute("velocity"), 4.8);
    EXPECT_DOUBLE_EQ(limit->DoubleAttribute("effort"), 1000.);
    EXPECT_STREQ(joint->FirstChildElement("origin")->Attribute("xyz"), ".1 0 .2");
  }
  EXPECT_DOUBLE_EQ(joint->FirstChildElement("limit")->DoubleAttribute("lower"), -.011);
  EXPECT_DOUBLE_EQ(joint->FirstChildElement("limit")->DoubleAttribute("upper"), .02);
  EXPECT_EQ(original, physical());
}

TEST(PlanningLimits, UnusableOrAmbiguousModelsAreRejected) {
  EXPECT_THROW(flexcell::planningDescription("not xml"), std::runtime_error);
  EXPECT_THROW(flexcell::planningDescription("<robot/>"), std::runtime_error);
  auto duplicate = physical();
  duplicate.insert(duplicate.find("</robot>"), "<joint name='joint3' type='revolute'/>");
  EXPECT_THROW(flexcell::planningDescription(duplicate), std::runtime_error);
  auto missing = physical();
  missing.replace(missing.find("name='joint3'"), 13, "name='other3'");
  EXPECT_THROW(flexcell::planningDescription(missing), std::runtime_error);
}

TEST(PlanningLimits, ClearanceCannotExpandLimitsOrEraseTheUsableRange) {
  for (double margin : {0., -.01, 1.5, std::numeric_limits<double>::infinity(),
                        std::numeric_limits<double>::quiet_NaN()})
    EXPECT_THROW(flexcell::planningDescription(physical(), margin), std::runtime_error);
}
