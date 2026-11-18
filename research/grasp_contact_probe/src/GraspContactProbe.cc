// Grasp contact probe: a closed-loop, force-limited parallel-jaw rig that
// squeezes a rigid box with real DART contact and records the object pose
// relative to the gripper every physics step.
//
// This system never creates, teleports or welds a joint between gripper and
// object. The only coupling is contact + friction. If the object rises with the
// gripper, it is because the contact solver held it.
//
// Deterministic by construction: all motion is a function of simulation time,
// so a trial can be replayed bit-for-bit from the same world file.
#include <gz/msgs/empty.pb.h>
#include <gz/plugin/Register.hh>
#include <gz/transport/Node.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/Collision.hh>
#include <gz/sim/components/ContactSensorData.hh>
#include <gz/sim/components/JointForceCmd.hh>
#include <gz/sim/components/JointPosition.hh>
#include <gz/sim/components/JointVelocity.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace flexcell {
namespace {

constexpr double kPi = 3.14159265358979323846;

double SmoothStep(double u) {
  u = std::clamp(u, 0.0, 1.0);
  return u * u * (3.0 - 2.0 * u);
}

double Clamp(double v, double limit) { return std::clamp(v, -limit, limit); }

template <typename T>
T Param(const sdf::ElementPtr &config, const std::string &key, const T &fallback) {
  return config->Get<T>(key, fallback).first;
}

}  // namespace

