#pragma once
#include <tinyxml2.h>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>

namespace flexcell {
inline constexpr double jointStopClearance = .02;  // radians, planning only

// Gazebo's mechanical stops remain unchanged. A position-only IK solution may
// otherwise end exactly on a stop: main CI 41435906803 reached joint3=-1.5,
// then the joint stayed there despite a subsequent -0.416 rad command.
// Narrow the private planner model so its IK sampler and path planner agree
// on the usable range. Geometry, dynamics and the controller model stay intact.
inline std::string planningDescription(const std::string& physical,
                                       double clearance = jointStopClearance) {
  if (!std::isfinite(clearance) || clearance <= 0.)
    throw std::runtime_error("invalid planning joint-stop clearance");
  tinyxml2::XMLDocument document;
  if (document.Parse(physical.c_str()) != tinyxml2::XML_SUCCESS)
    throw std::runtime_error("invalid physical robot description");
  auto* robot = document.FirstChildElement("robot");
  if (!robot) throw std::runtime_error("missing physical robot model");
  std::array<bool, 4> found{};
  for (auto* joint = robot->FirstChildElement("joint"); joint;
       joint = joint->NextSiblingElement("joint")) {
    const std::string name = joint->Attribute("name") ? joint->Attribute("name") : "";
    for (size_t i = 0; i < found.size(); ++i) {
      if (name != "joint" + std::to_string(i + 1)) continue;
      auto* limit = joint->FirstChildElement("limit");
      double lower = 0., upper = 0.;
      if (found[i] || !joint->Attribute("type") ||
          std::string(joint->Attribute("type")) != "revolute" || !limit ||
          limit->QueryDoubleAttribute("lower", &lower) != tinyxml2::XML_SUCCESS ||
          limit->QueryDoubleAttribute("upper", &upper) != tinyxml2::XML_SUCCESS ||
          !std::isfinite(lower) || !std::isfinite(upper) || upper - lower <= 2 * clearance)
        throw std::runtime_error("invalid bounded arm joint: " + name);
      limit->SetAttribute("lower", lower + clearance);
      limit->SetAttribute("upper", upper - clearance);
      found[i] = true;
    }
  }
  for (bool joint : found)
    if (!joint) throw std::runtime_error("four bounded arm joints required");
  tinyxml2::XMLPrinter output;
  document.Print(&output);
  return output.CStr();
}
}  // namespace flexcell
