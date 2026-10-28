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
#include <iomanip>
#include <sstream>

namespace flexcell {
class PhysicsTrace final : public gz::sim::System, public gz::sim::ISystemConfigure,
                           public gz::sim::ISystemPostUpdate {
  gz::transport::Node node;
  gz::transport::Node::Publisher publisher;
  gz::sim::Entity world{gz::sim::kNullEntity};
  int64_t last{-1};
  static void Pose(std::ostringstream& out, const gz::math::Pose3d& p) {
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
  }
  void PostUpdate(const gz::sim::UpdateInfo& info, const gz::sim::EntityComponentManager& ecm) override {
    using namespace gz::sim;
    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(info.simTime).count();
    if (info.paused || (last >= 0 && ns - last < 20000000)) return;  // 50 Hz simulation clock
    const auto parent = Link(ecm, "open_manipulator_x", "link5");
    const auto a = Link(ecm, "target_box_a", "link"), b = Link(ecm, "target_box_b", "link");
    if (parent == kNullEntity || a == kNullEntity || b == kNullEntity) return;
    bool attached[2]{false, false};
    ecm.Each<components::DetachableJoint>([&](const Entity&, const components::DetachableJoint* j) {
      if (j->Data().parentLink == parent) {
        attached[0] |= j->Data().childLink == a; attached[1] |= j->Data().childLink == b;
      }
      return true;
    });
    std::ostringstream out;
    out << std::setprecision(15) << "{\"schema_version\":1,\"sim_ns\":" << ns
        << ",\"step_ns\":" << (last < 0 ? 0 : ns - last) << ",\"monotonic_ns\":"
        << std::chrono::duration_cast<std::chrono::nanoseconds>(
             std::chrono::steady_clock::now().time_since_epoch()).count()
        << ",\"parent_link\":\"link5\",\"parent_pose\":";
    const auto parentPose = worldPose(parent, ecm);
    Pose(out, parentPose);
    out << ",\"ee_pose\":";
    Pose(out, parentPose * gz::math::Pose3d(.126, 0, 0, 0, 0, 0));
    out << ",\"ee_source\":\"link5_plus_urdf_fixed_transform\",\"objects\":{\"target_box_a\":{\"pose\":";
    Pose(out, worldPose(a, ecm));
    out << ",\"joint_component\":" << (attached[0] ? "true" : "false") << "},\"target_box_b\":{\"pose\":";
    Pose(out, worldPose(b, ecm));
    out << ",\"joint_component\":" << (attached[1] ? "true" : "false") << "}}}";
    gz::msgs::StringMsg message; message.set_data(out.str()); publisher.Publish(message); last = ns;
  }
};
}
GZ_ADD_PLUGIN(flexcell::PhysicsTrace, gz::sim::System,
             flexcell::PhysicsTrace::ISystemConfigure, flexcell::PhysicsTrace::ISystemPostUpdate)
