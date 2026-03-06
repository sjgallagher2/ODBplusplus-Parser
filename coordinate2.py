# -*- coding: utf-8 -*-
"""
Created on Fri Mar  6 15:03:46 2026

@author: SG1295
"""

from typing import List
import math
from math import sqrt,pow,fabs

pi = 3.14159265358979

# Ported from my C++ Coordinate2 class with an LLM, not verified

class Coordinate2:
    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y
        self._prec = 1e-10

    def __iadd__(self, other):
        if isinstance(other, Coordinate2):
            self.x += other.x
            self.y += other.y
        else:
            self.x += other
            self.y += other
        return self

    def __isub__(self, other):
        if isinstance(other, Coordinate2):
            self.x -= other.x
            self.y -= other.y
        else:
            self.x -= other
            self.y -= other
        return self

    def __imul__(self, f):
        self.x *= f
        self.y *= f
        return self

    def __itruediv__(self, f):
        self.x /= f
        self.y /= f
        return self

    @property
    def prec(self):
        return self._prec

    @prec.setter
    def prec(self, pin):
        if pin > 0.0:
            self._prec = pin
        else:
            raise ValueError("Coordinate precision cannot be negative or zero.")

    def magnitude(self):
        return math.sqrt(self.x**2 + self.y**2)

    def angle(self, degrees=False):
        if self.magnitude() < self._prec:
            raise ValueError("Cannot calculate angle of zero vector.")
        ang = math.atan2(self.y, self.x)
        if degrees:
            return ang * 180 / pi
        else:
            return ang

    def distance(self, c):
        return math.sqrt((self.x - c.x)**2 + (self.y - c.y)**2)

    def angle_to(self, c, degrees=False):
        if self.magnitude() < self._prec or c.magnitude() < c.prec:
            raise ValueError("Cannot calculate angle when one vector is the zero vector.")
        ang = math.atan2(self.y - c.y, self.x - c.x)
        if degrees:
            return ang * 180 / pi
        else:
            return ang

    def print(self, newline=True):
        if newline:
            print(f"({self.x}, {self.y})")
        else:
            print(f"({self.x}, {self.y})", end='')

    def __add__(self, other):
        if isinstance(other, Coordinate2):
            return Coordinate2(self.x + other.x, self.y + other.y)
        else:
            return Coordinate2(self.x + other, self.y + other)

    def __sub__(self, other):
        if isinstance(other, Coordinate2):
            return Coordinate2(self.x - other.x, self.y - other.y)
        else:
            return Coordinate2(self.x - other, self.y - other)

    def __neg__(self):
        return Coordinate2(-self.x, -self.y)

    def __mul__(self, f):
        return Coordinate2(self.x * f, self.y * f)

    def __truediv__(self, f):
        return Coordinate2(self.x / f, self.y / f)

    def __eq__(self, other):
        cprec = max(self.prec, other.prec)
        return (abs(self.x - other.x) < cprec) and (abs(self.y - other.y) < cprec)
    
    def __repr__(self):
        return f'({self.x}, {self.y}) [{self.prec}]'


def distance_from_line(P: Coordinate2, LineStart: Coordinate2, LineEnd: Coordinate2):
    dx = LineEnd.x - LineStart.x
    dy = LineEnd.y - LineStart.y
    delta = Coordinate2(dx, dy)

    ip = (P.x - LineStart.x) * delta.x + (P.y - LineStart.y) * delta.y
    proj = (0 <= ip <= pow(delta.magnitude(), 2))

    if proj:
        d = fabs(delta.y * P.x - delta.x * P.y + LineEnd.x * LineStart.y - LineEnd.y * LineStart.x) / delta.magnitude()
    else:
        d1 = P.distance(LineStart)
        d2 = P.distance(LineEnd)
        d = d1 if d1 < d2 else d2
    return d

