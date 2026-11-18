// Contact-only carry guard for a two-jaw gripper.
//
// This system replaces the DetachableJoint carry path with real contact: it
// closes the jaw onto the object with a force-limited servo, confirms the grasp
// from joint stall + contact, and confirms release from the jaw opening again.
// It never creates a joint, never sets an object pose and never writes a
// velocity: if the object travels, the contact solver is doing the work.
//
// Service contract (mirrors DetachableCarryGuard's style, JSON in/out):
//   /world/<world>/flexcell/contact/grasp    {"object":"target_box_a"}
//   /world/<world>/flexcell/contact/release  {}
//   /world/<world>/flexcell/contact/status   {}
// Reply: {"ok":true,"state":"GRASPED|RELEASED|IDLE|FAILED","gap":0.0350,...}
#include <gz/msgs/stringmsg.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/components/ContactSensorData.hh>
#include <gz/sim/components/Collision.hh>
#include <gz/sim/components/JointForceCmd.hh>
#include <gz/sim/components/JointPosition.hh>
#include <gz/sim/components/JointVelocity.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/transport/Node.hh>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <deque>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>

namespace flexcell {
using namespace gz::sim;

class ContactCarryGuard final : public System, public ISystemConfigure,
                                public ISystemPreUpdate, public ISystemPostUpdate {
  using Clock = std::chrono::steady_clock;
  enum class Kind { Grasp, Release, Status, Lift };

  struct Command {
    Kind kind;
    std::string object;
    bool done{false}, success{false};
    std::string state;
    double gap{0.0};
    std::condition_variable ready;
  };

  gz::transport::Node node;
  std::mutex mutex;
  Entity world{kNullEntity};
  Entity leftJoint{kNullEntity}, rightJoint{kNullEntity}, objectLink{kNullEntity};
  Entity baseLink{kNullEntity}, objectModel{kNullEntity}, liftJoint{kNullEntity};
  std::deque<std::shared_ptr<Command>> queue;
  std::shared_ptr<Command> pendingGrasp, pendingRelease;
  double pendingSince{-1.0};

  std::string objectName{"target_box_a"}, gripperModel{"open_manipulator_x"};
  std::string leftName{"gripper_left_joint"}, rightName{"gripper_right_joint"};
  double zeroGap{0.034}, closedGap{0.026}, maxForce{1.5}, kp{30.0}, kd{1.0};
  double expectedWidth{0.035}, widthTolerance{0.006};
  std::string baseName{"base_link"}, liftName{"lift_joint"};
  double liftHeight{0.15}, liftTime{0.5}, liftStart{-1.0}, liftGoal{0.0}, liftNow{0.0};
  int confirmFrames{40};
  double targetGap{0.034};
  bool engaged{false};
  int stallFrames{0};
  double gapNow{0.034}, objZ{0.0}, baseZ{0.0}, qLeft{0.0}, qRight{0.0};
  double signLeft_{1.0}, signRight_{1.0}, calibrateRef{0.0};
  double offX{0.0}, offY{0.0}, offZ{0.0}, jawSpeed{0.0};
  double jointLower{-0.011}, jointUpper{0.020};
  int calibSteps{0};

  static double Value(const std::string &json, const std::string &key, double fallback) {
    const auto at = json.find("\"" + key + "\"");
    if (at == std::string::npos) return fallback;
    const auto colon = json.find(':', at);
    if (colon == std::string::npos) return fallback;
    try {
      return std::stod(json.substr(colon + 1));
    } catch (const std::exception &) {
      return fallback;
    }
  }

  static std::string Text(const std::string &json, const std::string &key) {
    const auto at = json.find("\"" + key + "\"");
    if (at == std::string::npos) return {};
    const auto first = json.find('"', json.find(':', at) + 1);
    if (first == std::string::npos) return {};
    const auto last = json.find('"', first + 1);
    return last == std::string::npos ? std::string{} : json.substr(first + 1, last - first - 1);
  }

  static double JointPosition(const EntityComponentManager &ecm, Entity joint) {
    const auto *component = ecm.Component<components::JointPosition>(joint);
    if (component == nullptr || component->Data().empty()) return 0.0;
    return component->Data().front();
  }

  static double JointVelocity(const EntityComponentManager &ecm, Entity joint) {
    const auto *component = ecm.Component<components::JointVelocity>(joint);
    if (component == nullptr || component->Data().empty()) return 0.0;
    return component->Data().front();
  }

  void Resolve(EntityComponentManager &ecm) {
    if (leftJoint != kNullEntity) return;
    const auto gripper = ecm.EntityByComponents(components::Model(), components::Name(gripperModel),
                                                components::ParentEntity(world));
    if (gripper == kNullEntity) return;
    const gz::sim::Model handle(gripper);
    const auto left = handle.JointByName(ecm, leftName);
    const auto right = handle.JointByName(ecm, rightName);
    if (left == kNullEntity || right == kNullEntity) return;
    for (const auto joint : {left, right}) {
      if (ecm.Component<components::JointPosition>(joint) == nullptr)
        ecm.CreateComponent(joint, components::JointPosition());
      if (ecm.Component<components::JointVelocity>(joint) == nullptr)
        ecm.CreateComponent(joint, components::JointVelocity());
    }
    leftJoint = left;
    rightJoint = right;

    if (objectLink != kNullEntity) return;
    objectModel = ecm.EntityByComponents(components::Model(), components::Name(objectName),
                                         components::ParentEntity(world));
    if (objectModel != kNullEntity)
      objectLink = ecm.EntityByComponents(components::Link(), components::Name("link"),
                                          components::ParentEntity(objectModel));
    baseLink = ecm.EntityByComponents(components::Link(), components::Name(baseName),
                                      components::ParentEntity(gripper));
    if (!liftName.empty()) {
      liftJoint = handle.JointByName(ecm, liftName);
      if (liftJoint != kNullEntity) {
        if (ecm.Component<components::JointPosition>(liftJoint) == nullptr)
          ecm.CreateComponent(liftJoint, components::JointPosition());
        if (ecm.Component<components::JointVelocity>(liftJoint) == nullptr)
          ecm.CreateComponent(liftJoint, components::JointVelocity());
      }
    }
  }

  bool Reply(const gz::msgs::StringMsg &request, const Kind kind,
             gz::msgs::StringMsg &reply) {
    auto command = std::make_shared<Command>();
    command->kind = kind;
    command->object = kind == Kind::Grasp ? Text(request.data(), "object") : std::string{};
    {
      std::lock_guard<std::mutex> lock(mutex);
      queue.push_back(command);
    }
    std::unique_lock<std::mutex> lock(mutex);
    if (!command->ready.wait_for(lock, std::chrono::milliseconds(6000),
                                 [&command] { return command->done; })) {
      std::ostringstream out;
      out << "{\"ok\":false,\"state\":\"TIMEOUT\",\"gap\":" << gapNow
          << ",\"obj_z\":" << objZ << ",\"base_z\":" << baseZ
          << ",\"rel_z\":" << (objZ - baseZ)
          << ",\"ql\":" << qLeft << ",\"qr\":" << qRight
          << ",\"stall\":" << stallFrames
          << ",\"ox\":" << offX << ",\"oy\":" << offY << ",\"oz\":" << offZ
          << ",\"jaw_speed\":" << jawSpeed << "}";
      reply.set_data(out.str());
      return true;
    }
    std::ostringstream out;
    out << "{\"ok\":" << (command->success ? "true" : "false")
        << ",\"state\":\"" << command->state << "\",\"gap\":" << command->gap
        << ",\"obj_z\":" << objZ << ",\"base_z\":" << baseZ
        << ",\"rel_z\":" << (objZ - baseZ)
        << ",\"ql\":" << qLeft << ",\"qr\":" << qRight << "}";
    reply.set_data(out.str());
    return true;
  }

  bool Grasp(const gz::msgs::StringMsg &request, gz::msgs::StringMsg &reply) {
    return Reply(request, Kind::Grasp, reply);
  }
  bool Release(const gz::msgs::StringMsg &, gz::msgs::StringMsg &reply) {
    return Reply({}, Kind::Release, reply);
  }
  bool Status(const gz::msgs::StringMsg &, gz::msgs::StringMsg &reply) {
    return Reply({}, Kind::Status, reply);
  }
  bool Lift(const gz::msgs::StringMsg &request, gz::msgs::StringMsg &reply) {
    auto command = std::make_shared<Command>();
    command->kind = Kind::Lift;
    command->object = request.data();
    liftHeight = Value(request.data(), "height", liftHeight);
    liftTime = Value(request.data(), "time", liftTime);
    {
      std::lock_guard<std::mutex> lock(mutex);
      queue.push_back(command);
    }
    std::unique_lock<std::mutex> lock(mutex);
    command->ready.wait_for(lock, std::chrono::milliseconds(300), [&command] { return command->done; });
    std::ostringstream out;
    out << "{\"ok\":" << (command->done ? "true" : "false") << ",\"state\":\""
        << (engaged ? "GRASPED" : "UNGRASPED") << "\",\"gap\":" << gapNow
        << ",\"obj_z\":" << objZ << ",\"base_z\":" << baseZ
        << ",\"rel_z\":" << (objZ - baseZ)
        << ",\"ql\":" << qLeft << ",\"qr\":" << qRight << "}";
    reply.set_data(out.str());
    return true;
  }

  void Complete(const std::shared_ptr<Command> &command, bool success, const char *state) {
    command->success = success;
    command->state = state;
    command->gap = gapNow;
    command->done = true;
    command->ready.notify_all();
  }

 public:
  void Configure(const Entity &entity, const std::shared_ptr<const sdf::Element> &sdf,
                 EntityComponentManager &ecm, EventManager &) override {
    world = entity;
    const auto config = sdf->Clone();
    if (config->HasElement("object_model")) objectName = config->Get<std::string>("object_model");
    if (config->HasElement("gripper_model")) gripperModel = config->Get<std::string>("gripper_model");
    if (config->HasElement("left_joint")) leftName = config->Get<std::string>("left_joint");
    if (config->HasElement("right_joint")) rightName = config->Get<std::string>("right_joint");
    zeroGap = config->HasElement("zero_gap") ? config->Get<double>("zero_gap") : zeroGap;
    jointLower = config->HasElement("joint_lower") ? config->Get<double>("joint_lower") : jointLower;
    jointUpper = config->HasElement("joint_upper") ? config->Get<double>("joint_upper") : jointUpper;
    closedGap = config->HasElement("closed_gap") ? config->Get<double>("closed_gap") : closedGap;
    maxForce = config->HasElement("max_force") ? config->Get<double>("max_force") : maxForce;
    kp = config->HasElement("kp") ? config->Get<double>("kp") : kp;
    kd = config->HasElement("kd") ? config->Get<double>("kd") : kd;
    kp = config->HasElement("kp") ? config->Get<double>("kp") : kp;
    kd = config->HasElement("kd") ? config->Get<double>("kd") : kd;
    confirmFrames = config->HasElement("confirm_frames") ? config->Get<int>("confirm_frames") : confirmFrames;
    expectedWidth = config->HasElement("expected_object_width") ? config->Get<double>("expected_object_width") : expectedWidth;
    widthTolerance = config->HasElement("width_tolerance") ? config->Get<double>("width_tolerance") : widthTolerance;
    if (config->HasElement("base_link")) baseName = config->Get<std::string>("base_link");
    if (config->HasElement("lift_joint")) liftName = config->Get<std::string>("lift_joint");
    if (config->HasElement("lift_height")) liftHeight = config->Get<double>("lift_height");
    if (config->HasElement("lift_time")) liftTime = config->Get<double>("lift_time");
    targetGap = zeroGap;

    const auto name = ecm.Component<components::Name>(world)->Data();
    const auto prefix = "/world/" + name + "/flexcell/contact/";
    if (!node.Advertise(prefix + "lift", &ContactCarryGuard::Lift, this) ||
        !node.Advertise(prefix + "grasp", &ContactCarryGuard::Grasp, this) ||
        !node.Advertise(prefix + "release", &ContactCarryGuard::Release, this) ||
        !node.Advertise(prefix + "status", &ContactCarryGuard::Status, this))
      throw std::runtime_error("contact carry services unavailable");
  }

  void PreUpdate(const UpdateInfo &info, EntityComponentManager &ecm) override {
    if (info.paused) return;
    Resolve(ecm);
    if (leftJoint == kNullEntity) return;

    const double nowT = std::chrono::duration<double>(info.simTime).count();
    std::deque<std::shared_ptr<Command>> local;
    {
      std::lock_guard<std::mutex> lock(mutex);
      local.swap(queue);
    }
    for (const auto &command : local) {
      if (command->kind == Kind::Grasp) {
        if (!command->object.empty() && command->object != objectName) {
          objectName = command->object;
          objectModel = kNullEntity;
          objectLink = kNullEntity;
        }
        targetGap = closedGap;
        stallFrames = 0;
        engaged = false;
        pendingGrasp = command;
        pendingSince = nowT;
        continue;
      } else if (command->kind == Kind::Release) {
        targetGap = zeroGap;
        engaged = false;
        stallFrames = 0;
        pendingRelease = command;
        pendingSince = nowT;
        continue;
      } else if (command->kind == Kind::Lift) {
        if (liftJoint != kNullEntity && engaged) {
          liftStart = nowT;
          liftGoal = liftNow + liftHeight;
        } else {
          command->state = "NOT_GRASPED";
        }
      }
      command->state = command->kind == Kind::Status ? (engaged ? "GRASPED" : "RELEASED")
                                                     : (engaged ? "GRASPED" : "CLOSING");
      if (command->kind == Kind::Status) command->success = engaged;
      command->gap = gapNow;
      command->done = true;
      command->ready.notify_all();
    }

    const double ql = JointPosition(ecm, leftJoint);
    const double qr = JointPosition(ecm, rightJoint);
    gapNow = zeroGap + (ql + qr);
    qLeft = ql;
    qRight = qr;
    // Detect the force sign once: a positive joint force must open the jaw.
    // Models differ (URDF axis vs converted SDF axis), and a wrong sign turns a
    // Calibrate each jaw separately: the two axes are mirrored, so one combined
    // test cannot tell which sign closes which finger.
    if (calibSteps >= 0 && calibSteps < 120) {
      const double probe = 2.0;
      const bool onLeft = calibSteps < 60;
      ecm.SetComponentData<components::JointForceCmd>(leftJoint,
                             std::vector<double>{onLeft ? probe : 0.0});
      ecm.SetComponentData<components::JointForceCmd>(rightJoint,
                             std::vector<double>{onLeft ? 0.0 : probe});
      if (onLeft && calibSteps == 0) calibrateRef = ql;
      if (onLeft && calibSteps == 59) signLeft_ = (ql > calibrateRef + 1e-9) ? 1.0 : -1.0;
      if (!onLeft && calibSteps == 60) calibrateRef = qr;
      if (!onLeft && calibSteps == 119) signRight_ = (qr > calibrateRef + 1e-9) ? 1.0 : -1.0;
      ++calibSteps;
      if (calibSteps >= 120) calibSteps = 9999;
      return;
    }
    const double qTarget = std::clamp(0.5 * (targetGap - zeroGap), jointLower, jointUpper);
    const double forceL = signLeft_ * std::clamp(kp * (qTarget - ql) - kd * JointVelocity(ecm, leftJoint),
                                -maxForce, maxForce);
    const double forceR = signRight_ * std::clamp(kp * (qTarget - qr) - kd * JointVelocity(ecm, rightJoint),
                                -maxForce, maxForce);
    ecm.SetComponentData<components::JointForceCmd>(leftJoint, std::vector<double>{forceL});
    ecm.SetComponentData<components::JointForceCmd>(rightJoint, std::vector<double>{forceR});

    if (liftJoint != kNullEntity) {
      liftNow = JointPosition(ecm, liftJoint);
      if (liftStart >= 0.0) {
        const double u = std::min(1.0, (nowT - liftStart) / std::max(liftTime, 1e-3));
        const double shape = u * u * (3.0 - 2.0 * u);
        const double target = liftGoal * shape;
        const double force = std::clamp(4.0 * kp * (target - liftNow) -
                                        kd * JointVelocity(ecm, liftJoint) + 7.4, -200.0, 200.0);
        ecm.SetComponentData<components::JointForceCmd>(liftJoint, std::vector<double>{force});
      }
    }
  }

  void PostUpdate(const UpdateInfo &info, const EntityComponentManager &ecm) override {
    if (info.paused || leftJoint == kNullEntity) return;
    if (objectLink != kNullEntity) objZ = worldPose(objectLink, ecm).Pos().Z();
    if (baseLink != kNullEntity) baseZ = worldPose(baseLink, ecm).Pos().Z();
    const double speed = std::fabs(JointVelocity(ecm, leftJoint)) +
                         std::fabs(JointVelocity(ecm, rightJoint));
    const bool closing = targetGap < zeroGap - 1e-9;
    // A grasp only counts when the object is really between the jaws: width
    // match alone would also fire on air.
    bool between = false;
    if (objectLink != kNullEntity && baseLink != kNullEntity) {
      const auto basePose = worldPose(baseLink, ecm);
      const auto objPose = worldPose(objectLink, ecm);
      // Judge the offset in the gripper frame: the jaw axis is the base Y axis,
      // so a world-frame check fails whenever the wrist is yawed.
      const auto offset = basePose.Rot().RotateVectorReverse(objPose.Pos() - basePose.Pos());
      offX = offset.X(); offY = offset.Y(); offZ = offset.Z();
      between = std::fabs(offset.Y()) <= 0.030 && std::fabs(offset.X()) <= 0.120 &&
                std::fabs(offset.Z()) <= 0.200;
    }
    jawSpeed = std::fabs(0.5 * (JointVelocity(ecm, leftJoint) + JointVelocity(ecm, rightJoint)));
    const bool onObject = std::fabs(gapNow - expectedWidth) <= widthTolerance && between;
    if (closing && speed < 5e-3 && onObject) {
      if (++stallFrames >= confirmFrames) engaged = true;
    } else if (closing) {
      stallFrames = 0;
    } else if (gapNow > zeroGap - 1e-3) {
      engaged = false;
      stallFrames = 0;
    }

    const double nowT = std::chrono::duration<double>(info.simTime).count();
    {
      std::lock_guard<std::mutex> lock(mutex);
      if (pendingGrasp && engaged) {
        Complete(pendingGrasp, true, "GRASPED");
        pendingGrasp.reset();
      } else if (pendingGrasp && pendingSince >= 0.0 && nowT - pendingSince > 3.0) {
        Complete(pendingGrasp, false, "TIMEOUT");
        pendingGrasp.reset();
      }
      if (pendingRelease && gapNow > zeroGap - 2e-3) {
        Complete(pendingRelease, true, "RELEASED");
        pendingRelease.reset();
      } else if (pendingRelease && pendingSince >= 0.0 && nowT - pendingSince > 3.0) {
        Complete(pendingRelease, false, "TIMEOUT");
        pendingRelease.reset();
      }
    }
  }
};

}  // namespace flexcell

GZ_ADD_PLUGIN(flexcell::ContactCarryGuard, gz::sim::System,
              flexcell::ContactCarryGuard::ISystemConfigure,
              flexcell::ContactCarryGuard::ISystemPreUpdate,
              flexcell::ContactCarryGuard::ISystemPostUpdate)