class GraspContactProbe final : public gz::sim::System,
                               public gz::sim::ISystemConfigure,
                               public gz::sim::ISystemPreUpdate,
                               public gz::sim::ISystemPostUpdate {
 public:
  void Configure(const gz::sim::Entity &entity,
                 const std::shared_ptr<const sdf::Element> &sdf,
                 gz::sim::EntityComponentManager &ecm,
                 gz::sim::EventManager &) override {
    using namespace gz::sim;
    world_ = entity;
    const auto config = sdf->Clone();

    const std::string logPath = Param<std::string>(config, "log_path", "");
    if (logPath.empty())
      throw std::runtime_error("grasp probe: log_path is required");
    const std::string objectModel = Param<std::string>(config, "object_model", "");
    const std::string gripperModel = Param<std::string>(config, "gripper_model", "gripper");
    const std::string baseLink = Param<std::string>(config, "base_link", "base_link");
    const std::string objectLink = Param<std::string>(config, "object_link", "link");
    const std::string leftJoint = Param<std::string>(config, "left_joint", "finger_left_joint");
    const std::string rightJoint = Param<std::string>(config, "right_joint", "finger_right_joint");
    const std::string liftJoint = Param<std::string>(config, "lift_joint", "lift_joint");

    openGap_ = Param<double>(config, "open_gap", 0.056);
    closedGap_ = Param<double>(config, "closed_gap", 0.02);
    settleS_ = Param<double>(config, "settle_s", 0.30);
    closeS_ = Param<double>(config, "close_s", 0.40);
    liftS_ = Param<double>(config, "lift_s", 0.50);
    holdS_ = Param<double>(config, "hold_s", 0.50);
    liftHeight_ = Param<double>(config, "lift_height", 0.15);
    kpFinger_ = Param<double>(config, "kp_finger", 1000.0);
    kdFinger_ = Param<double>(config, "kd_finger", 20.0);
    maxFingerForce_ = Param<double>(config, "max_finger_force", 20.0);
    kpLift_ = Param<double>(config, "kp_lift", 4000.0);
    kdLift_ = Param<double>(config, "kd_lift", 80.0);
    maxLiftForce_ = Param<double>(config, "max_lift_force", 80.0);
    gripperMass_ = Param<double>(config, "gripper_mass", 0.6);
    payloadMass_ = Param<double>(config, "payload_mass", 0.05);
    mode_ = Param<std::string>(config, "mode", "contact");
    if (mode_ != "contact" && mode_ != "magnet")
      throw std::runtime_error("grasp probe: mode must be contact or magnet");
    magnet_ = mode_ == "magnet";
    if (magnet_) {
      attachTopic_ = Param<std::string>(config, "attach_topic", "/probe/magnet/attach");
      attachPub_ = node_.Advertise<gz::msgs::Empty>(attachTopic_);
    }

    // Entity creation happens after world plugins are configured, so the whole
    // graph is resolved lazily on the first step (see Resolve).
    gripperName_ = gripperModel;
    objectName_ = objectModel;
    baseLinkName_ = baseLink;
    objectLinkName_ = objectLink;
    leftJointName_ = leftJoint;
    rightJointName_ = rightJoint;
    liftJointName_ = liftJoint;

    log_.open(logPath, std::ios::out | std::ios::trunc);
    Require(log_.good(), "cannot open step log: " + logPath);
    log_ << std::setprecision(17);
  }

  void PreUpdate(const gz::sim::UpdateInfo &info,
                 gz::sim::EntityComponentManager &ecm) override {
    if (info.paused) return;
    const double t = std::chrono::duration<double>(info.simTime).count();
    if (!resolved_) {
      if (!Resolve(ecm) && t > 0.2) throw std::runtime_error("grasp probe: world graph not found");
      if (!resolved_) return;
    }

    // Phase machine: pure function of simulation time.
    const double closeEnd = settleS_ + closeS_;
    const double liftEnd = closeEnd + liftS_;
    double gapTarget = openGap_;
    double liftTarget = 0.0;
    if (t < settleS_) {
      gapTarget = openGap_;
    } else if (t < closeEnd) {
      gapTarget = openGap_ + (closedGap_ - openGap_) * SmoothStep((t - settleS_) / closeS_);
    } else if (t < liftEnd) {
      gapTarget = closedGap_;
      liftTarget = liftHeight_ * SmoothStep((t - closeEnd) / liftS_);
    } else {
      gapTarget = closedGap_;
      liftTarget = liftHeight_;
    }
    if (magnet_) {
      // Magnet backend: the jaw never touches the object. Everything the object
      // gets comes from the detachable joint that the mainline would use.
      gapTarget = openGap_;
      if (t >= closeEnd && !attachSent_) {
        gz::msgs::Empty message;
        attachPub_.Publish(message);
        attachSent_ = true;
      }
    }
    gapTarget_ = gapTarget;
    liftTarget_ = liftTarget;

    // Finger position servo with effort cap. q_target is the joint travel that
    // would give the commanded gap: gap = open_gap - 2 q.
    const double qTarget = 0.5 * (openGap_ - gapTarget);
    const double ql = JointPositionOf(ecm, leftJoint_);
    const double qr = JointPositionOf(ecm, rightJoint_);
    const double vl = JointVelocityOf(ecm, leftJoint_);
    const double vr = JointVelocityOf(ecm, rightJoint_);
    cmdLeft_ = Clamp(kpFinger_ * (qTarget - ql) - kdFinger_ * vl, maxFingerForce_);
    cmdRight_ = Clamp(kpFinger_ * (qTarget - qr) - kdFinger_ * vr, maxFingerForce_);
    SetForce(ecm, leftJoint_, cmdLeft_);
    SetForce(ecm, rightJoint_, cmdRight_);

    // Vertical lift servo with gravity feed-forward.
    const double z = JointPositionOf(ecm, liftJoint_);
    const double vz = JointVelocityOf(ecm, liftJoint_);
    const double feedforward = (gripperMass_ + payloadMass_) * 9.8;
    cmdLift_ = Clamp(kpLift_ * (liftTarget - z) - kdLift_ * vz + feedforward, maxLiftForce_);
    SetForce(ecm, liftJoint_, cmdLift_);
  }

  void PostUpdate(const gz::sim::UpdateInfo &info,
                  const gz::sim::EntityComponentManager &ecm) override {
    if (info.paused || !resolved_) return;
    const double t = std::chrono::duration<double>(info.simTime).count();
    const double closeEnd = settleS_ + closeS_;
    const double liftEnd = closeEnd + liftS_;
    const char *phase = t < settleS_ ? "settle" : t < closeEnd ? "close" : t < liftEnd ? "lift" : "hold";

    const auto objPose = gz::sim::worldPose(objLink_, ecm);
    const auto basePose = gz::sim::worldPose(baseLink_, ecm);
    const auto rel = basePose.Inverse() * objPose;

    const double ql = JointPositionOf(ecm, leftJoint_);
    const double qr = JointPositionOf(ecm, rightJoint_);
    const double z = JointPositionOf(ecm, liftJoint_);
    const double gapActual = openGap_ - (ql + qr);

    log_ << "{\"iter\":" << info.iterations << ",\"t\":" << t
         << ",\"phase\":\"" << phase << "\""
         << ",\"mode\":\"" << mode_ << "\",\"attached\":" << (attachSent_ ? "true" : "false");
    WritePose("obj", objPose);
    WritePose("base", basePose);
    WritePose("rel", rel);
    log_ << ",\"joints\":{\"left\":{\"q\":" << ql << ",\"qd\":" << JointVelocityOf(ecm, leftJoint_)
         << ",\"f\":" << ForceOf(ecm, leftJoint_)
         << "},\"right\":{\"q\":" << qr << ",\"qd\":" << JointVelocityOf(ecm, rightJoint_)
         << ",\"f\":" << ForceOf(ecm, rightJoint_)
         << "},\"lift\":{\"q\":" << z << ",\"qd\":" << JointVelocityOf(ecm, liftJoint_)
         << ",\"f\":" << ForceOf(ecm, liftJoint_) << "}}";
    const auto leftPad = Summarize(ecm, leftPad_, {"left_pad", "right_pad", "obj_col"});
    const auto rightPad = Summarize(ecm, rightPad_, {"left_pad", "right_pad", "obj_col"});
    const auto objContacts = Summarize(ecm, objCol_, {"ground_col"});
    log_ << ",\"contacts\":{\"left_pad\":" << leftPad.count
         << ",\"right_pad\":" << rightPad.count
         << ",\"left_pad_force\":" << leftPad.peak
         << ",\"right_pad_force\":" << rightPad.peak
         << ",\"obj_contacts\":" << objContacts.count
         << ",\"obj_ground\":" << objContacts.partner << "}";
    log_ << ",\"cmd\":{\"left\":" << cmdLeft_ << ",\"right\":" << cmdRight_ << ",\"lift\":" << cmdLift_ << "}";
    const auto lfPose = gz::sim::worldPose(leftFingerLink_, ecm);
    const auto rfPose = gz::sim::worldPose(rightFingerLink_, ecm);
    log_ << ",\"fingers_world\":{\"left\":[" << lfPose.Pos().X() << ',' << lfPose.Pos().Y() << ',' << lfPose.Pos().Z() << "],\"right\":[" << rfPose.Pos().X() << ',' << rfPose.Pos().Y() << ',' << rfPose.Pos().Z() << "]}";
    log_ << ",\"gap_target\":" << gapTarget_ << ",\"gap_actual\":" << gapActual
         << ",\"lift_target\":" << liftTarget_ << "}\n";
    if (!log_) throw std::runtime_error("grasp probe: step log write failed");
  }

 private:
  using Entity = gz::sim::Entity;
  using EntityComponentManager = gz::sim::EntityComponentManager;

  static void Require(bool ok, const std::string &message) {
    if (!ok) throw std::runtime_error("grasp probe: " + message);
  }

  bool Resolve(EntityComponentManager &ecm) {
    using namespace gz::sim;
    const auto gripper = ecm.EntityByComponents(components::Model(), components::Name(gripperName_),
                                                components::ParentEntity(world_));
    const auto object = ecm.EntityByComponents(components::Model(), components::Name(objectName_),
                                               components::ParentEntity(world_));
    if (gripper == kNullEntity || object == kNullEntity) return false;
    baseLink_ = ecm.EntityByComponents(components::Link(), components::Name(baseLinkName_),
                                       components::ParentEntity(gripper));
    objLink_ = ecm.EntityByComponents(components::Link(), components::Name(objectLinkName_),
                                      components::ParentEntity(object));
    const gz::sim::Model gripperHandle(gripper);
    leftJoint_ = gripperHandle.JointByName(ecm, leftJointName_);
    rightJoint_ = gripperHandle.JointByName(ecm, rightJointName_);
    liftJoint_ = gripperHandle.JointByName(ecm, liftJointName_);
    leftFingerLink_ = ecm.EntityByComponents(components::Link(), components::Name("left_finger"),
                                             components::ParentEntity(gripper));
    rightFingerLink_ = ecm.EntityByComponents(components::Link(), components::Name("right_finger"),
                                              components::ParentEntity(gripper));
    leftPad_ = PadOf(ecm, gripper, "left_finger", "left_pad");
    rightPad_ = PadOf(ecm, gripper, "right_finger", "right_pad");
    objCol_ = PadOf(ecm, object, objectLinkName_, "obj_col");
    if (baseLink_ == kNullEntity || objLink_ == kNullEntity || leftJoint_ == kNullEntity ||
        rightJoint_ == kNullEntity || liftJoint_ == kNullEntity) return false;
    // The physics engine only refreshes joint state components it finds in the
    // ECM, and setForce-style command components do not imply their presence.
    for (const auto joint : {leftJoint_, rightJoint_, liftJoint_}) {
      if (ecm.Component<components::JointPosition>(joint) == nullptr)
        ecm.CreateComponent(joint, components::JointPosition());
      if (ecm.Component<components::JointVelocity>(joint) == nullptr)
        ecm.CreateComponent(joint, components::JointVelocity());
    }
    resolved_ = true;
    return true;
  }

  static Entity PadOf(const EntityComponentManager &ecm, Entity model, const std::string &link,
                     const std::string &collision) {
    const auto linkEntity = ecm.EntityByComponents(gz::sim::components::Link(),
                                                   gz::sim::components::Name(link),
                                                   gz::sim::components::ParentEntity(model));
    if (linkEntity == gz::sim::kNullEntity) return gz::sim::kNullEntity;
    return ecm.EntityByComponents(gz::sim::components::Collision(),
                                  gz::sim::components::Name(collision),
                                  gz::sim::components::ParentEntity(linkEntity));
  }

  static double JointPositionOf(const EntityComponentManager &ecm, Entity joint) {
    const auto *component = ecm.Component<gz::sim::components::JointPosition>(joint);
    if (component == nullptr || component->Data().empty()) return 0.0;
    return component->Data().front();
  }

  static double JointVelocityOf(const EntityComponentManager &ecm, Entity joint) {
    const auto *component = ecm.Component<gz::sim::components::JointVelocity>(joint);
    if (component == nullptr || component->Data().empty()) return 0.0;
    return component->Data().front();
  }

  static double ForceOf(const EntityComponentManager &ecm, Entity joint) {
    const auto *component = ecm.Component<gz::sim::components::JointForceCmd>(joint);
    if (component == nullptr || component->Data().empty()) return 0.0;
    return component->Data().front();
  }

  static void SetForce(EntityComponentManager &ecm, Entity joint, double force) {
    ecm.SetComponentData<gz::sim::components::JointForceCmd>(joint, std::vector<double>{force});
  }

  // Contact bookkeeping for one instrumented collision. count is the number of
  // contact pairs reported this step; partner is how many of those pairs involve
  // one of the named partner collisions (used to separate ground contact from
  // jaw contact on the object).
  struct ContactSummary {
    int count{-1};
    int partner{0};
    double peak{0.0};
  };

  static ContactSummary Summarize(const EntityComponentManager &ecm, Entity collision,
                                  const std::vector<std::string> &partners) {
    ContactSummary summary;
    if (collision == gz::sim::kNullEntity) return summary;
    const auto *component = ecm.Component<gz::sim::components::ContactSensorData>(collision);
    if (component == nullptr) return summary;
    const auto &data = component->Data();
    summary.count = data.contact_size();
    for (const auto &contact : data.contact()) {
      // Contact names can be scoped ("model::link::collision"), so match on suffix.
      const auto matches = [&partners](const std::string &name) {
        for (const auto &partner : partners) {
          if (name.size() >= partner.size() &&
              name.compare(name.size() - partner.size(), partner.size(), partner) == 0)
            return true;
        }
        return false;
      };
      if (matches(contact.collision1().name()) || matches(contact.collision2().name()))
        ++summary.partner;
      for (int i = 0; i < contact.wrench_size(); ++i) {
        const auto &force = contact.wrench(i).body_1_wrench().force();
        summary.peak = std::max(summary.peak, std::sqrt(force.x() * force.x() +
                                                       force.y() * force.y() +
                                                       force.z() * force.z()));
      }
    }
    return summary;
  }

  void WritePose(const char *key, const gz::math::Pose3d &pose) {
    const auto &p = pose.Pos();
    const auto &q = pose.Rot();
    log_ << ",\"" << key << "\":{\"p\":[" << p.X() << ',' << p.Y() << ',' << p.Z()
         << "],\"q\":[" << q.X() << ',' << q.Y() << ',' << q.Z() << ',' << q.W() << "]}";
  }

  Entity world_{gz::sim::kNullEntity};
  Entity baseLink_{gz::sim::kNullEntity};
  Entity objLink_{gz::sim::kNullEntity};
  Entity leftJoint_{gz::sim::kNullEntity};
  Entity rightJoint_{gz::sim::kNullEntity};
  Entity liftJoint_{gz::sim::kNullEntity};
  Entity leftPad_{gz::sim::kNullEntity};
  Entity rightPad_{gz::sim::kNullEntity};
  Entity objCol_{gz::sim::kNullEntity};

  double openGap_{0.056}, closedGap_{0.02};
  double settleS_{0.30}, closeS_{0.40}, liftS_{0.50}, holdS_{0.50}, liftHeight_{0.15};
  double kpFinger_{1000.0}, kdFinger_{20.0}, maxFingerForce_{20.0};
  double kpLift_{4000.0}, kdLift_{80.0}, maxLiftForce_{80.0};
  double gripperMass_{0.6}, payloadMass_{0.05};
  double gapTarget_{0.056}, liftTarget_{0.0};
  std::string gripperName_, objectName_, baseLinkName_, objectLinkName_;
  std::string leftJointName_, rightJointName_, liftJointName_;
  Entity leftFingerLink_{gz::sim::kNullEntity};
  Entity rightFingerLink_{gz::sim::kNullEntity};
  bool resolved_{false};
  double cmdLeft_{0.0}, cmdRight_{0.0}, cmdLift_{0.0};
  std::string mode_{"contact"}, attachTopic_;
  bool magnet_{false}, attachSent_{false};
  gz::transport::Node node_;
  gz::transport::Node::Publisher attachPub_;
  std::ofstream log_;
};

}  // namespace flexcell

GZ_ADD_PLUGIN(flexcell::GraspContactProbe, gz::sim::System,
              flexcell::GraspContactProbe::ISystemConfigure,
              flexcell::GraspContactProbe::ISystemPreUpdate,
              flexcell::GraspContactProbe::ISystemPostUpdate)