def distance_from_rect(p: Coordinate2, anchor: Coordinate2, width, height):
    left_dist = distance_from_line(p, anchor, Coordinate2(anchor.x, anchor.y + height))
    top_dist = distance_from_line(p, Coordinate2(anchor.x, anchor.y + height), Coordinate2(anchor.x + width, anchor.y + height))
    right_dist = distance_from_line(p, Coordinate2(anchor.x + width, anchor.y + height), Coordinate2(anchor.x + width, anchor.y))
    bottom_dist = distance_from_line(p, Coordinate2(anchor.x, anchor.y), Coordinate2(anchor.x, anchor.y))
    return min(left_dist, top_dist, right_dist, bottom_dist)

def distance_from_circle(p: Coordinate2, center: Coordinate2, radius):
    dist = p.distance(center)
    return radius - dist

def distance_from_arc(p: Coordinate2, center: Coordinate2, radius, start_angle_d, end_angle_d):
    distance = 0
    if start_angle_d != end_angle_d:
        # Normalize and get endpoints
        if start_angle_d > end_angle_d:  # Make sure start is lower angle
            start_angle_d, end_angle_d = end_angle_d, start_angle_d

        start_angle = math.radians(start_angle_d)
        end_angle = math.radians(end_angle_d)

        while start_angle < 0:
            start_angle += 2 * math.pi
            end_angle += 2 * math.pi

        if abs(end_angle - start_angle) < 2 * math.pi:  # If the arc is not a full circle
            # Start and end points on arc
            startpoint = (center[0] + radius * math.cos(start_angle),
                          center[1] + radius * math.sin(start_angle))
            endpoint = (center[0] + radius * math.cos(end_angle),
                        center[1] + radius * math.sin(end_angle))

            # Get angle from arc center to point
            p_angle = math.atan2(p[1] - center[1], p[0] - center[0])
            if p_angle < 0:  # Normalize to 0 to 2pi
                p_angle += 2 * math.pi

            # Check for angle inclusion
            incl = False
            cwside = False
            ccwside = False
            if start_angle < p_angle < end_angle:
                incl = True  # Angle of p included
            elif p_angle < start_angle:
                cwside = True  # Angle of p is clockwise from arc
            elif p_angle > end_angle:
                ccwside = True  # Angle of p is counterclockwise from arc

            # Compute distance
            def dist(a, b):
                return math.hypot(a[0] - b[0], a[1] - b[1])

            if incl:
                distance = abs(radius - dist(p, center))
            elif cwside:
                distance = dist(p, startpoint)
            elif ccwside:
                distance = dist(p, endpoint)
            else:
                distance = -1  # Error
        else:  # Arc is circle, use circle distance
            distance = abs(radius - math.hypot(p[0] - center[0], p[1] - center[1]))
    else:  # Angles are the same, only one point
        if start_angle_d > end_angle_d:  # Make sure start is lower angle
            start_angle_d, end_angle_d = end_angle_d, start_angle_d

        end_angle = math.radians(end_angle_d)
        anglepoint = (center[0] + radius * math.cos(end_angle),
                      center[1] + radius * math.sin(end_angle))
        distance = math.hypot(p[0] - anglepoint[0], p[1] - anglepoint[1])

    return distance


def sort_by_distance(pts: List[Coordinate2], center: Coordinate2) -> List[Coordinate2]:
    # Return pts, but sorted from nearest to farthest from center
    # Intended only for small sets of points
    ret = []
    orig_sz = len(pts)
    if orig_sz > 0:
        sz = 0
        while sz != orig_sz:
            closest_idx = 0
            min_dist = pts[0].distance(center)
            for i, pt in enumerate(pts):
                dist = pt.distance(center)
                if dist < min_dist:
                    closest_idx = i
                    min_dist = dist
            ret.append(pts[closest_idx])
            pts.pop(closest_idx)
            sz = len(ret)
    return ret


if __name__ == '__main__':
    p1 = Coordinate2()
    p2 = Coordinate2(5,10)
    p3 = Coordinate2(15,-5)
    print(p1)
    print(p2)
    print(p3)
    print(p1+p3)
    print(p2+p3)
    print(-p1)
    print(-p1-p3)
    