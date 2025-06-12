cmake_minimum_required(VERSION 3.15)
project(enviro_launcher)

set(CMAKE_CXX_STANDARD 17)

add_executable(enviro_launcher launcher.cpp build.rc)
