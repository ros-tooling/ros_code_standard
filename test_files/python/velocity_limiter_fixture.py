# Copyright 2026 Polymath Robotics, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Velocity limiting helpers in the ROS 2 Python style, used as a passing fixture."""

MAX_LINEAR_VELOCITY = 1.5
MAX_ANGULAR_VELOCITY = 2.0


def clamp(value: float, low: float, high: float) -> float:
    """Return the value limited to the inclusive range from low to high."""
    return max(low, min(high, value))


def limit_twist(linear: float, angular: float) -> tuple[float, float]:
    """
    Clamp a velocity command to the fixture limits.

    :param linear: forward velocity in metres per second.
    :param angular: yaw rate in radians per second.
    :return: the clamped linear and angular pair.
    """
    return (
        clamp(linear, -MAX_LINEAR_VELOCITY, MAX_LINEAR_VELOCITY),
        clamp(angular, -MAX_ANGULAR_VELOCITY, MAX_ANGULAR_VELOCITY),
    )
