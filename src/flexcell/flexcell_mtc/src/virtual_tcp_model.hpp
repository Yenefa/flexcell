#pragma once
#include <rclcpp/rclcpp.hpp>
#include <moveit/robot_model_loader/robot_model_loader.hpp>
#include <moveit/kinematics_base/kinematics_base.hpp>
#include <tinyxml2.h>
#include <Eigen/Geometry>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace flexcell {
// Add a geometry-free, fixed tool frame to a planning-only copy of the model.
// KDL must solve the actual constrained point: subtracting a sampled rotation
// times an offset is incompatible with a solver that ignores that rotation.
// Keep the original arm group for EE retreat; no actuator or joint is added.
class VirtualTcpModel {
 public:
  static constexpr const char* link = "flexcell_object_tcp";
  static constexpr const char* joint = "flexcell_object_tcp_joint";
  static constexpr const char* group = "flexcell_object_arm";
  VirtualTcpModel(const rclcpp::Node::SharedPtr& source, const Eigen::Isometry3d& offset) {
    if (!offset.matrix().allFinite()) throw std::runtime_error("nonfinite TCP transform");
    tinyxml2::XMLDocument robot, semantic;
    auto parse = [](tinyxml2::XMLDocument& doc, const std::string& value) {
      if (doc.Parse(value.c_str()) != tinyxml2::XML_SUCCESS || !doc.FirstChildElement("robot"))
        throw std::runtime_error("invalid model XML for virtual TCP");
    };
    parse(robot, source->get_parameter("robot_description").as_string());
    parse(semantic, source->get_parameter("robot_description_semantic").as_string());
    auto* urdf = robot.FirstChildElement("robot");
    for (auto* child = urdf->FirstChildElement(); child; child = child->NextSiblingElement()) {
      const auto* name = child->Attribute("name");
      if (name && (std::string(name) == link || std::string(name) == joint))
        throw std::runtime_error("reserved virtual TCP name already exists");
    }
    auto* tcp = robot.NewElement("link"); tcp->SetAttribute("name", link); urdf->InsertEndChild(tcp);
    auto* fixed = robot.NewElement("joint"); fixed->SetAttribute("name", joint); fixed->SetAttribute("type", "fixed");
    auto* parent = robot.NewElement("parent"); parent->SetAttribute("link", "end_effector_link"); fixed->InsertEndChild(parent);
    auto* child = robot.NewElement("child"); child->SetAttribute("link", link); fixed->InsertEndChild(child);
    auto* origin = robot.NewElement("origin");
    std::ostringstream xyz, rpy; xyz << std::setprecision(17); rpy << std::setprecision(17);
    const Eigen::Vector3d angles = offset.linear().eulerAngles(2, 1, 0);
    xyz << offset.translation().x() << ' ' << offset.translation().y() << ' ' << offset.translation().z();
    rpy << angles.z() << ' ' << angles.y() << ' ' << angles.x();
    origin->SetAttribute("xyz", xyz.str().c_str()); origin->SetAttribute("rpy", rpy.str().c_str()); fixed->InsertEndChild(origin);
    urdf->InsertEndChild(fixed);
    auto* srdf = semantic.FirstChildElement("robot");
    for (auto* value = srdf->FirstChildElement("group"); value; value = value->NextSiblingElement("group"))
      if (value->Attribute("name") && std::string(value->Attribute("name")) == group)
        throw std::runtime_error("reserved virtual TCP group already exists");
    auto* arm = semantic.NewElement("group"); arm->SetAttribute("name", group);
    auto* original = semantic.NewElement("group"); original->SetAttribute("name", "arm"); arm->InsertEndChild(original);
    auto* tool = semantic.NewElement("joint"); tool->SetAttribute("name", joint); arm->InsertEndChild(tool); srdf->InsertEndChild(arm);
    tinyxml2::XMLPrinter robot_xml, semantic_xml; robot.Print(&robot_xml); semantic.Print(&semantic_xml);
    urdf_xml = robot_xml.CStr(); srdf_xml = semantic_xml.CStr();
    std::vector<rclcpp::Parameter> parameters;
    const std::string prefix = "robot_description_kinematics.arm.";
    for (const auto& name : source->list_parameters({}, 100).names) {
      if (name.rfind("robot_description", 0) != 0) continue;
      rclcpp::Parameter value;
      try { value = source->get_parameter(name); }
      catch (const rclcpp::exceptions::ParameterUninitializedException&) { continue; }
      if (value.get_type() == rclcpp::ParameterType::PARAMETER_NOT_SET) continue;
      if (name == "robot_description") parameters.emplace_back(name, urdf_xml);
      else if (name == "robot_description_semantic") parameters.emplace_back(name, srdf_xml);
      else parameters.push_back(value);
      if (name.rfind(prefix, 0) == 0)
        parameters.emplace_back("robot_description_kinematics." + std::string(group) + "." + name.substr(prefix.size()), value.get_parameter_value());
    }
    rclcpp::NodeOptions options;
    options.use_global_arguments(false).automatically_declare_parameters_from_overrides(true).parameter_overrides(parameters);
    node = std::make_shared<rclcpp::Node>("flexcell_tcp_model", options);
    loader = std::make_unique<robot_model_loader::RobotModelLoader>(node, "robot_description");
    const auto* extended = loader->getModel()->getJointModelGroup(group);
    const auto* legacy = loader->getModel()->getJointModelGroup("arm");
    if (!extended || !legacy || extended->getActiveJointModelNames() != legacy->getActiveJointModelNames() ||
        !extended->getSolverInstance() || extended->getSolverInstance()->getTipFrames() != std::vector<std::string>{link})
      throw std::runtime_error("virtual TCP solver did not retain arm joints and select the tool tip");
  }
  const moveit::core::RobotModelPtr& model() const { return loader->getModel(); }
  std::string urdf_xml, srdf_xml;
 private:
  rclcpp::Node::SharedPtr node;
  std::unique_ptr<robot_model_loader::RobotModelLoader> loader;
};
}
