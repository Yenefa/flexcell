// Read-only snapshots of Gazebo's contact components; never creates a sensor,
// moves a body, or treats silence on a contact topic as an empty contact set.
#include <google/protobuf/util/json_util.h>
#include <gz/plugin/Register.hh>
#include <gz/sim/System.hh>
#include <gz/sim/Util.hh>
#include <gz/sim/components/Collision.hh>
#include <gz/sim/components/ContactSensorData.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace flexcell {
class ContactTrace final : public gz::sim::System, public gz::sim::ISystemConfigure,
                           public gz::sim::ISystemPostUpdate {
  struct Watch { std::string model, link, collision; };
  std::vector<Watch> watches;
  gz::sim::Entity world{gz::sim::kNullEntity};
  std::ofstream log;
  uint64_t samples{0};
  static void Number(std::ostream& out, double value) {
    if (std::isfinite(value)) out << value;
    else out << std::quoted(std::isnan(value) ? "NaN" : value > 0 ? "Infinity" : "-Infinity");
  }
  static bool SafeName(const std::string& name) {
    return !name.empty() && std::all_of(name.begin(), name.end(), [](unsigned char c) {
      return std::isalnum(c) || c == '_' || c == '-' || c == '.';
    });
  }
 public:
  void Configure(const gz::sim::Entity& entity, const std::shared_ptr<const sdf::Element>& sdf,
                 gz::sim::EntityComponentManager&, gz::sim::EventManager&) override {
    world = entity;
    std::set<std::string> names;
    const auto config = sdf->Clone();
    if (config->HasElement("watch")) {
      auto item = config->GetElement("watch");
      for (; item; item = item->GetNextElement("watch")) {
        Watch watch{item->Get<std::string>("model"), item->Get<std::string>("link"),
                    item->Get<std::string>("collision")};
        if (!SafeName(watch.model) || !SafeName(watch.link) || !SafeName(watch.collision) ||
            !names.insert(watch.model).second) throw std::runtime_error("invalid contact watch");
        watches.push_back(watch);
      }
    }
    if (watches.empty() || watches.size() > 16) throw std::runtime_error("contact watches required");
    const char *path = std::getenv("FLEXCELL_CONTACT_STEP_LOG");
    if (!path || !*path || std::filesystem::exists(path))
      throw std::runtime_error("new contact step log path required");
    log.open(path, std::ios::out);
    if (!log) throw std::runtime_error("cannot open contact step log");
    log << std::setprecision(17);
  }
  void PostUpdate(const gz::sim::UpdateInfo& info, const gz::sim::EntityComponentManager& ecm) override {
    if (info.paused) return;
    using namespace gz::sim;
    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(info.simTime).count();
    const auto dt = std::chrono::duration_cast<std::chrono::nanoseconds>(info.dt).count();
    const auto mono = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
    log << "{\"schema_version\":1,\"source\":\"ECM_POST_PHYSICS\",\"sim_ns\":" << ns
        << ",\"step_ns\":" << dt << ",\"monotonic_ns\":" << mono << ",\"targets\":{";
    bool first = true;
    for (const auto& watch : watches) {
      if (!first) log << ',';
      first = false;
      const auto model = ecm.EntityByComponents(components::Model(), components::Name(watch.model),
                                                components::ParentEntity(world));
      const auto link = model == kNullEntity ? kNullEntity : ecm.EntityByComponents(
          components::Link(), components::Name(watch.link), components::ParentEntity(model));
      const auto collision = link == kNullEntity ? kNullEntity : ecm.EntityByComponents(
          components::Collision(), components::Name(watch.collision), components::ParentEntity(link));
      const auto contacts = collision == kNullEntity ? nullptr :
          ecm.Component<components::ContactSensorData>(collision);
      log << std::quoted(watch.model) << ":{\"collision_entity\":";
      if (collision == kNullEntity) log << "null";
      else log << collision;
      log << ",\"pose\":";
      if (link == kNullEntity) log << "null";
      else {
        const auto pose = worldPose(link, ecm);
        const double values[]{pose.Pos().X(), pose.Pos().Y(), pose.Pos().Z(),
            pose.Rot().X(), pose.Rot().Y(), pose.Rot().Z(), pose.Rot().W()};
        log << '[';
        for (int i = 0; i < 7; ++i) { if (i) log << ','; Number(log, values[i]); }
        log << ']';
      }
      log << ",\"component_present\":" << (contacts ? "true" : "false") << ",\"contacts\":";
      if (!contacts) log << "null";
      else {
        std::string json;
        google::protobuf::util::JsonPrintOptions options;
        options.preserve_proto_field_names = true;
        const auto result = google::protobuf::util::MessageToJsonString(contacts->Data(), &json, options);
        if (!result.ok()) throw std::runtime_error("contact protobuf JSON failed: " + result.ToString());
        log << json;
      }
      log << '}';
    }
    log << "}}\n";
    if (++samples % 10 == 0) log.flush();
    if (!log) throw std::runtime_error("contact step log write failed");
  }
};
}
GZ_ADD_PLUGIN(flexcell::ContactTrace, gz::sim::System,
             flexcell::ContactTrace::ISystemConfigure, flexcell::ContactTrace::ISystemPostUpdate)
