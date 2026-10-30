#pragma once
#include <rclcpp/rclcpp.hpp>
#include <rclcpp/serialization.hpp>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace flexcell {
// Opt-in, exact service inputs/outputs for replay. Never alter a measured scene.
class PlanningSnapshot {
 public:
  template <typename Request>
  PlanningSnapshot(const rclcpp::Node& node, const Request& request, uint64_t& sequence) {
    const char* root = std::getenv("FLEXCELL_MTC_DIAGNOSTIC_DIR");
    if (!root || !*root) return;
    std::filesystem::create_directories(root);
    do {
      std::ostringstream name;
      name << "request-" << std::setw(8) << std::setfill('0') << ++sequence;
      directory_ = std::filesystem::path(root) / name.str();
    } while (!std::filesystem::create_directory(directory_));
    write("request", request);
    for (const auto* parameter : {"robot_description", "robot_description_semantic"})
      file(std::string(parameter) + ".xml", node.get_parameter(parameter).as_string());
    if (const char* revision = std::getenv("FLEXCELL_SOURCE_REV")) file("source_revision.txt", revision);
  }

  template <typename Message>
  void write(const std::string& name, const Message& message) const {
    if (directory_.empty()) return;
    rclcpp::SerializedMessage serialized;
    rclcpp::Serialization<Message> serializer;
    serializer.serialize_message(&message, &serialized);
    const auto& buffer = serialized.get_rcl_serialized_message();
    std::ofstream output;
    output.exceptions(std::ios::failbit | std::ios::badbit);
    output.open(directory_ / (name + ".cdr"), std::ios::binary);
    output.write(reinterpret_cast<const char*>(buffer.buffer), buffer.buffer_length);
    output.close();
  }
 private:
  void file(const std::string& name, const std::string& value) const {
    std::ofstream output;
    output.exceptions(std::ios::failbit | std::ios::badbit);
    output.open(directory_ / name, std::ios::binary);
    output << value;
    output.close();
  }
  std::filesystem::path directory_;
};
}  // namespace flexcell
