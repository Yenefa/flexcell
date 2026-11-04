// Ownership/lease adapter for Gazebo's official DetachableJoint systems.
// This system NEVER creates joints, sets poses or changes object velocities.
#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/empty.pb.h>
#include <gz/msgs/pose.pb.h>
#include <gz/msgs/stringmsg.pb.h>
#include <gz/msgs/Utility.hh>
#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/DetachableJoint.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/transport/Node.hh>
#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <unordered_set>
#include <vector>

namespace flexcell {
using namespace gz::sim;
class DetachableCarryGuard final : public System, public ISystemConfigure,
    public ISystemPreUpdate, public ISystemPostUpdate {
  using Clock = std::chrono::steady_clock;
  enum class Kind { Engage, Pin, Release };
  struct Command {
    Kind kind;
    std::string object, token;
    gz::math::Pose3d target;
    bool done{false}, success{false}, cancelled{false};
    std::condition_variable ready;
  };
  gz::transport::Node node;
  std::mutex mutex;
  Entity world{kNullEntity}, parent{kNullEntity};
  std::vector<std::string> names;
  std::vector<Entity> children;
  std::vector<gz::transport::Node::Publisher> attach, detach;
  std::vector<bool> present, seenInitial;
  bool ready{false}, releasing{false};
  bool channelsConnected{false};
  unsigned detachedFrames{0};
  unsigned attachedFrames{0};
  int active{-1};
  int64_t simNs{0};
  std::string session;
  gz::math::Pose3d relative;
  Clock::time_point renewed;
  const std::chrono::milliseconds lease{500};
  std::unordered_set<std::string> retired;
  std::deque<std::shared_ptr<Command>> queue, pending;

  static std::string Token(const gz::msgs::Pose &pose) {
    for (const auto &item : pose.header().data())
      if (item.key() == "carry_session" && item.value_size() == 1) return item.value(0);
    return {};
  }
  static bool Valid(const std::string &token) {
    return token.size() == 32 && std::all_of(token.begin(), token.end(),
        [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); });
  }
  int Index(const std::string &name) const {
    for (size_t i = 0; i < names.size(); ++i) if (name == names[i]) return static_cast<int>(i);
    return -1;
  }
  bool AnyPresent() const {
    for (bool value : present) if (value) return true;
    return false;
  }
  bool OtherPresent(int index) const {
    for (size_t i = 0; i < present.size(); ++i)
      if (static_cast<int>(i) != index && present[i]) return true;
    return false;
  }
  Entity Link(const EntityComponentManager &ecm, const std::string &modelName,
              const std::string &linkName) const {
    Entity model = ecm.EntityByComponents(components::Model(), components::Name(modelName),
                                         components::ParentEntity(world));
    return model == kNullEntity ? kNullEntity : ecm.EntityByComponents(
        components::Link(), components::Name(linkName), components::ParentEntity(model));
  }
  void Inspect(const EntityComponentManager &ecm) {
    parent = Link(ecm, "open_manipulator_x", "link5");
    for (size_t i = 0; i < names.size(); ++i) {
      children[i] = Link(ecm, names[i], "link");
      present[i] = false;
    }
    ecm.Each<components::DetachableJoint>([&](const Entity &, const components::DetachableJoint *j) {
      for (size_t i = 0; i < names.size(); ++i)
        if (parent != kNullEntity && children[i] != kNullEntity &&
            j->Data().parentLink == parent && j->Data().childLink == children[i]) present[i] = true;
      return true;
    });
  }
  void DetachAll() {
    for (auto &publisher : detach) publisher.Publish(gz::msgs::Empty());
  }
  void ReadObjects(const std::shared_ptr<const sdf::Element> &sdf) {
    const auto config = sdf->Clone();
    for (auto item = config->FindElement("allowed_model"); item;
         item = item->GetNextElement("allowed_model")) {
      const auto name = item->Get<std::string>();
      if (!name.empty()) names.push_back(name);
    }
    if (names.empty()) names = {"target_box_a", "target_box_b"};
    children.assign(names.size(), kNullEntity);
    present.assign(names.size(), false);
    seenInitial.assign(names.size(), false);
  }
  bool Submit(Kind kind, const gz::msgs::Pose &pose, const std::string &token,
              gz::msgs::Boolean &reply) {
    auto command = std::make_shared<Command>();
    command->kind = kind; command->object = pose.name(); command->token = token;
    command->target = gz::msgs::Convert(pose);
    std::unique_lock<std::mutex> lock(mutex);
    queue.push_back(command);
    if (!command->ready.wait_for(lock, std::chrono::milliseconds(500), [&] { return command->done; })) {
      command->cancelled = true;
      reply.set_data(false);
    } else reply.set_data(command->success);
    return true;
  }
  bool Engage(const gz::msgs::Pose &p, gz::msgs::Boolean &r) { return Submit(Kind::Engage, p, Token(p), r); }
  bool Pin(const gz::msgs::Pose &p, gz::msgs::Boolean &r) { return Submit(Kind::Pin, p, Token(p), r); }
  bool Release(const gz::msgs::StringMsg &p, gz::msgs::Boolean &r) { return Submit(Kind::Release, {}, p.data(), r); }
  bool Status(const gz::msgs::Empty &, gz::msgs::StringMsg &reply) {
    std::lock_guard<std::mutex> lock(mutex);
    std::ostringstream text;
    text << "{\"backend\":\"detachable_joint_v1\",\"ready\":" << (ready ? "true" : "false")
         << ",\"engaged\":" << (active >= 0 && present[active] ? "true" : "false")
         << ",\"object\":\"" << (active >= 0 ? names[active] : "")
         << "\",\"session\":\"" << session << "\",\"lease_ms\":500,\"sim_ns\":" << simNs
         << ",\"parent_link\":\"link5\",\"relative_pose\":["
         << relative.Pos().X() << ',' << relative.Pos().Y() << ',' << relative.Pos().Z() << ','
         << relative.Rot().X() << ',' << relative.Rot().Y() << ',' << relative.Rot().Z() << ','
         << relative.Rot().W() << "],\"channels_connected\":" << (channelsConnected ? "true" : "false")
         << ",\"initial_joint_observed\":[";
    for (size_t i = 0; i < names.size(); ++i) text << (i ? "," : "") << (seenInitial[i] ? "true" : "false");
    text << "],\"component_present\":[";
    for (size_t i = 0; i < names.size(); ++i) text << (i ? "," : "") << (present[i] ? "true" : "false");
    text << "],\"detached_frames\":" << detachedFrames << '}';
    reply.set_data(text.str());
    return true;
  }
  void Complete(const std::shared_ptr<Command> &command, bool success) {
    command->success = success; command->done = true; command->ready.notify_all();
  }
 public:
  void Configure(const Entity &entity, const std::shared_ptr<const sdf::Element> &sdf,
                 EntityComponentManager &ecm, EventManager &) override {
    world = entity;
    ReadObjects(sdf);
    const auto name = ecm.Component<components::Name>(world)->Data();
    for (size_t i = 0; i < names.size(); ++i) {
      const auto topic = "/flexcell/detachable/" + names[i];
      attach.push_back(node.Advertise<gz::msgs::Empty>(topic + "/attach"));
      detach.push_back(node.Advertise<gz::msgs::Empty>(topic + "/detach"));
    }
    const auto prefix = "/world/" + name + "/flexcell/carry/";
    if (!node.Advertise(prefix + "engage", &DetachableCarryGuard::Engage, this) ||
        !node.Advertise(prefix + "pin", &DetachableCarryGuard::Pin, this) ||
        !node.Advertise(prefix + "release", &DetachableCarryGuard::Release, this) ||
        !node.Advertise(prefix + "status", &DetachableCarryGuard::Status, this))
      throw std::runtime_error("detachable guard services unavailable");
  }
  void PreUpdate(const UpdateInfo &info, EntityComponentManager &ecm) override {
    std::lock_guard<std::mutex> lock(mutex);
    Inspect(ecm);
    channelsConnected = !names.empty();
    for (size_t i = 0; i < names.size(); ++i)
      channelsConnected = channelsConnected && attach[i].HasConnections() && detach[i].HasConnections();
    for (size_t i = 0; i < names.size(); ++i) seenInitial[i] = seenInitial[i] || present[i];
    if ((active < 0 && AnyPresent()) || (active >= 0 && OtherPresent(active))) {
      ready = false; releasing = true; DetachAll();
    }
    if (!ready || releasing) DetachAll();
    if (active >= 0 && Clock::now() - renewed > lease) { releasing = true; DetachAll(); }
    while (!queue.empty()) {
      auto command = queue.front(); queue.pop_front();
      if (command->cancelled) continue;
      const int index = Index(command->object);
      if (command->kind == Kind::Release) {
        if (!command->token.empty() && command->token != session) {
          Complete(command, active < 0 && retired.count(command->token));
          continue;
        }
        releasing = true; DetachAll(); pending.push_back(command);
      } else if (!ready || info.paused || !Valid(command->token) || index < 0 || releasing ||
                 !command->target.IsFinite()) {
        Complete(command, false);
      } else if (command->kind == Kind::Engage && active < 0 && !retired.count(command->token)
                 && command->target.IsFinite() && parent != kNullEntity && children[index] != kNullEntity
                 && (worldPose(children[index], ecm).Pos() - command->target.Pos()).Length() <= .02) {
        active = index; session = command->token; renewed = Clock::now();
        relative = worldPose(parent, ecm).Inverse() * worldPose(children[index], ecm);
        attach[index].Publish(gz::msgs::Empty()); pending.push_back(command);
      } else if (active == index && session == command->token && !retired.count(command->token)) {
        if (command->kind == Kind::Engage && !present[index]) attach[index].Publish(gz::msgs::Empty());
        renewed = Clock::now(); pending.push_back(command);
      } else Complete(command, false);
    }
  }
  void PostUpdate(const UpdateInfo &info, const EntityComponentManager &ecm) override {
    std::lock_guard<std::mutex> lock(mutex);
    Inspect(ecm);
    const auto currentNs = std::chrono::duration_cast<std::chrono::nanoseconds>(info.simTime).count();
    const bool advanced = !info.paused && currentNs > simNs;
    simNs = currentNs;
    if (advanced && active >= 0 && present[active] && !OtherPresent(active)) ++attachedFrames;
    else if (active < 0 || !present[active] || OtherPresent(active)) attachedFrames = 0;
    bool missing_child = parent == kNullEntity;
    for (const auto child : children) missing_child = missing_child || child == kNullEntity;
    if (!channelsConnected || missing_child) {
      ready = false; detachedFrames = 0;
    } else if (!AnyPresent()) {
      if (advanced) ++detachedFrames;
      // Initial joints can be detached before this observer ever sees them.
      // Readiness depends on current reconciled physics and connected official
      // command channels, not on observing a transient startup attachment.
      if (detachedFrames >= 2) ready = true;
      if (releasing && detachedFrames >= 2) {
        if (!session.empty()) retired.insert(session);
        session.clear(); active = -1; releasing = false;
      }
    } else detachedFrames = 0;
    for (auto it = pending.begin(); it != pending.end();) {
      auto command = *it;
      const bool released = command->kind == Kind::Release && !releasing &&
                            !AnyPresent() && detachedFrames >= 2;
      const bool attached = command->kind != Kind::Release && !releasing && active >= 0 &&
                            command->token == session && present[active] && !OtherPresent(active) && attachedFrames >= 2;
      if (released || attached || command->cancelled) {
        Complete(command, !command->cancelled && (released || attached));
        it = pending.erase(it);
      } else ++it;
    }
  }
};
}
GZ_ADD_PLUGIN(flexcell::DetachableCarryGuard, gz::sim::System,
              flexcell::DetachableCarryGuard::ISystemConfigure,
              flexcell::DetachableCarryGuard::ISystemPreUpdate,
              flexcell::DetachableCarryGuard::ISystemPostUpdate)
