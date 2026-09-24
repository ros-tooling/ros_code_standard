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


"""
A node-like class in the ROS 2 Python style, used as a passing fixture.

It exercises docstrings, type annotations, dataclasses, and import ordering, so
that flake8, pep257, pycodestyle, pyflakes, and mypy all have something to say
yes to with their default settings.
"""

from dataclasses import dataclass, field
import math


@dataclass
class Pose2D:
    """A planar pose, in metres and radians."""

    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0

    def distance_to(self, other: 'Pose2D') -> float:
        """
        Return the straight line distance to another pose.

        :param other: the pose to measure against.
        :return: the distance in metres.
        """
        return math.hypot(other.x - self.x, other.y - self.y)


@dataclass
class WaypointFollower:
    """Tracks a list of waypoints and reports which one is current."""

    waypoints: list[Pose2D] = field(default_factory=list)
    tolerance: float = 0.25
    _index: int = 0

    def add(self, waypoint: Pose2D) -> None:
        """Append a waypoint to the end of the list."""
        self.waypoints.append(waypoint)

    def current(self) -> Pose2D | None:
        """Return the waypoint being followed, or None when the list is exhausted."""
        if self._index >= len(self.waypoints):
            return None
        return self.waypoints[self._index]

    def update(self, pose: Pose2D) -> bool:
        """
        Advance to the next waypoint when the current one is within tolerance.

        :param pose: the pose the robot reports.
        :return: True when the waypoint list is exhausted.
        """
        target = self.current()
        while target is not None and pose.distance_to(target) <= self.tolerance:
            self._index += 1
            target = self.current()
        return target is None
