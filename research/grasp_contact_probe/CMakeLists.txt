cmake_minimum_required(VERSION 3.16)
# Standalone build for the grasp contact probe R&D line.
# Deliberately NOT an ament package: this line must not touch the mainline build.
# Build: source /opt/ros/jazzy/setup.bash && cmake -S . -B build && cmake --build build -j
project(flexcell_grasp_probe CXX)

find_package(gz-sim8 REQUIRED)
find_package(gz-plugin2 REQUIRED COMPONENTS register)
find_package(gz-transport13 REQUIRED)

add_library(flexcell_grasp_probe SHARED src/GraspContactProbe.cc)
target_compile_features(flexcell_grasp_probe PRIVATE cxx_std_17)
target_compile_options(flexcell_grasp_probe PRIVATE -Wall -Wextra -Wpedantic)
target_link_libraries(flexcell_grasp_probe PRIVATE gz-sim8::gz-sim8 gz-plugin2::register
                      gz-transport13::gz-transport13)

install(TARGETS flexcell_grasp_probe LIBRARY DESTINATION lib)
