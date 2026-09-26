# Week-2 Preparation — Architecture Reconnaissance & Design (NO CODE CHANGES)

> **Status: DESIGN ONLY.** Nothing in this document has been implemented. No runtime
> behavior, skill, Gazebo, carry backend, or FSM code was touched — the repository is
> exactly the Week-1.5 delivery baseline `7956d63` (pushed, remote-verified).
>
> Scope guard: this document prepares a future **Runtime Decision Layer**. The hierarchy
> is fixed and unchanged:
>
>     Human Goal
>         ↓
>     Runtime Decision Layer      ← designed in §2 (does not exist yet)
>         ↓
>     Task Executor               ← today: task_fsm_server.py (frozen behavior)
>         ↓
>     Skill Server
>         ↓
>     Robot
>
> Models only decide **task-level actions**. They never control joints, trajectories,
> parameters, or safety. Enforced by a deterministic gate (§2.6), not by policy goodwill.
>
> Sources cited as `file:line` (repo @ 7956d63) or `issue#1` (RFC: DecisionPolicy
> abstraction + Jev as a fast policy, Yenefa/flexcell#1, incl. its benchmark-prerequisites
> supplement comment).

---

## 0. 摘要（中文一页）

- **审计结论（§1）**：执行器/技能/验证器/证据链四层已就绪，唯一结构性缺口是"下一步做什么"的决策逻辑以代码形式硬编码在 `task_fsm_server.py` 内部——需要抽取到 DecisionPolicy 接口之后，而不是重写执行器。
- **DecisionPolicy 设计（§2）**：`decide(WorldState, TaskGoal, Constraints, TaskHistory) → Decision(action, target, confidence, reason_code, evidence_ref)`；四种实现 FSMPolicy / JevPolicy / LLMPolicy / HybridRouter 共用同一输入字节与同一验证门；FSMPolicy 必须能逐字复现现行 FSM 行为（回归保证）。
- **WorldState v2 提案（§3）**：v1.5 字段一字不动，纯增量加 `TaskContext`（任务进度/重试计数/剩余约束/可用动作菜单/注入标志）；所有策略拿**同一份**规范化序列化字节；`notes[]` 不进策略视野。
- **基准设计（§4）**：A/B/C/D 四格（FSM/LLM/Jev/Hybrid）× 7 场景族，7 项指标定义到测量点，策略输入级离线回放（issue#1 补充 C）。
- **Jev 可行性（§5）**：真实产品（TypeSafe AI，2026-09-15 发布，Choice/Noul/Score 三原语，官方称比 LLM 快 ~200×——vendor claim 已按 issue#1 打折标注）；官方云服务**未对中国大陆开放** → 建议适配层后端可替换（官方 SDK / APUS MIT 本地复现两条腿）。API 细节（确切 schema/鉴权/定价/是否输出完整分布）= 待 vendor 文档与离线 spike，标注 UNKNOWN 处不臆断。
- **待大统领决策（§6）**：v2 schema 冻结批准、LLM provider/model 选型、Jev 后端路线（官方 vs 本地复现）、Hybrid 阈值策略、扰动场景轨道归属。

---

## 1. Current architecture audit

### 1.1 Runtime plane today (component map, verified @ 7956d63)

```
w1_client.py / flexcell_admin.py            (test client / lifecycle + health gate)
        │ actions                               │
        ▼                                       ▼
  /run_demo, /run_pick_place            strict health gate (17 checks)
        │
task_fsm_server  ← TODAY'S TASK EXECUTOR: hard-coded FSM + bounded recovery
        │ /observe  /pick_object  /place_object  /verify_object
        ▼
observe_server   pick_server   place_server   verify_server   carry_server   move_to_pose_server
   │ gz stream      │ /move_to_pose    │ /move_to_pose   │ gz sample    │ gz set_pose    │ MoveIt /execute_trajectory
   │ /joint_states  │ /flexcell/carry_start(+stop)        │              │ 10Hz servo     │ IK pre-check, whitelist
   ▼                ▼                                     ▼              ▼
WorldState v1.5  ── /flexcell/world_state        (single producer: observe_server)
CarryState       ── /flexcell/carry_state        (latched, backend belief)
TaskState        ── /flexcell/task_state         (latched IDLE/BUSY)
FailureInject    ── /flexcell/inject             (scenario:once|always, benchmark input)
MoveIt 2 → ros2_control → Gazebo Harmonic 8.15 (OpenMANIPULATOR-X)
```

Config of record: `src/flexcell/flexcell_skills/config/week1.yaml` (zones, tolerances,
budgets, profiles, topics — all parameters cited below come from there unless noted).

### 1.2 Task executor (FSM) — location & behavior

**Location**: `src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py` (539 lines).

Two action servers in one node:

