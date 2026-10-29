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
  gz::math::Vector3d previous[3];
  double maxPoseJump{0.};
  std::ofstream stepLog;
  uint64_t stepRecords{0};
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
  void Configure(const gz::sim::Entity& entity, const std::shared_ptr<const sdf::Element>&,
                 gz::sim::EntityComponentManager&, gz::sim::EventManager&) override {
    world = entity;
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
    const auto a = Link(ecm, "target_box_a", "link"), b = Link(ecm, "target_box_b", "link");
    if (parent == kNullEntity || a == kNullEntity || b == kNullEntity) {
      ++missingPoseSteps; havePrevious = false; return;
    }
    const gz::math::Pose3d poses[3]{worldPose(parent, ecm), worldPose(a, ecm), worldPose(b, ecm)};
    if (!poses[0].IsFinite() || !poses[1].IsFinite() || !poses[2].IsFinite()) {
      nonfinitePose = true; havePrevious = false;
    } else {
      if (havePrevious)
        for (int i = 0; i < 3; ++i)
          maxPoseJump = std::max(maxPoseJump, (poses[i].Pos() - previous[i]).Length());
      for (int i = 0; i < 3; ++i) previous[i] = poses[i].Pos();
      havePrevious = true;
    }
    bool attached[2]{false, false};
    ecm.Each<components::DetachableJoint>([&](const Entity&, const components::DetachableJoint* j) {
      if (j->Data().parentLink == parent) {
        attached[0] |= j->Data().childLink == a; attached[1] |= j->Data().childLink == b;
      }
      return true;
    });
    const auto monotonicNs = std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch()).count();
    if (stepLog.is_open()) {
      stepLog << "{\"schema_version\":1,\"sim_ns\":" << ns
              << ",\"step_ns\":" << currentStep << ",\"monotonic_ns\":" << monotonicNs
              << ",\"parent_pose\":";
      Pose(stepLog, poses[0]);
      stepLog << ",\"objects\":{\"target_box_a\":{\"pose\":";
      Pose(stepLog, poses[1]);
      stepLog << ",\"joint_component\":" << (attached[0] ? "true" : "false")
              << "},\"target_box_b\":{\"pose\":";
      Pose(stepLog, poses[2]);
      stepLog << ",\"joint_component\":" << (attached[1] ? "true" : "false")
              << "}},\"contact_force_observed\":false}\n";
      ++stepRecords;
      if (stepRecords % 10 == 0) stepLog.flush();
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
    out << ",\"ee_source\":\"link5_plus_urdf_fixed_transform\",\"objects\":{\"target_box_a\":{\"pose\":";
    Pose(out, poses[1]);
    out << ",\"joint_component\":" << (attached[0] ? "true" : "false") << "},\"target_box_b\":{\"pose\":";
    Pose(out, poses[2]);
    out << ",\"joint_component\":" << (attached[1] ? "true" : "false") << "}}}";
    gz::msgs::StringMsg message; message.set_data(out.str()); publisher.Publish(message); last = ns;
    physicsSteps = missingPoseSteps = 0;
    minPhysicsStep = std::numeric_limits<int64_t>::max(); maxPhysicsStep = 0;
    badPhysicsTime = nonfinitePose = false; maxPoseJump = 0.;
  }
};
}
GZ_ADD_PLUGIN(flexcell::PhysicsTrace, gz::sim::System,
             flexcell::PhysicsTrace::ISystemConfigure, flexcell::PhysicsTrace::ISystemPostUpdate)
