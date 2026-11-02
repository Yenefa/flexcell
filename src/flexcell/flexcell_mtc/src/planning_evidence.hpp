#pragma once
#include <rclcpp/rclcpp.hpp>
#include <rcl_interfaces/msg/parameter_event.hpp>
#include <flexcell_interfaces/srv/plan_manipulation.hpp>
#include <moveit_msgs/msg/planning_scene.hpp>
#include <filesystem>
#include <fstream>
#include <chrono>

namespace flexcell {
class PlanningEvidence {
 public:
  PlanningEvidence(const rclcpp::Node::SharedPtr& node,
      const flexcell_interfaces::srv::PlanManipulation::Request& request,
      const moveit_msgs::msg::PlanningScene& scene) {
    const auto* base=std::getenv("FLEXCELL_MTC_PLAN_EVIDENCE_DIR");
    if (!base || !*base) return;
    static unsigned sequence=0;
    const auto time=std::chrono::system_clock::now().time_since_epoch().count();
    directory=std::filesystem::path(base)/(std::to_string(time)+"-"+std::to_string(++sequence));
    std::filesystem::create_directories(directory.parent_path());
    if (!std::filesystem::create_directory(directory)) throw std::runtime_error("planning evidence path already exists");
    message("request.cdr",request); message("scene.cdr",scene);
    rcl_interfaces::msg::ParameterEvent parameters;
    for (const auto& name:node->list_parameters({},100).names) {
      try {
        const auto value=node->get_parameter(name);
        if(value.get_type()!=rclcpp::ParameterType::PARAMETER_NOT_SET)
          parameters.changed_parameters.push_back(value.to_parameter_msg());
      } catch (const rclcpp::exceptions::ParameterUninitializedException&) {}
    }
    message("parameters.cdr",parameters);
  }
  void model(const std::string& urdf,const std::string& srdf) {
    if(directory.empty()) return;
    text("planning_model.urdf",urdf); text("planning_model.srdf",srdf);
  }
  void response(const flexcell_interfaces::srv::PlanManipulation::Response& value) {
    if(!directory.empty()) message("response.cdr",value);
  }
 private:
  template<typename T> void message(const char* name,const T& value) {
    rclcpp::Serialization<T> serializer;
    rclcpp::SerializedMessage serialized; serializer.serialize_message(&value,&serialized);
    const auto& buffer=serialized.get_rcl_serialized_message();
    write(name,reinterpret_cast<const char*>(buffer.buffer),buffer.buffer_length);
  }
  void text(const char* name,const std::string& value) {write(name,value.data(),value.size());}
  void write(const char* name,const char* data,std::size_t count) {
    std::ofstream file(directory/name,std::ios::binary);file.write(data,count);file.close();
    if(!file) throw std::runtime_error("planning evidence write failed before execution");
  }
  std::filesystem::path directory;
};
}
