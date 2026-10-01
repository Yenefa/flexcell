// Simulation-only pose/velocity constraint. It is not a contact grasp model.
#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/empty.pb.h>
#include <gz/msgs/pose.pb.h>
#include <gz/msgs/stringmsg.pb.h>
#include <gz/msgs/Utility.hh>
#include <gz/plugin/Register.hh>
#include <gz/common/Console.hh>
#include <gz/sim/System.hh>
#include <gz/sim/components/AngularVelocityCmd.hh>
#include <gz/sim/components/LinearVelocityCmd.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/components/Static.hh>
#include <gz/sim/components/PoseCmd.hh>
#include <gz/transport/Node.hh>
#include <chrono>
#include <algorithm>
#include <cctype>
#include <condition_variable>
#include <deque>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <unordered_set>

namespace flexcell {
using namespace gz::sim;
using Clock = std::chrono::steady_clock;

class CarryDynamics final : public System, public ISystemConfigure,
    public ISystemPreUpdate, public ISystemPostUpdate {
  enum class Kind { Engage, Pin, Release };
  struct Command {
    Kind kind;
    gz::msgs::Pose pose;
    std::string session;
    bool done{false}, cancelled{false}, success{false};
    std::condition_variable ready;
  };
  gz::transport::Node node;
  std::mutex mutex;
  std::deque<std::shared_ptr<Command>> queue, applied;
  Entity world{kNullEntity}, model{kNullEntity};
  std::string object, session;
  gz::math::Pose3d target;
  Clock::time_point renewed;
  std::chrono::milliseconds lease{500};
  std::unordered_set<std::string> allowed, retired;
  int64_t releaseSimNs{0};

  static std::string Session(const gz::msgs::Pose &pose) {
    for (const auto &item : pose.header().data())
      if (item.key() == "carry_session" && item.value_size() == 1)
        return item.value(0);
    return {};
  }
  static bool ValidSession(const std::string &value) {
    return value.size() == 32 && std::all_of(value.begin(), value.end(),
        [](unsigned char c) { return std::isxdigit(c); });
  }
  bool Submit(Kind kind, const gz::msgs::Pose &pose,
              const std::string &token, gz::msgs::Boolean &reply) {
    auto cmd = std::make_shared<Command>();
    gzdbg << "carry request kind=" << static_cast<int>(kind) << std::endl;
    cmd->kind = kind; cmd->pose = pose; cmd->session = token;
    std::unique_lock<std::mutex> lock(mutex);
    queue.push_back(cmd);
    // A transport reply must reflect a simulation step, not queue acceptance.
    if (!cmd->ready.wait_for(lock, std::chrono::milliseconds(500),
                            [&] { return cmd->done; })) {
      cmd->cancelled = true;
      gzwarn << "carry simulation acknowledgement timeout" << std::endl;
      reply.set_data(false);
    } else reply.set_data(cmd->success);
    return true;
  }
  bool Engage(const gz::msgs::Pose &pose, gz::msgs::Boolean &reply) {
    return Submit(Kind::Engage, pose, Session(pose), reply);
  }
  bool Pin(const gz::msgs::Pose &pose, gz::msgs::Boolean &reply) {
    return Submit(Kind::Pin, pose, Session(pose), reply);
  }
  bool Release(const gz::msgs::StringMsg &msg, gz::msgs::Boolean &reply) {
    return Submit(Kind::Release, {}, msg.data(), reply);
  }
  bool Status(const gz::msgs::Empty &, gz::msgs::StringMsg &reply) {
    std::lock_guard<std::mutex> lock(mutex);
    std::ostringstream value;
    value << "{\"backend\":\"velocity_servo_v1\",\"engaged\":"
          << (model != kNullEntity ? "true" : "false")
          << ",\"object\":\"" << object << "\",\"session\":\"" << session
          << "\",\"lease_ms\":" << lease.count()
          << ",\"release_sim_ns\":" << releaseSimNs << "}";
    reply.set_data(value.str());
    return true;
  }
  void Disengage(EntityComponentManager &ecm, int64_t simNs) {
    if (model != kNullEntity) {
      ecm.RemoveComponent<components::WorldPoseCmd>(model);
      ecm.RemoveComponent<components::LinearVelocityCmd>(model);
      ecm.RemoveComponent<components::AngularVelocityCmd>(model);
      retired.insert(session);  // delayed pins/engages cannot resurrect ownership
    }
    model = kNullEntity; object.clear(); session.clear(); releaseSimNs = simNs;
  }
 public:
  void Configure(const Entity &entity, const std::shared_ptr<const sdf::Element> &sdf,
                 EntityComponentManager &ecm, EventManager &) override {
    world = entity;
    auto name = ecm.Component<components::Name>(world)->Data();
    if (sdf->HasElement("lease_ms")) lease = std::chrono::milliseconds(sdf->Get<int>("lease_ms"));
    if (lease.count() < 100 || lease.count() > 5000) throw std::runtime_error("invalid carry lease");
    auto item = sdf->FindElement("allowed_model");
    while (item) {
      allowed.insert(item->Get<std::string>());
      item = item->GetNextElement("allowed_model");
    }
    const auto prefix = "/world/" + name + "/flexcell/carry/";
    if (!node.Advertise(prefix + "engage", &CarryDynamics::Engage, this) ||
        !node.Advertise(prefix + "pin", &CarryDynamics::Pin, this) ||
        !node.Advertise(prefix + "release", &CarryDynamics::Release, this) ||
        !node.Advertise(prefix + "status", &CarryDynamics::Status, this))
      throw std::runtime_error("carry service advertisement failed");
  }
  void PreUpdate(const UpdateInfo &info, EntityComponentManager &ecm) override {
    std::lock_guard<std::mutex> lock(mutex);
    const auto simNs = std::chrono::duration_cast<std::chrono::nanoseconds>(info.simTime).count();
    if (model != kNullEntity && (Clock::now() - renewed > lease || !ecm.HasEntity(model)))
      Disengage(ecm, simNs);
    while (!queue.empty()) {
      auto cmd = queue.front(); queue.pop_front();
      if (cmd->cancelled) continue;
      gzdbg << "carry apply kind=" << static_cast<int>(cmd->kind) << std::endl;
      if (cmd->kind == Kind::Release) {
        // Empty token is the explicit force-release/reset operation.
        cmd->success = cmd->session.empty() || cmd->session == session ||
                       (model == kNullEntity && retired.count(cmd->session));
        if (cmd->success) Disengage(ecm, simNs);
      } else if (!info.paused && ValidSession(cmd->session) && allowed.count(cmd->pose.name())) {
        auto pose = gz::msgs::Convert(cmd->pose);
        if (pose.IsFinite()) {
          if (cmd->kind == Kind::Engage && model == kNullEntity && !retired.count(cmd->session)) {
            const auto found = ecm.EntityByComponents(components::Model(),
                components::Name(cmd->pose.name()), components::ParentEntity(world));
            auto isStatic = ecm.Component<components::Static>(found);
            // Refuse to steal velocity components owned by a different system.
            if (found != kNullEntity && (!isStatic || !isStatic->Data()) &&
                !ecm.Component<components::LinearVelocityCmd>(found) &&
                !ecm.Component<components::AngularVelocityCmd>(found)) {
              model = found; object = cmd->pose.name(); session = cmd->session;
            }
          }
          cmd->success = model != kNullEntity && object == cmd->pose.name() && session == cmd->session;
          if (cmd->success) { target = pose; renewed = Clock::now(); }
        }
      }
      applied.push_back(cmd);
    }
    if (model != kNullEntity && !info.paused) {
      ecm.SetComponentData<components::WorldPoseCmd>(model, target);
      ecm.SetComponentData<components::LinearVelocityCmd>(model, gz::math::Vector3d::Zero);
      ecm.SetComponentData<components::AngularVelocityCmd>(model, gz::math::Vector3d::Zero);
    }
  }
  void PostUpdate(const UpdateInfo &, const EntityComponentManager &) override {
    std::lock_guard<std::mutex> lock(mutex);
    for (auto &cmd : applied) { cmd->done = true; cmd->ready.notify_all(); }
    applied.clear();
  }
};
}
GZ_ADD_PLUGIN(flexcell::CarryDynamics, gz::sim::System,
    flexcell::CarryDynamics::ISystemConfigure, flexcell::CarryDynamics::ISystemPreUpdate,
    flexcell::CarryDynamics::ISystemPostUpdate)
GZ_ADD_PLUGIN_ALIAS(flexcell::CarryDynamics, "flexcell::CarryDynamics")