| Server | Purpose | Sequence |
|---|---|---|
| `run_pick_place` (Week-1) | single object pick-and-place | OBSERVE → PICK → PLACE → VERIFY; cancel honored between states; `skip_verify` option (`task_fsm_server.py:167-296`) |
| `run_demo` (Week-1.5) | canonical dual-object demo | for each leg in plan `[('A',obj_a,'zone_1'), ('B',obj_b,'zone_2')]`: OBSERVE(refresh) → PICK(+bounded recovery) → PLACE (no retry, typed abort) → VERIFY(+bounded reverify) (`task_fsm_server.py:337-520`) |

Key mechanics relevant to a DecisionPolicy layer:

- **Plan is code, not data**: `plan = [('A', self._obj_a, 'zone_1', ...), ('B', ...)]` at
  `task_fsm_server.py:392-393`.
- **Recovery policy is code**: `RECOVERABLE_PICK = frozenset({22, 23, 30})`
  (WORLD_STATE_UNAVAIL / GRASP_FAILED / MOTION_FAILED) at `task_fsm_server.py:308`;
  recovery = REOBSERVE(refresh) + one retry, `recovery_budget: 1` (`week1.yaml:109`);
  budget exhaustion → `ERR_RECOVERY_EXHAUSTED` (`task_fsm_server.py:431-437`).
- **PLACE has no retry by design** — a carried box must not be re-attempted blindly
  (`task_fsm_server.py:453` comment); failure aborts typed.
- **Mutual exclusion**: `_busy` / `_demo_busy` flags; `ERR_RESOURCE_BUSY` on overlap.
- **Deadlines**: observe/verify 30s, pick/place 90s, goal-send 15s
  (`task_fsm_server.py:218,417,465,321`); skill-level `deadline_ms` defaults 30000 in
  pick/place servers (`week1.yaml:44,64`).
- **Evidence**: per-run record to `demo_runs.jsonl` (`task_fsm_server.py:365-375`);
  per-step records with attempt + evidence_id; latched task state topic
  (`task_fsm_server.py:110-116`).

**What must be preserved when a policy layer lands**: the admission/mutex, the skill
dispatch plumbing (`_demo_call`/`_call_skill` — reusable as-is), cancellation semantics,
evidence writing, and the task-state topic. **What gets extracted**: the "which action
next" decisions (§2.5).

### 1.3 Skill interfaces (all typed, all evidence-carrying)

| Action | Goal (essentials) | Result (essentials) | Notes |
|---|---|---|---|
| `MoveToPose` | target pose, `motion_profile_id` (whitelist), `expected_world_revision`, `deadline_ms` | outcome, 13-code error taxonomy, `reached_pose` **measured from TF**, `position_error_m`, `stop_confirmed` (5-condition strict stop), `world_revision_before/after`, `evidence_id` | the Day-2 contract; "everything below the Task Policy must work without an LLM" (`.action:9`) |
| `Observe` | `refresh`, `max_age_s` | `WorldState` snapshot, `evidence_id` | single producer of canonical state |
| `PickObject` | `object_name`, profile, `expected_world_revision`, `deadline_ms` | outcome, `ERR_GRASP_FAILED=23` etc., `object_pose_before/after`, `grasp_attached`, `evidence_id` | internal rise check: `box_follow_min_m: 0.03` (`week1.yaml:40`) |
| `PlaceObject` | `object_name` (must be carried), `place_pose`, profile | outcome, `ERR_NOT_CARRIED=24` etc., `object_pose_after`, `released`, `evidence_id` | drop check `place_tolerance_m: 0.06` |
| `VerifyObject` | `object_name`, `expected_pose`, `position_tolerance_m` | `OUTCOME_VERIFIED/MISMATCH/FAILED`, `measured_pose`, `position_error_m`, `evidence_id` | MISMATCH is an honest result, not a server failure (`verify_server.py:100`) |
| `RunDemo` | `scenario_id` | run_id, `fsm_trace`, per-zone truth, duration, `evidence_id` | the executor's demo task |
| `RunPickPlace` | object + place pose | fsm_trace, `object_at_place`, `final_position_error_m`, `evidence_id` | single-object task |

The **action space a policy chooses from is already finite and typed** — exactly the
"bounded question" shape issue #1 describes (its example set: PICK_A / PICK_B /
REOBSERVE / WAIT / ABORT).

### 1.4 WorldState v1.5 implementation (current, frozen)

Producer: `observe_server.py::_snapshot()` (`observe_server.py:128-228`); schema
`flexcell_interfaces/msg/*.msg`:

- `WorldState`: `header`, `revision` (uint64), `source` (`SIMULATION_GROUND_TRUTH`),
  `robot` (RobotStateSummary), `objects` (WorldObject[]), `carry` (CarryState),
  `zones` (ZoneState[]), `notes` (string[]).
- `WorldObject`: `name`, `pose` (gz ground truth), `size`, `available`.
- `RobotStateSummary`: `joint_names/positions` (4 arm joints only — gripper filtered out,
  `observe_server.py:38,163-167`), `ee_pose` (TF world→end_effector_link, 1s timeout), `ee_frame`.
- `CarryState`: `engaged`, `object_id`, `reference_frame`, `offset` — **backend belief,
  never physical evidence** (msg header comment; the frozen Week-1.5 compromise).
