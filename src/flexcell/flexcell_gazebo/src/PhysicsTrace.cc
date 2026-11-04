// Synchronous physics-step observations. Does not move, attach or control anything.
#include <gz/msgs/stringmsg.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/DetachableJoint.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/transport/Node.hh>
#include <chrono>
#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace flexcell {
class PhysicsTrace final : public gz::sim::System, public gz::sim::ISystemConfigure,
                           public gz::sim::ISystemPostUpdate {
  gz::transport::Node node;
  gz::transport::Node::Publisher publisher;
  gz::sim::Entity world{gz::sim::kNullEntity};
  int64_t last{-1};
  int64_t lastPhysics{-1}, minPhysicsStep{std::numeric_limits<int64_t>::max()}, maxPhysicsStep{0};
  uint64_t physicsSteps{0}, missingPoseSteps{0};
  bool badPhysicsTime{false}, nonfinitePose{false}, havePrevious{false};
  std::vector<std::string> names;
  std::vector<gz::math::Vector3d> previous;
  double maxPoseJump{0.};
  std::ofstream stepLog;
  uint64_t stepRecords{0};
  bool flushEachStep{false};
  static void Pose(std::ostream& out, const gz::math::Pose3d& p) {
    out << '[' << p.Pos().X() << ',' << p.Pos().Y() << ',' << p.Pos().Z() << ','
        << p.Rot().X() << ',' << p.Rot().Y() << ',' << p.Rot().Z() << ',' << p.Rot().W() << ']';
  }
  gz::sim::Entity Link(const gz::sim::EntityComponentManager& ecm,
                       const std::string& model, const std::string& link) const {
    using namespace gz::sim;
    const auto entity = ecm.EntityByComponents(components::Model(), components::Name(model),
                                             components::ParentEntity(world));
    if (entity == kNullEntity) return entity;
    return ecm.EntityByComponents(components::Link(), components::Name(link), components::ParentEntity(entity));
  }
 public:
  void Configure(const gz::sim::Entity& entity, const std::shared_ptr<const sdf::Element>& sdf,
                 gz::sim::EntityComponentManager&, gz::sim::EventManager&) override {
    world = entity;
    const auto config = sdf->Clone();
    for (auto item = config->FindElement("object"); item; item = item->GetNextElement("object")) {
      const auto name = item->Get<std::string>();
      if (!name.empty()) names.push_back(name);
    }
    if (names.empty()) names = {"target_box_a", "target_box_b"};
    previous.assign(names.size() + 1, gz::math::Vector3d(0, 0, 0));
    flushEachStep = config->HasElement("flush_each_step") && config->Get<bool>("flush_each_step");
    publisher = node.Advertise<gz::msgs::StringMsg>("/flexcell/physics_trace");
    const char *path = std::getenv("FLEXCELL_PHYSICS_STEP_LOG");
    if (path && *path) {
      if (std::filesystem::exists(path)) throw std::runtime_error("physics step log already exists");
      stepLog.open(path, std::ios::out);
      if (!stepLog) throw std::runtime_error("cannot open physics step log");
      stepLog << std::setprecision(15);
    }
  }
  void PostUpdate(const gz::sim::UpdateInfo& info, const gz::sim::EntityComponentManager& ecm) override {
    using namespace gz::sim;
    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(info.simTime).count();
    if (info.paused) return;
    const auto currentStep = lastPhysics >= 0 ? ns - lastPhysics : 0;
    if (lastPhysics >= 0) {
      const auto delta = currentStep;
      ++physicsSteps;
      minPhysicsStep = std::min(minPhysicsStep, delta);
      maxPhysicsStep = std::max(maxPhysicsStep, delta);
      if (delta <= 0) badPhysicsTime = true;
      if (delta < 0) { last = -1; havePrevious = false; }
    }
    lastPhysics = ns;
    const auto parent = Link(ecm, "open_manipulator_x", "link5");
    std::vector<gz::sim::Entity> objects;
    objects.reserve(names.size());
    bool missing = parent == kNullEntity;
    for (const auto& name : names) {
      const auto entity = Link(ecm, name, "link");
      objects.push_back(entity);
      missing = missing || entity == kNullEntity;
    }
    if (missing) {
      ++missingPoseSteps; havePrevious = false; return;
    }
    std::vector<gz::math::Pose3d> poses;
    poses.reserve(objects.size() + 1);
    poses.push_back(worldPose(parent, ecm));
    for (const auto entity : objects) poses.push_back(worldPose(entity, ecm));
    bool finite = true;
    for (const auto& pose : poses) finite = finite && pose.IsFinite();
    if (!finite) {
      nonfinitePose = true; havePrevious = false;
    } else {
      if (havePrevious)
        for (size_t i = 0; i < poses.size(); ++i)
          maxPoseJump = std::max(maxPoseJump, (poses[i].Pos() - previous[i]).Length());
      for (size_t i = 0; i < poses.size(); ++i) previous[i] = poses[i].Pos();
      havePrevious = true;
    }
    std::vector<bool> attached(names.size(), false);
    ecm.Each<components::DetachableJoint>([&](const Entity&, const components::DetachableJoint* j) {
      if (j->Data().parentLink == parent)
        for (size_t i = 0; i < objects.size(); ++i)
          attached[i] = attached[i] || j->Data().childLink == objects[i];
      return true;
    });
    const auto monotonicNs = std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch()).count();
    if (stepLog.is_open()) {
      stepLog << "{\"schema_version\":1,\"sim_ns\":" << ns
              << ",\"step_ns\":" << currentStep << ",\"monotonic_ns\":" << monotonicNs
              << ",\"parent_pose\":";
      Pose(stepLog, poses[0]);
      stepLog << ",\"objects\":{";
      for (size_t i = 0; i < names.size(); ++i) {
        stepLog << (i ? "," : "") << '"' << names[i] << "\":{\"pose\":";
        Pose(stepLog, poses[i + 1]);
        stepLog << ",\"joint_component\":" << (attached[i] ? "true" : "false") << '}';
      }
      stepLog << "},\"contact_force_observed\":false}\n";
      ++stepRecords;
      if (flushEachStep || stepRecords % 10 == 0) stepLog.flush();
    }
    if (last >= 0 && ns - last < 20000000) return;  // publish at 50 Hz; inspect every step
    std::ostringstream out;
    out << std::setprecision(15) << "{\"schema_version\":1,\"sim_ns\":" << ns
        << ",\"step_ns\":" << (last < 0 ? 0 : ns - last) << ",\"monotonic_ns\":" << monotonicNs
        << ",\"physics_steps\":" << physicsSteps
        << ",\"physics_min_step_ns\":" << (physicsSteps ? minPhysicsStep : 0)
        << ",\"physics_max_step_ns\":" << maxPhysicsStep
        << ",\"physics_bad_time\":" << (badPhysicsTime ? "true" : "false")
        << ",\"physics_missing_pose_steps\":" << missingPoseSteps
        << ",\"physics_nonfinite_pose\":" << (nonfinitePose ? "true" : "false")
        << ",\"physics_max_pose_jump_m\":" << maxPoseJump
        << ",\"contact_force_observed\":false"
        << ",\"parent_link\":\"link5\",\"parent_pose\":";
    const auto parentPose = poses[0];
    Pose(out, parentPose);
    out << ",\"ee_pose\":";
    Pose(out, parentPose * gz::math::Pose3d(.126, 0, 0, 0, 0, 0));
    out << ",\"ee_source\":\"link5_plus_urdf_fixed_transform\",\"objects\":{";
    for (size_t i = 0; i < names.size(); ++i) {
      out << (i ? "," : "") << '"' << names[i] << "\":{\"pose\":";
      Pose(out, poses[i + 1]);
      out << ",\"joint_component\":" << (attached[i] ? "true" : "false") << '}';
    }
    out << "}}";
    gz::msgs::StringMsg message; message.set_data(out.str()); publisher.Publish(message); last = ns;
    physicsSteps = missingPoseSteps = 0;
    minPhysicsStep = std::numeric_limits<int64_t>::max(); maxPhysicsStep = 0;
    badPhysicsTime = nonfinitePose = false; maxPoseJump = 0.;
  }
};
}
GZ_ADD_PLUGIN(flexcell::PhysicsTrace, gz::sim::System,
             flexcell::PhysicsTrace::ISystemConfigure, flexcell::PhysicsTrace::ISystemPostUpdate)
