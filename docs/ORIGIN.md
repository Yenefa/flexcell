# Origin & Motivation

> Living document. This records *why FlexCell exists* and the framing we converged on.
> It is expected to be revised as the project matures.

---

## 1. The spark: agent-native robotics development

Isaac ROS 5.0 (released 2026-09-21) shipped **AI Agent Skills** in the open Agent Skills
format. They extend coding assistants (Claude Code, Cursor, Codex, and others) so they can
understand and execute Isaac ROS workflows - activating the development container, migrating
nodes to rosidl::Buffer, bringing up Mission Control, editing maps and fleets.

Isaac Sim goes further and ships its own skill packs teaching a coding agent to import robots,
configure physics, generate synthetic data, drive rendering, and operate a *running* Isaac Sim
through a Python server. NVIDIA also made pick-and-place an agent-ready skill, and
FoundationStereo fine-tuning agent-assisted.

That is the thing that started this project:

    you
     -> coding agent / harness
        -> understands robot-development intent
           -> reads ROS / Isaac docs
              -> configures the environment
                 -> writes ROS nodes
                    -> wires perception / planning / manipulation
                       -> debugs
                          -> it runs

**A robot development environment becoming an agent-operable environment.** That is real,
it exists today, and it is what we were originally drawn to.

---

## 2. The misframing we had to correct

Two different things were being conflated:

    1. Agent DEVELOPS robots      - the agent writes, configures and debugs robot software
    2. Agent CONTROLS robots      - the agent autonomously observes, decides and drives the
                                    robot at runtime

NVIDIA has genuinely built (1) at scale. (2) is **not** an off-the-shelf Isaac ROS product -
there is no general runtime agent orchestration framework shipped with it.

So the honest correction is:

- It was wrong to say "NVIDIA is not relevant to us." NVIDIA really did open an
  Agent -> ROS/robotics development channel, and it is the headline feature of Isaac ROS 5.0.
- It was equally wrong to read that as "NVIDIA already gives us a runtime robot agent."
  It does not.

---

## 3. The two planes

Once (1) and (2) are separated, the architecture stops being contradictory and becomes a
complete system with two halves:

    ================== DEVELOPMENT PLANE ==================

        you
         -> Coding Agent / Harness
            -> NVIDIA Agent Skills
               -> ROS code | Simulation | Perception
                  -> FlexCell code

    ==================== RUNTIME PLANE ====================

        Human Intent
         -> Runtime Agent
            -> Skill Registry
               -> Skill Server
                  -> Deterministic Executor
                     -> MoveIt
                        -> ROS 2
                           -> Robot
                              -> Observe -> Verify -> Replan

NVIDIA's contribution sits in the **Development Plane**.
FlexCell's research question sits in the **Runtime Plane**.

---

## 4. The question FlexCell actually asks

> Coding agents now understand robot development through skills.
> Can the robot's **runtime** adopt the same skill-oriented paradigm -
> a Runtime Agent operating on top of a deterministic execution layer?

That is the natural next step, and it is what this repository is for.

Correspondingly, NVIDIA's role in the project narrative is:

> **NVIDIA Agent Skills make the *development* agent able to operate the robot software stack.
> FlexCell explores how the same skill-oriented paradigm extends to the robot's *runtime*.**

Not "we wanted to use NVIDIA and ended up not using it."

---

## 5. Why the Jazzy baseline was still the right Day 1

Isaac ROS 5.0 requires **ROS 2 Lyrical**, **CUDA 13.2+** and **driver 595+**. Our baseline is
**Jazzy + Gazebo Harmonic + MoveIt**.

The RTX 4060 Laptop (8 GB) is *not* the blocker - it meets Isaac ROS's stated x86 floor
(Ampere or newer, 8 GB VRAM or more). The blocker is the **ecosystem version combination**.

So the reasoning was never "NVIDIA is useless". It was:

> Do not eat ROS Lyrical + CUDA 13.2 + Isaac ROS migration on day one
> just to use brand-new Agent Skills.

Those are very different statements, and only the second one is true.

---

## 6. Revised roadmap

    Day 1     traditional ROS baseline                        [done]
              Gazebo Harmonic + MoveIt 2 Plan & Execute
                |
    Week 1    FlexCell deterministic skills
              observe / pick / place / verify + FSM
                |
              in parallel: standalone NVIDIA Development Agent sandbox
              load NVIDIA Agent Skills into our coding agent and test
              whether it can complete a concrete ROS / Isaac dev task
                |
    Week 2+   DecisionPolicy abstraction (FSM / Jev / LLM)    [issue #1]

The NVIDIA sandbox is deliberately **separate**: Isaac ROS 5.0 cannot share the Jazzy
environment, so it belongs in its own Docker-isolated container, never in this workspace.

---

## 7. A concrete experiment this suggests

    Coding Agent                          vs   Coding Agent + NVIDIA Agent Skills

on a well-scoped robot-development task (e.g. "configure / modify / validate this Isaac ROS
node"), measuring:

- task success rate
- terminal command count
- number of human interventions
- debug iterations
- time to completion

This is directly comparable to the Runtime-Plane experiment in issue #1 - the same
skill-abstraction question, asked one layer up.

---

## 8. Status

- This document is a **living record**; revise freely.
- Related: issue #1 (DecisionPolicy abstraction + Jev as a fast policy).
- Day 1 result: see DAY1_REPORT.md.