- `ZoneState`: `id`, `center`, `radius` (0.06m), `occupancy` ∈ {NOT_AVAILABLE=-1, FREE=0,
  OCCUPIED=1} — derived from ground truth only (`observe_server.py:190-212`).
- **Revision gate**: bumps when any tracked object moves > `move_epsilon_m: 0.002`
  (`observe_server.py:146-150`); consumed by `expected_world_revision` on
  Pick/Place/MoveToPose goals — **stale-decision protection already exists below the
  policy layer**.
- `notes[]`: free-text diagnostics (`observe_server.py:142,177,188,215`) — human-only.

Distribution: published on `/flexcell/world_state` (depth-1) **and** returned in every
`Observe` action result (policies will consume the action result, not the topic race).

### 1.5 Logging / evidence system

- Per-server JSONL in `~/.ros/flexcell/`: `observe/pick/place/verify/carry/task_fsm/
  demo_runs/move_to_pose`. One line per request; `new_evidence()` mints
  `request_id` + `evidence_id` (`common.py`); the executor links run → steps → skill
  evidence_ids (`task_fsm_server.py:400-425,465-471,486-498`).
- Injection audit: injected attempts are marked `"injected": true` in pick.jsonl
  (observed in delivery acceptance) — benchmark episodes are distinguishable.
- Lifecycle evidence: flexcell CLI transcripts + strict health gate (17 checks incl.
  action-server presence, controller activity, model poses, carry publisher count == 1,
  task IDLE) — reproducible episode start/stop for benchmarks.

### 1.6 Verifier mechanism (measured-not-inherited doctrine)

Layered, independent of whoever decided:

1. `verify_server`: independent gz ground-truth sampling; distance vs expected;
   tolerance (default 0.05m; demo 0.06m `week1.yaml:110`); returns MISMATCH as an
   honest result (`verify_server.py:85-101`).
2. Pick's physical check: box must follow the lift ≥ `box_follow_min_m: 0.03` else
   `ERR_GRASP_FAILED` + **release for safety** (delivery-acceptance-proven: caught 3
   servo-starvation failures with zero false successes).
3. Place drop check (`place_tolerance_m: 0.06`) + settle time.
4. Reset canonical re-verification ±0.005m (flexcell_admin).
5. Lifecycle strict health gate (§1.5).

**A DecisionPolicy layer sits entirely above this doctrine and can never inherit a
success** — the property that makes policy benchmarking trustworthy.

### 1.7 Readiness assessment — "What parts are already ready for a DecisionPolicy layer?"

**Ready now (no change needed):**

| # | Asset | Why it matters for policies |
|---|---|---|
| R1 | Finite, typed, mutually-exclusive action space (7 action servers, single-task mutex) | the "bounded question" issue #1 defines is already the runtime shape |
| R2 | Canonical WorldState v1.5: single producer, revision counter, source tag, frozen schema | same-state-to-all-policies is mostly a serialization exercise (§3) |
| R3 | Full typed error taxonomy on every skill | the raw material for the deterministic safety gate and for policy features |
| R4 | Evidence chain (run_id → step evidence_id) per request | benchmark episode logging builds directly on it |
| R5 | Verifier doctrine (measured-not-inherited, 5 layers) | success ground truth independent of the decider |
| R6 | World-revision gates on Pick/Place/MoveToPose goals | stale-decision protection exists below the policy layer |
| R7 | Bounded-recovery machinery (REOBSERVE+RETRY, budget, recoverable-error classes) | its *mechanics* are reusable; only its *decision* gets extracted |
| R8 | Lifecycle + strict health gates | reproducible episode boundaries for the benchmark |
| R9 | Failure-injection channel (`/flexcell/inject`, scenario:once/always) | seeded fault schedules for the benchmark, already audit-logged |

**Gaps (designed in §2/§3, not yet implemented):**

