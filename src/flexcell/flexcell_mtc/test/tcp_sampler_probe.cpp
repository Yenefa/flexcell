// Offline only: no simulator, action client, executor or hardware interface.
#include "virtual_tcp_model.hpp"
#include "position_only_planner.hpp"
#include "planning_evidence.hpp"
#include <moveit/constraint_samplers/default_constraint_samplers.hpp>
#include <moveit/robot_state/attached_body.hpp>
#include <moveit_msgs/msg/attached_collision_object.hpp>
#include <shape_msgs/msg/solid_primitive.hpp>
#include <fstream>
#include <iostream>

static void require(bool value, const std::string& reason) {
  if (!value) throw std::runtime_error(reason);
}
static geometry_msgs::msg::Pose pose(const Eigen::Isometry3d& transform) {
  geometry_msgs::msg::Pose result;
  result.position.x=transform.translation().x(); result.position.y=transform.translation().y(); result.position.z=transform.translation().z();
  const Eigen::Quaterniond q(transform.linear());
  result.orientation.x=q.x(); result.orientation.y=q.y(); result.orientation.z=q.z(); result.orientation.w=q.w();
  return result;
}
class Sampler : public constraint_samplers::IKConstraintSampler {
 public:
  Sampler(const planning_scene::PlanningScenePtr& scene, const std::string& group)
    : IKConstraintSampler(scene, group) {}
  unsigned seed() { return random_number_generator_.getFirstSeed(); }
};
static planning_scene::PlanningScenePtr sceneFor(const moveit::core::RobotModelConstPtr& model,
    const std::vector<std::string>& names, const std::vector<double>& positions, const Eigen::Isometry3d& offset) {
  auto scene=std::make_shared<planning_scene::PlanningScene>(model);
  scene->getCurrentStateNonConst().setToDefaultValues();
  scene->getCurrentStateNonConst().setVariablePositions(names,positions);
  scene->getCurrentStateNonConst().update();
  moveit_msgs::msg::AttachedCollisionObject box;
  box.link_name="end_effector_link"; box.object.id="target_box_a"; box.object.header.frame_id=box.link_name;
  box.object.operation=moveit_msgs::msg::CollisionObject::ADD;
  shape_msgs::msg::SolidPrimitive primitive;
  primitive.type=shape_msgs::msg::SolidPrimitive::BOX; primitive.dimensions={.035,.035,.035};
  box.object.primitives.push_back(primitive); box.object.primitive_poses.push_back(pose(offset));
  require(scene->processAttachedCollisionObjectMsg(box),"cannot reconstruct frozen attachment");
  return scene;
}
struct Samples { int accepted=0,collision_checks=0; double max_error=0.; unsigned seed=0; };
static Samples sampleGoal(const planning_scene::PlanningScenePtr& scene, const std::string& group,
    const std::string& link, const Eigen::Isometry3d& offset, const Eigen::Isometry3d& target) {
  Samples result;
  Sampler sampler(scene,group);
  result.seed=sampler.seed();
  require(sampler.configure(flexcell::positionGoal("world",link,offset,target,1e-4)),"cannot configure point sampler");
  sampler.setGroupStateValidityCallback([&](moveit::core::RobotState* state,const moveit::core::JointModelGroup* arm,const double* joints) {
    ++result.collision_checks; state->setJointGroupPositions(arm,joints); state->update();
    return !scene->isStateColliding(*state,arm->getName());
  });
  auto state=scene->getCurrentState();
  for(int i=0;i<20;++i) {
    if(!sampler.sample(state,scene->getCurrentState(),20)) continue;
    ++result.accepted;
    const double error=((state.getGlobalLinkTransform(link)*offset).translation()-target.translation()).norm();
    result.max_error=std::max(result.max_error,error);
    require(error<=1e-4,"accepted point goal violates unchanged tolerance");
    require(!scene->isStateColliding(state,group),"accepted point goal is colliding");
  }
  return result;
}
int main(int argc,char** argv) {
  rclcpp::init(argc,argv);
  auto node=std::make_shared<rclcpp::Node>("flexcell_tcp_probe",rclcpp::NodeOptions().automatically_declare_parameters_from_overrides(true));
  int exit=1;
  try {
    robot_model_loader::RobotModelLoader original(node,"robot_description");
    const auto names=node->get_parameter("frozen_joint_names").as_string_array();
    const auto positions=node->get_parameter("frozen_joint_positions").as_double_array();
    const auto p=node->get_parameter("tcp_pose").as_double_array(); require(p.size()==7,"invalid frozen transform");
    Eigen::Isometry3d offset=Eigen::Isometry3d::Identity(); offset.translation()=Eigen::Vector3d(p[0],p[1],p[2]);
    offset.linear()=Eigen::Quaterniond(p[6],p[3],p[4],p[5]).normalized().toRotationMatrix();
    flexcell::VirtualTcpModel tcp(node,offset);
    auto legacy=sceneFor(original.getModel(),names,positions,offset);
    auto adapted=sceneFor(tcp.model(),names,positions,offset);
    moveit_msgs::msg::PlanningScene scene_message; legacy->getPlanningSceneMsg(scene_message);
    flexcell_interfaces::srv::PlanManipulation::Request request;
    request.operation="PLACE";request.object_name="target_box_a";request.attached_object_targets=true;
    request.motion_profile_id="demo_slow";request.deadline_ms=30000;
    request.object_pose.header.frame_id="world";
    request.object_pose.pose=pose(legacy->getCurrentState().getGlobalLinkTransform("end_effector_link")*offset);
    for(double z:{.1675,.0675,.1675}) {
      geometry_msgs::msg::PoseStamped target;target.header.frame_id="world";
      target.pose.position.x=.12;target.pose.position.y=-.15;target.pose.position.z=z;target.pose.orientation.w=1.;
      request.targets.push_back(target);
    }
    flexcell::PlanningEvidence captured(node,request,scene_message);captured.model(tcp.urdf_xml,tcp.srdf_xml);
    const auto* evidence_env=std::getenv("FLEXCELL_MTC_PLAN_EVIDENCE_DIR");
    require(evidence_env && *evidence_env,"offline evidence capture must be enabled");
    const std::string evidence_path=evidence_env;
    const auto blocker=std::filesystem::path(node->get_parameter("probe_output").as_string()).parent_path()/"blocked-evidence";
    {std::ofstream file(blocker);file<<"intentional non-directory control";}
    setenv("FLEXCELL_MTC_PLAN_EVIDENCE_DIR",blocker.c_str(),1);
    bool write_rejected=false;
    try { flexcell::PlanningEvidence blocked_capture(node,request,scene_message); }
    catch (const std::exception&) { write_rejected=true; }
    setenv("FLEXCELL_MTC_PLAN_EVIDENCE_DIR",evidence_path.c_str(),1);
    require(write_rejected,"evidence-write failure did not block the request");
    require((legacy->getCurrentState().getGlobalLinkTransform("end_effector_link").matrix()-
             adapted->getCurrentState().getGlobalLinkTransform("end_effector_link").matrix()).norm()<1e-12,"real EE FK changed");
    Eigen::Isometry3d hover=Eigen::Isometry3d::Identity();hover.translation()=Eigen::Vector3d(.12,-.15,.1675);
    auto before=sampleGoal(legacy,"arm","end_effector_link",offset,hover);
    auto after=sampleGoal(adapted,flexcell::VirtualTcpModel::group,flexcell::VirtualTcpModel::link,Eigen::Isometry3d::Identity(),hover);
    require(after.accepted>before.accepted,"virtual TCP did not improve sampled valid goals");
    require(after.accepted>0,"virtual TCP produced no valid goal");
    auto blocked=sceneFor(tcp.model(),names,positions,offset);
    moveit_msgs::msg::CollisionObject obstacle;
    obstacle.header.frame_id="world"; obstacle.id="blocked_tcp"; obstacle.operation=moveit_msgs::msg::CollisionObject::ADD;
    shape_msgs::msg::SolidPrimitive sphere; sphere.type=shape_msgs::msg::SolidPrimitive::SPHERE;sphere.dimensions={.08};
    obstacle.primitives.push_back(sphere); obstacle.primitive_poses.push_back(pose(hover));
    require(blocked->processCollisionObjectMsg(obstacle),"cannot add blocked-goal control");
    auto rejected=sampleGoal(blocked,flexcell::VirtualTcpModel::group,flexcell::VirtualTcpModel::link,Eigen::Isometry3d::Identity(),hover);
    require(rejected.accepted==0 && rejected.collision_checks>0,"collision control was not rejected");
    flexcell::PositionOnlyPlanner planner(node,"ompl"); planner.init(tcp.model());
    planner.setMaxVelocityScalingFactor(.2);planner.setMaxAccelerationScalingFactor(.2);
    flexcell_interfaces::srv::PlanManipulation::Response planned;
    for(int i=0;i<3;++i) {
      auto target=hover; const bool retreat=i==2;
      std::string group=flexcell::VirtualTcpModel::group,link=flexcell::VirtualTcpModel::link;
      if(i==1) target.translation().z()=.0675;
      if(retreat) {
        moveit_msgs::msg::AttachedCollisionObject remove;remove.object.id="target_box_a";
        remove.object.operation=moveit_msgs::msg::CollisionObject::REMOVE;
        require(adapted->processAttachedCollisionObjectMsg(remove),"cannot detach for offline retreat");
        target=adapted->getCurrentState().getGlobalLinkTransform("end_effector_link");target.translation().z()+=.1;
        group="arm";link="end_effector_link";
      }
      robot_trajectory::RobotTrajectoryPtr trajectory;
      auto result=planner.plan(adapted,*tcp.model()->getLinkModel(link),Eigen::Isometry3d::Identity(),target,
        tcp.model()->getJointModelGroup(group),5.,trajectory,moveit_msgs::msg::Constraints());
      require(result.success && trajectory && !trajectory->empty(),"offline stage "+std::to_string(i)+": "+result.message);
      adapted->setCurrentState(trajectory->getLastWayPoint());
      require((adapted->getCurrentState().getGlobalLinkTransform(link).translation()-target.translation()).norm()<=1e-4,"planned endpoint misses goal");
      moveit_msgs::msg::RobotTrajectory message;trajectory->getRobotTrajectoryMsg(message);planned.trajectories.push_back(message);
      geometry_msgs::msg::PoseStamped ee;ee.header.frame_id="world";
      ee.pose=pose(adapted->getCurrentState().getGlobalLinkTransform("end_effector_link"));planned.executor_targets.push_back(ee);
    }
    planned.success=true;planned.detail="offline only; no execution";captured.response(planned);
    std::ofstream report(node->get_parameter("probe_output").as_string());
    report << "{\"status\":\"OFFLINE_TCP_PASS\",\"robot_tasks\":0,\"sampler_trials\":20,\"legacy_valid_samples\":"<<before.accepted
      <<",\"tcp_valid_samples\":"<<after.accepted<<",\"tcp_max_error_m\":"<<std::setprecision(17)<<after.max_error
      <<",\"blocked_valid_samples\":"<<rejected.accepted<<",\"collision_checks\":"<<rejected.collision_checks
      <<",\"sampler_seeds\":["<<before.seed<<','<<after.seed<<','<<rejected.seed<<']'
      <<",\"planned_stages\":3,\"bad_evidence_path_rejected\":true,\"default_admission\":\"NO_GO\"}\n";
    exit=0;
  } catch(const std::exception& e) { std::cerr << "OFFLINE_TCP_FAIL: " <<e.what()<<std::endl; }
  rclcpp::shutdown();return exit;
}
