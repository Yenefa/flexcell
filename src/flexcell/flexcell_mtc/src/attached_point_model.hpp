#pragma once
#include <moveit/robot_model_loader/robot_model_loader.hpp>
#include <rclcpp/rclcpp.hpp>
#include <tinyxml2.h>
#include <Eigen/Geometry>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace flexcell {
inline constexpr const char* pointLink = "flexcell_attached_point";
inline constexpr const char* pointJoint = "flexcell_attached_point_joint";
inline constexpr const char* pointGroup = "flexcell_attached_arm";

// A real fixed tip makes position-only KDL solve the attached point directly.
// This model belongs only to the planner. Original arm/EE, collision geometry,
// variable limits and controller descriptions remain unchanged.
inline robot_model_loader::RobotModelLoaderPtr attachedPointModel(
    const rclcpp::Node::SharedPtr& parent, const Eigen::Vector3d& offset) {
  if (!offset.allFinite()) throw std::runtime_error("nonfinite attached point offset");
  tinyxml2::XMLDocument urdf, srdf;
  if (urdf.Parse(parent->get_parameter("robot_description").as_string().c_str()) != tinyxml2::XML_SUCCESS ||
      srdf.Parse(parent->get_parameter("robot_description_semantic").as_string().c_str()) != tinyxml2::XML_SUCCESS)
    throw std::runtime_error("invalid model XML for attached point planning");
  auto* robot = urdf.FirstChildElement("robot");
  auto* semantic = srdf.FirstChildElement("robot");
  if (!robot || !semantic) throw std::runtime_error("missing robot model root");
  for (auto* element = robot->FirstChildElement(); element; element = element->NextSiblingElement()) {
    const std::string name = element->Attribute("name") ? element->Attribute("name") : "";
    if (name == pointLink || name == pointJoint)
      throw std::runtime_error("attached point model name already exists");
  }
  tinyxml2::XMLElement* arm = nullptr;
  for (auto* group = semantic->FirstChildElement("group"); group; group = group->NextSiblingElement("group")) {
    const std::string name = group->Attribute("name") ? group->Attribute("name") : "";
    if (name == pointGroup) throw std::runtime_error("attached point group already exists");
    if (name == "arm") arm = group;
  }
  if (!arm) throw std::runtime_error("arm group missing for attached point planning");
  auto* link = urdf.NewElement("link"); link->SetAttribute("name", pointLink); robot->InsertEndChild(link);
  auto* joint = urdf.NewElement("joint");
  joint->SetAttribute("name", pointJoint); joint->SetAttribute("type", "fixed");
  auto* origin = urdf.NewElement("origin");
  std::ostringstream xyz; xyz << std::setprecision(17) << offset.x() << ' ' << offset.y() << ' ' << offset.z();
  origin->SetAttribute("xyz", xyz.str().c_str()); joint->InsertEndChild(origin);
  auto* base = urdf.NewElement("parent"); base->SetAttribute("link", "end_effector_link"); joint->InsertEndChild(base);
  auto* tip = urdf.NewElement("child"); tip->SetAttribute("link", pointLink); joint->InsertEndChild(tip);
  robot->InsertEndChild(joint);
  // The locked arm is an explicit joint list, including end_effector_joint.
  // Append only the new fixed joint; never add an active degree of freedom.
  if (arm->FirstChildElement("chain") || arm->FirstChildElement("group"))
    throw std::runtime_error("attached point adapter requires the locked explicit arm joint group");
  auto* alias = arm->DeepClone(&srdf)->ToElement(); alias->SetAttribute("name", pointGroup);
  auto* member = srdf.NewElement("joint"); member->SetAttribute("name", pointJoint); alias->InsertEndChild(member);
  semantic->InsertEndChild(alias);
  tinyxml2::XMLPrinter robot_xml, semantic_xml;
  urdf.Print(&robot_xml); srdf.Print(&semantic_xml);
  std::vector<rclcpp::Parameter> overrides;
  const std::string arm_prefix = "robot_description_kinematics.arm.";
  for (const auto& name : parent->list_parameters({}, 0).names) {
    if (name != "robot_description" && name != "robot_description_semantic" &&
        name.rfind("robot_description_planning.", 0) != 0 &&
        name.rfind("robot_description_kinematics.", 0) != 0) continue;
    rclcpp::Parameter value;
    if (!parent->get_parameter(name, value) || value.get_type() == rclcpp::ParameterType::PARAMETER_NOT_SET) continue;
    if (name == "robot_description") overrides.emplace_back(name, std::string(robot_xml.CStr()));
    else if (name == "robot_description_semantic") overrides.emplace_back(name, std::string(semantic_xml.CStr()));
    else overrides.push_back(value);
    if (name.rfind(arm_prefix, 0) == 0)
      overrides.emplace_back("robot_description_kinematics." + std::string(pointGroup) + "." +
                             name.substr(arm_prefix.size()), value.get_parameter_value());
  }
  auto node = std::make_shared<rclcpp::Node>("attached_point_model", "/flexcell/private",
      rclcpp::NodeOptions().use_global_arguments(false).start_parameter_services(false)
          .start_parameter_event_publisher(false).automatically_declare_parameters_from_overrides(true)
          .parameter_overrides(overrides));
  auto loader = std::make_shared<robot_model_loader::RobotModelLoader>(node, "robot_description");
  const auto& model = loader->getModel();
  const auto* original = model ? model->getJointModelGroup("arm") : nullptr;
  const auto* point = model ? model->getJointModelGroup(pointGroup) : nullptr;
  if (!original || !point || original->getActiveJointModelNames() != point->getActiveJointModelNames() ||
      !point->getSolverInstance() || point->getSolverInstance()->getTipFrame() != pointLink)
    throw std::runtime_error("attached point model did not preserve the arm or load its true-tip solver");
  return loader;
}
}