| # | Gap | Consequence today |
|---|---|---|
| G1 | Sequencing/recovery/budgets hard-coded in `task_fsm_server.py` | no policy seam; "what next" is not a callable |
| G2 | No `TaskGoal` / `Constraints` representation | goal = hard-coded plan + server params |
| G3 | No `Decision` object or policy-facing action enum | nothing for a policy to return |
| G4 | WorldState lacks task context: previous action/result, retry counters, remaining plan, deadline, available-action menu, injection-active flag (issue#1 supplement A list) | policies would have to mine JSONL logs — forbidden by design |
| G5 | Zone definitions duplicated (observe_server params vs task_fsm_server params, same values) | single-source risk to fix in v2 |
| G6 | Gripper position not in RobotStateSummary (4 arm joints only) | policies can't see grasp aperture |
| G7 | No benchmark harness / policy-input replay store | supplement C unmet until built |

---

## 2. DecisionPolicy abstraction (proposal — design only)

### 2.1 Place in the hierarchy

Matches the fixed hierarchy and issue #1's three tiers:

```
Human Goal
    ↓
Runtime Decision Layer                     ← §2 (Fast Policy + optional Slow Reasoner)
    ↓  Decision objects only
Task Executor  (task_fsm_server, generalized loop; validation + dispatch + evidence)
    ↓  typed skill actions
Skill Server → Robot   (safety envelope, MoveIt, ros2_control — deterministic, untouched)
```

- **Fast Policy** (FSM / Jev / Hybrid): next task-level action, retry/reobserve/abort,
  escalation trigger — `decide()` per step.
- **Slow Reasoner** (LLM): goal understanding, novel constraints, exceptions, takeover
  on low confidence. In the primary benchmark it appears as `LLMPolicy` (per-step) and
  inside `HybridRouter` (escalation target).
- **Deterministic Executor**: parameter validation, safety envelope, revision gates,
  MoveIt, collision, trajectories, timeouts, retry-budget *accounting*. Never a model.

### 2.2 Types (python sketch; ROS msg equivalents proposed in §3)

```python
class ActionKind(enum.Enum):
    OBSERVE  = "observe"    # refresh ground truth (= issue#1's REOBSERVE)
    PICK     = "pick"
    PLACE    = "place"
    VERIFY   = "verify"
    WAIT     = "wait"
    ABORT    = "abort"

@dataclass(frozen=True)
class TaskGoal:
    goal_id: str
    kind: str                      # "dual_object_demo" | "pick_place" (v1)
    assignments: tuple[Assignment, ...]   # (object_id, zone_id) — from config, not from policy
    deadline_s: float

@dataclass(frozen=True)
class Constraints:
    allowed_actions: frozenset[ActionKind]   # executor-owned menu
    recovery_budget: int                     # accounting stays executor-side
    verify_tolerance_m: float
    motion_profile_id: str                   # whitelist key only; raw scaling forbidden
    max_world_age_s: float                   # freshness gate input

@dataclass(frozen=True)
class Decision:
    action: ActionKind
    target: TargetSpec | None      # (object_id, zone_id) for PICK/PLACE; None otherwise
    confidence: float              # [0,1]; semantics per policy (§2.3 rule 5)
    reason_code: str               # token, e.g. PLAN_NEXT_LEG / RECOVERABLE_RETRY / BUDGET_EXHAUSTED
    explanation: str | None        # optional human text; WRITE-ONLY (logged, never parsed)
    evidence_ref: EvidenceRef      # (policy_name, policy_version, world_revision,
                                   #  observe_evidence_id, decide_latency_ms)

class DecisionPolicy(Protocol):
    name: str
    version: str
    def decide(self, world: WorldState, goal: TaskGoal,
               constraints: Constraints, history: TaskHistory) -> Decision: ...
    # optional for probabilistic policies (Jev; LLM if it yields scores):
    def decide_distribution(self, ...) -> dict[ActionKind, float]: ...
```

`TaskHistory` = the executor-maintained digest of prior decisions + typed results
(per-leg outcome/error_code, retry counts, elapsed) — the §3 `TaskContext` source;
policies see it ONLY through the canonical structure, never by reading logs.

### 2.3 Policy contract (hard rules for every implementation)

1. **Purity**: `decide()` performs no IO and no robot/skill calls. Same inputs (+seed)
   → same output; LLM exempted from strict determinism but must record
   model/version/temperature/seed per call.
2. **Bounded vocabulary**: a policy may only emit actions from
   `Constraints.allowed_actions` and targets that exist in `WorldState`/`TaskGoal`.
   Anything else is an **invalid decision** — rejected by the gate (§2.6), counted as
   the `invalid actions` metric, never executed.
3. **No safety authority**: policies never see or modify trajectories, joint values,
   motion scaling, tolerances, or budgets. Issue #1 hard rule, restated as law:
   a policy may answer "which task action next?", never "is this physically safe?".
4. **Timeout + fallback**: executor enforces `decide_timeout_ms` per call
   (config; FSM ≈ 0; fast-path target ≤ 500 ms; LLM escalation ≤ 5 s — budgets chosen
   from skill durations (pick ≈ 7 s), not from vendor claims). On timeout/exception/
   unparseable output the executor falls back to `FSMPolicy` for that step and records
   `policy_failure`. The system degrades to today's behavior, never to silence.
5. **Confidence semantics**: [0,1]. FSMPolicy emits 1.0 on its deterministic plan steps
   and marks recovery branches distinctly (it is not pretending to be a probability).
   Jev/LLM/Hybrid confidences are **routing signals until calibrated** (issue#1
   supplement B) — they may gate escalation but are never described as safety
   guarantees.
6. **Byte-identical input**: all policies receive the same canonical serialization
   (§3.4). `notes[]` is excluded. No policy gets extra context. (supplement A)
7. **Explanation is write-only**: logged for humans/debugging; the executor and other
   policies must not parse it.

### 2.4 The four implementations (design notes, not code)

| Policy | Input handling | Decision rule | Confidence source | Failure mode |
|---|---|---|---|---|
| `FSMPolicy` | canonical state + history | encodes today's logic as pure rules: leg plan → next action; error ∈ recoverable set ∧ budget remains → OBSERVE+retry; PLACE failure → ABORT; budget exhausted → ABORT | 1.0 on plan steps; recovery branches flagged via reason_code | none (reference implementation) |
| `JevPolicy` | canonical serialization rendered into Jev `state` + a `Choice` question over the allowed-action menu (§5) | top choice from Jev response; map to ActionKind | Jev-reported probability (routing signal until calibrated) | parse/OOV/timeout → typed `policy_failure` → FSM fallback |
| `LLMPolicy` | **identical** canonical JSON embedded verbatim in a fixed prompt template + action menu + output JSON-schema (structured output enforced) | model's single choice | model self-reported confidence (parsed from structured output; calibration expected to be poor — measured, not assumed) | unparseable/timeout → FSM fallback; all calls logged with tokens |
| `HybridRouter` | receives both backends' views | Jev first: if `p_max ≥ τ_high` → pass through; if `p_max < τ_low` or gate-invalid → escalate to LLM; LLM choice gate-checked too; both fail → FSM fallback | Jev p_max; escalation counters recorded | inherits backends' fallbacks; escalation rate is a first-class metric |

`τ_high/τ_low` start as configuration and are later tuned **only** from the calibration
phase (§4 metric 7) — never hand-tuned to make the hybrid look good.

### 2.5 Executor integration point (how `task_fsm_server` evolves — future work, not now)

Preserve: admission/mutex, `_demo_call`/`_call_skill` plumbing, cancellation, evidence,
task-state topic, per-step logging.

Generalize the demo loop into:

```
ctx = TaskContext(goal, constraints, history)
while not ctx.done:
    world    = observe(refresh=ctx.needs_fresh_world)     # existing skill
    decision = policy.decide(world, ctx.goal, ctx.constraints, ctx.history)
    verdict  = gate.check(decision, world, ctx)           # §2.6, deterministic
    if not verdict.ok:  ctx.record_invalid(decision, verdict); continue_or_abort()
    result   = dispatch(decision)                         # existing plumbing, per ActionKind
    ctx.record(decision, result)                          # history + evidence + budget accounting
```

`FSMPolicy` must reproduce current traces **shape-for-shape** (fsm_trace strings, step
records, error codes) — that is the regression bar for the whole refactor. A
`decision_policy: fsm|jev|llm|hybrid` parameter defaults to `fsm`, so flipping to
benchmark modes is the only behavioral delta.

### 2.6 Safety gate (deterministic validator)

Checks before dispatch, all hard-coded:

- `decision.action ∈ Constraints.allowed_actions`;
- target object exists ∧ (PICK ⇒ object available ∧ not currently carried);
  (PLACE ⇒ that object is currently carried per WorldState.carry **and** an
  independent gz check — backend belief is not trusted for dispatch);
- world freshness: `now - world.header.stamp ≤ Constraints.max_world_age_s`
  (fresh OBSERVE forced otherwise);
- `expected_world_revision` stamped from the observed revision (existing gate);
- no field of any skill goal may originate from policy `explanation` or any free text.

Rejections are typed (`ERR_INVALID_DECISION` proposal), logged with the full decision
object, and counted. This implements issue #1's acceptance item: *"a Jev proposal
violating a hard constraint is rejected deterministically"*.

---

## 3. Canonical WorldState proposal (v2 — additive freeze candidate)

### 3.1 Audit of v1.5 (exact fields, verbatim from msg definitions)

| Field | Type | Producer logic | Policy-relevant? |
|---|---|---|---|
| `header` | stamp + frame_id(world) | now() per snapshot | freshness gate |
| `revision` | uint64 | bumps on tracked-object move > 0.002m | stale-decision protection |
| `source` | string | constant `SIMULATION_GROUND_TRUTH` | mixing guard |
| `robot` | RobotStateSummary: joint_names[4]/positions, ee_pose (TF), ee_frame | /joint_states + TF (1s timeout) | yes (grasp approach) |
| `objects` | WorldObject[]: name, pose(gt), size, available | gz stream per tracked object | yes (core) |
| `carry` | CarryState: engaged, object_id, reference_frame, offset | latched backend topic | **belief only** — dispatch must re-verify physically |
| `zones` | ZoneState[]: id, center, radius, occupancy {NA/FREE/OCCUPIED} | derived from gt | yes (task progress) |
| `notes` | string[] | free-text diagnostics | **NO — excluded from policy view** |

### 3.2 Missing fields / fields hidden in notes, logs and config

Issue #1 supplement A requires policies to see, without log mining:

| Required | Where it lives today | Verdict |
|---|---|---|
| scene_revision / observation timestamp | `revision` / `header.stamp` | present ✓ |
| object IDs / classes / poses | objects (names only, no class) | class missing → add |
| zone occupancy | zones | present ✓ |
| current task status | `/flexcell/task_state` latched topic | **outside WorldState** → add |
| previous action / result | `task_fsm.jsonl` / `demo_runs.jsonl` | **hidden in logs** → add |
| retry counters | `demo_runs.jsonl` steps | **hidden in logs** → add |
| remaining task / time constraints | executor params + action request | **not represented** → add |
| available skills / actions | implicit (server presence) | **not represented** → add menu |
| injected fault state | `/flexcell/inject` (write-only); `"injected": true` in pick.jsonl | **not visible to policies** → add flag |
| gripper state | `/joint_states` has it; `ARM_JOINTS` filter drops it (`observe_server.py:38`) | add to RobotStateSummary |
| object→zone assignment progress | only in demo runs | add (plan/completed legs) |
| per-object observation freshness | only snapshot-level stamp | add per-object age |

Also found: zone geometry is **duplicated** in `observe_server` params
(`week1.yaml:13-21`) and `task_fsm_server` params (`week1.yaml:103-108`) — same values,
two sources (G5). v2 should declare observe_server the single source and have the
executor consume zones from WorldState instead of its own params.

### 3.3 Proposed v2 schema (additive; v1.5 fields unchanged)

```text
WorldState  (schema_version: "2.0")
  std_msgs/Header header
  uint64 revision
  string source
  string schema_version                    # NEW
  RobotStateSummary robot                  # + float64 gripper_position (NEW)
  WorldObject[] objects                    # + string klass (NEW, default "box")
                                           # + float64 pose_age_s (NEW: age of this object's sample)
  CarryState carry                         # unchanged (backend belief, labeled as such)
  ZoneState[] zones                        # + string occupied_by (NEW: object name or "")
  TaskContext task                         # NEW (assembled by the EXECUTOR, see below)
  string[] notes                           # unchanged; excluded from policy serialization

TaskContext (NEW msg, executor-owned truth)
  string task_state                        # IDLE / RUNNING / ...
  string goal_id
  Assignment[] plan_remaining              # (object_id, zone_id)
  Assignment[] plan_completed              # + per-leg outcome/error_code summary
  uint32[] retry_counts                    # per remaining leg
  uint32 recovery_budget_remaining
  string last_action                       # ActionKind of the previous decision
  uint8  last_outcome                      # typed outcome of the previous action
  uint16 last_error_code
  uint64 last_action_world_revision
  string[] available_actions               # executor menu == Constraints.allowed_actions
  float64 deadline_remaining_s
  bool   fault_injection_active            # benchmark honesty: policies know injection
                                           # EXISTS; never the schedule
```

**Assembly rule**: `world`-part stays single-producer (observe_server). `task`-part is
assembled by the executor at `decide()` time (it owns that truth). The policy-facing
snapshot is the union — one assembly point, byte-identical for all policies. Zone
geometry becomes single-source (observe_server) with the executor consuming zones from
WorldState.

### 3.4 Serialization contract (the fairness core)

- Canonical JSON: fixed field order, sorted map keys, explicit nulls, rounded floats
  (documented precision), UTF-8, schema_version envelope:
  `{"schema_version":"2.0","world_state":{...},"task_context":{...}}`.
- `notes[]` and any free text are **stripped** from the policy-facing bytes.
- The **same serialized bytes** are: parsed back by `FSMPolicy`, passed as Jev `state`,
  and embedded verbatim in the LLM prompt. No policy receives one extra byte of
  context. (supplement A: "the LLM must not receive extra natural-language context".)
- An unstructured-context track (operator notes, anomaly prose) may exist **later as a
  separate benchmark**, never mixed into the primary one.
- Freeze procedure: this §3 is the freeze-candidate RFC; ratification (chief review)
  precedes any implementation, per supplement A.

---

## 4. Benchmark design (definition only — no experiments run)

### 4.1 Cells

| Cell | Policy | Notes |
|---|---|---|
| A | `FSMPolicy` | deterministic baseline; must be ≥ every other cell on task success before anything enters the critical path (issue#1 + HANDOFF) |
| B | `LLMPolicy` | per-step LLM decisions, structured output |
| C | `JevPolicy` | fast decision model behind the same interface |
| D | `HybridRouter` | Jev fast-path + LLM escalation |

Same executor, same skills, same verifier, same WorldState bytes, same budgets. The
only variable is the policy.

### 4.2 Scenario suite (seeded; reuses `/flexcell/inject`)

| ID | Scenario | Injection | Runs/cell (min → preferred) |
|---|---|---|---|
| S1 | canonical happy demo (`week1_demo_v1`) | none | 20 → 50 |
| S2 | injected failure, PICK_A first attempt | `once` | 20 → 50 |
| S3 | injected failure, PICK_B first attempt | `once` | 20 → 50 |
| S4 | unreachable place target (typed IK fail path) | none | 10 → 30 |
| S5 | retry-exhaustion (`scenario:always`) | `always` | 10 → 30 |
| S6 | cold-start episodes (lifecycle start→demo→stop per episode) | none | 5 → 10 |
| S7 | off-canonical initial placement (adaptation probe) | none (perturbed world) | stretch — needs chief decision (§6) |

Episode = one full lifecycle-scoped demo run with recorded inputs/outputs (§4.3
replay record). Environment snapshot (load, uptime — the delivery-acceptance lesson)
is recorded per episode; runs are interleaved across cells to avoid time-of-day drift.

### 4.3 Metrics (definitions + measurement points)

| # | Metric | Definition / measurement point |
|---|---|---|
| 1 | task success rate | `RunDemo.outcome == SUCCEEDED` per episode; Wilson 95% CI; n≥20 gives ±~19pp, n≥50 ±~11pp — prefer 50 |
| 2 | recovery success | injected episodes recovered (final SUCCEEDED) / injected |
| 3 | decision latency | wall time around `decide()` only; report p50/p95/p99 + distribution; dispatch/executor time measured separately |
| 4 | LLM invocation count | per episode and per task-leg; tokens (in/out) logged per call |
| 5 | cost | tokens × pinned price table (provider/model/date); Jev cost if vendor-priced (UNKNOWN today) |
| 6 | invalid actions | safety-gate (§2.6) rejections per 1000 decisions, with typed reasons |
| 7 | confidence calibration | reliability diagram + ECE (10 bins); Brier score where full distributions exist (C; D's fast path); risk-coverage curve on threshold sweep; wrong-autonomous-decision rate as threshold rises (supplement B) |

### 4.4 Replay & record (supplement C)

Per episode, persist: `scenario_id`, `seed`, `initial_world_state` (canonical bytes),
`failure_injection_schedule`, `policy_input` (exact bytes), `policy_output`,
`selected_action`, `executor_result`, `verifier_result`, `final_state`,
`timestamps/latencies`. Gazebo physics is NOT assumed bit-replayable; instead the
**policy-input level replay** runs all policies offline on the exact recorded state
sequences — this also lets Jev/LLM be evaluated without touching the robot.

### 4.5 Pass / fail gates

1. A (FSM) ≥ B, C, D on task success rate (statistically, CI-overlap rule) → else no
   policy enters the critical path (HANDOFF: "deterministic baseline ≥ LLM baseline
   before Jev").
2. Safety-gate demo: a planted out-of-contract proposal (unit test) is deterministically
   rejected and counted.
3. Calibration validated (metric 7) **before** any threshold-routing claim for C/D.
4. Every cell must complete on FSM-fallback alone when its backend fails — degradation,
   not deadlock.

### 4.6 Reporting

One table per cell × scenario (success CI, latency p50/p95, invocations, cost, invalid
rate, calibration summary), plus per-episode raw records; all numbers regenerate from
the replay store — no hand-written PASS lines.

---

## 5. Jev feasibility checklist

Research date: 2026-09-26/27. In-repo source: issue #1 (body + supplement comment).
Web sources: Xinhua (2026-09-21), CNR (2026-09-20), Aliyun developer community
("Jev in the Wild", 2026-09-26; Jev primer, 2026-09-26) — retrieved via 豆包 search.

| Question | Answer | Status | Basis / gap |
|---|---|---|---|
| What is Jev's actual interface? | **Choice / Noul / Score** primitives ("选哪个 / 是不是 / 打几分"): Choice = select one from a candidate set with per-option criteria, returning the choice **with probability/confidence**; Noul = yes/no; Score = numeric. Official Python/JS SDK (`typesafe-sdk`), call shape `client.system_one(state=..., questions={...})`. | **CONFIRMED (shape)** | Multiple independent secondary sources; exact request schema, auth, quotas, pricing = **UNKNOWN** until vendor doc / spike |
| Can it consume structured state? | Designed for it: `state` payload + typed questions; the APUS open-source reproduction shows numbered candidate-action sets derived from structured page state (browser-use domain). FlexCell mapping: canonical WorldState JSON → `state`; allowed-action menu → Choice criteria. | **YES (design-intent, evidenced)** | No published robotics input schema; token/size limits UNKNOWN |
| Can it output confidence? | Yes — probability/confidence returned with the typed answer. Whether the **full distribution** over candidates (issue #1's assumed shape) or only top-1+confidence is returned = **UNKNOWN** (spike will answer; affects Brier vs ECE choice in §4.3-7) | **PARTIAL** | supplement B forbids assuming calibration; measured ECE/risk-coverage required before routing claims |
| What latency constraints exist? | Vendor claim: up to ~200× faster than frontier LLMs on classification-style tasks (and ~1/400 cost) — **vendor-run numbers, treat with issue #1's caveat**. APUS local reproduction (single-token logits, no autoregressive decode; local Qwen3.5-9B) runs real-time on a laptop. FlexCell-side budget: decisions are task-level, skills take seconds (pick ≈7s, deadlines 30-90s), so a **≤500ms fast-path decision budget adds no measurable task latency**; LLM escalation ≤5s. | **ADEQUATE BUDGET (by our side); measured p95 UNKNOWN** | no independent benchmark; spike on replay store will measure |
| Is remote-only usage acceptable for FlexCell? | **Cloud API: impractical today** — TypeSafe service is not open to mainland China (CNR), and our WSL network blackholes even github.com. **Local/self-hosted: viable** — APUS MIT reproduction (cross-platform, GPU-optional, offline) demonstrates the Jev paradigm on local models; and architecturally remote-only *would* be acceptable (task-level, not control-rate) if availability handling + FSM fallback + evidence logging are in place. | **REMOTE = NO (today, this network); LOCAL BACKEND = YES** | backend choice is a chief decision (§6); JevPolicy adapter must be backend-agnostic either way |

Resolution path (when implementation is authorized): ① obtain vendor doc + trial key or
stand up the APUS local reproduction; ② offline spike against the §4 replay store
(no robot): schema fit, distribution-vs-top1, latency p95, cost, calibration;
③ only then on-robot cells C/D.

Explicitly UNKNOWN (not assumed): vendor pricing; exact input size limits; distribution
completeness; official-API SLA; whether the vendor ever opens mainland access.

---

## 6. Open questions

### For the chief (decisions needed before implementation)

1. **WorldState v2 freeze** — ratify §3.3 (additive schema + TaskContext + single-source
   zones) as the freeze RFC required by supplement A?
2. **FSMPolicy parity bar** — confirm: FSMPolicy must reproduce current traces
   shape-for-shape (my recommendation: yes; it is the regression guarantee).
3. **LLM provider/model for cell B** — pin provider, model, version, price snapshot
   (DeepSeek via opencode/zen gateway was the earlier working assumption — confirm).
4. **Jev backend route** — official API (not accessible from mainland today) vs
   APUS-style local reproduction vs "defer cells C/D until access resolves".
5. **Hybrid thresholds** — fixed config first, auto-tuned later from calibration
   (recommended), or skip Hybrid until C and B individually clear a minimum bar?
6. **S7 perturbation track** — include off-canonical placements in the primary
   benchmark (this is where non-FSM policies could actually differentiate) or keep
   primary pristine and make it a separate track?

### Technical unknowns

7. Choice-distribution completeness (affects metric 7's Brier vs ECE choice).
8. Whether gz physics noise creates state-sequence divergence large enough to matter
   for offline policy replay (mitigated by policy-input-level replay, supplement C).
9. Gripper-position surfacing cost (trivial, but touches frozen RobotStateSummary —
   v2 additive change).
10. Cosmetic: `_publish_task_state` logs a startup line on every state publish
    (`task_fsm_server.py:132`) — harmless; fold into any future executor touch-up,
    not worth a dedicated change under the freeze.

---

## 7. 三等建议 — on the "Confidence-gated Hybrid Runtime Agent" direction

**乐观**：这是 Jev 类模型几乎 ideal 的落地形状——动作空间小且强类型、状态已经是规范化结构、
成功判定有独立验证器、故障注入与证据链现成。"快慢分工"（Jev 高频小决策 + LLM 低频升级 +
确定性执行）与现有架构的接缝最小，且 Hybrid 的失败模式（回退 FSM）不会比今天更差。

**中立**：价值成立与否取决于两个尚未证明的前提——(a) Jev 的置信度在我们的状态分布上
可校准（supplement B 的核心问题）；(b) 存在 FSM 真的会输的场景。S1-S5 里 FSM 大概率
全胜（它就是为这些场景写的）；真正的分水岭在 S7 类扰动与新颖约束，而这部分尚未建。
基准很可能会得出"当前任务集上 FSM 已足够"——这本身是有价值且便宜的结论，但要提前接受。

**悲观**：LLM 自报置信度的校准性在文献中一贯很差，路由阈值可能调不出来，D 格或许只是
"更贵的 B"；Jev 是 9 月 15 日刚发布的 vendor 产品，官方服务对大陆不开放，本地复现路线
依赖第三方（APUS）对黑盒范式的逆向——若 API 细节对不上，C/D 两格直接搁浅，Week-2 缩水成
A/B；另外为双物体 demo 建决策层本质是研究载体而非刚需——issue #1 自己也划了红线
（"Jev must not become core infrastructure, never safety-critical"）。若校准失败，
整个 confidence-gated 故事退化为"带额外遥测的 FSM"。

---

## 8. Acceptance criteria check (of this preparation task)

- **No runtime code changed** — ✓ repository is at delivery baseline `7956d63`; only
  this document (and its commit) were added. Skills/Gazebo/carry/FSM untouched.
- **No existing demo behavior changed** — ✓ nothing executable was modified; the
  frozen Week-1.5 demo remains the att3-verified behavior.
- **Clear enough that implementation can start afterwards** — ✓ §2 defines types,
  contract, four implementations, executor seam and the safety gate; §3 is a
  ratifiable freeze candidate; §4 defines cells/scenarios/metrics/replay; §5 marks
  every UNKNOWN explicitly with a resolution path; §6 lists the decisions the chief
  must make first.

**Stop here — awaiting review. No implementation follows until authorized.**
