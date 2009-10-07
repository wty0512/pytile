#!/usr/bin/python
# coding: UTF-8
#
# This file is part of the pyTile project
#
# http://entropy.me.uk/pytile
#
## Copyright � 2008-2009 Timothy Baldock. All Rights Reserved.
##
## Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
##
## 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
##
## 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
##
## 3. The name of the author may not be used to endorse or promote products derived from this software without specific prior written permission from the author.
##
## 4. Products derived from this software may not be called "pyTile" nor may "pyTile" appear in their names without specific prior written permission from the author.
##
## THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. 

DEBUG = False

import os
import sys
import math

import pygame
from pygame.locals import *

import logger
debug = logger.Log()
 
from vec2d import *
 
grey = (100,100,100)
lightgray = (200,200,200)
red = (255,0,0)
darkred = (192,0,0)
green = (0,255,0)
darkgreen = (0,128,0)
blue = (0,0,255)
darkblue = (0,0,192)
brown = (72,64,0)
silver = (224,216,216)
black = (0,0,0)
white = (255,255,255)
yellow = (255,255,0)

FPS_REFRESH = 500
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800

# Size of the world in tiles
xWorld = 10
yWorld = 10

TILE_SIZE = 128
#TILE_SIZE = 96
#TILE_SIZE = 96

DRAW_HINTS = False

class World(object):
    """Global world object for all Tiles to reference"""
    init = True
    def __init__(self):
        if World.init:
            World.xWorld = xWorld
            World.yWorld = yWorld
            # Starting offsets, these will center the map by default
            World.offx = WINDOW_WIDTH / 2 - World.xWorld * TILE_SIZE / 2
            World.offy = WINDOW_HEIGHT / 2 - World.yWorld * TILE_SIZE / 2

class Bezier(object):
    """Bezier curve related methods"""
    def calculate_bezier(self, p, steps=30):
        """Calculate a bezier curve from 4 control points and return a list of the resulting points.
        This function uses the forward differencing algorithm described here: 
        http://www.niksula.cs.hut.fi/~hkankaan/Homepages/bezierfast.html"""

        # Bypasses the generation of a bezier curve in straight-line cases
        if len(p) == 2:
            return ([p[1], p[0]], [p[1] - p[0],p[1] - p[0]])

        t = 1.0 / steps
        temp = t*t
        
        f = p[0]
        fd = 3 * (p[1] - p[0]) * t
        fdd_per_2 = 3 * (p[0] - 2 * p[1] + p[2]) * temp
        fddd_per_2 = 3 * (3 * (p[1] - p[2]) + p[3] - p[0]) * temp * t
        
        fddd = fddd_per_2 + fddd_per_2
        fdd = fdd_per_2 + fdd_per_2
        fddd_per_6 = fddd_per_2 * (1.0 / 3)
        
        points = []
        tangents = []
        for x in range(steps):
            points.append(f)
            tangents.append(fd)
            f = f + fd + fdd_per_2 + fddd_per_6
            fd = fd + fdd + fddd_per_2
            fdd = fdd + fddd
            fdd_per_2 = fdd_per_2 + fddd_per_2
        points.append(f)
        tangents.append(fd)
        return (points, tangents)

    def get_at_width(self, point, tangent, width):
        """"""
        newpoint = point + tangent.perpendicular_normal() * width
        return newpoint

    def get_point_at_width(self, a, b, width):
        """"""
        a_to_b = b - a
        c = a + a_to_b.perpendicular_normal() * width
        d = b + a_to_b.perpendicular_normal() * width
        return d

    def find_midpoint(self, a, b):
        """"""
        a_to_b = b - a
        return a + a_to_b / 2.0

    def get_lengths(self, cps):
        """Return array of segment lengths for curve defined by the points in cps"""
        lengths = []
        for p in range(1, len(cps)):
            # Get gradient of a->b
            b = cps[p]
            a = cps[p-1]
            a_to_b = b - a
            ab_n = a_to_b.normalized()
            # Find length of vector divided by normal vector (number of unit lengths)
            lengths.append(a_to_b.get_length() / ab_n.get_length())
        return lengths

    def get_length(self, cps):
        """Return an approximation of the length of the curve
        defined by the control points in cps"""
        lengths = self.get_lengths(cps)
        return sum(lengths)

    def get_segment_vectors(self, cps):
        """Return segment vectors for curve defined by cps"""
        segments = []
        for p in range(1, len(cps)):
            # Get gradient of a->b
            b = cps[p]
            a = cps[p-1]
            a_to_b = b - a
            segments.append(a_to_b)
        return segments

    def get_point_at_length(self, cps, length):
        """Return a vec2d representing the coords of the point on the curve
        at the length specified in real terms"""
        # 1. look up array of segment vectors
        # cps is array from one endpoint to the other, need to find segments
        # in-between these points
        # Points:   0-1-2-3-4
        # Segments:  0-1-2-3
        segments = self.get_segment_vectors(cps)
        # 2. loop through these until the segment length is found
        running_total = 0
        remainder = 0
        exact_point = False
        for n, s in enumerate(segments):
            seg_length = s.get_length() / s.normalized().get_length()
            if running_total + seg_length == length:
                # Edge case, length falls exactly on a segment endpoint
                # Don't need to go any further, find exact point and break out
                exact_point = cps[n+1]
                break
            elif running_total + seg_length > length:
                # Don't need to go any further, find exact point and break out
                remainder = length - running_total
                exact_point = cps[n] + s.normalized() * remainder
                break
            else:
                # Continue
                running_total += seg_length
        return exact_point

        # 3. If segment outside curve, return False
        # 4. Once segment found, multiply remainder by the unit vector for
        #    that segment to find the coordinates of that point


    # This is based on the Graphics Gem code found here:
    # http://tog.acm.org/resources/GraphicsGems/gems/NearestPoint.c 
    def nearest_point_on_curve(self, P, cps):
        """Compute the parameter value fo the point on a Bezier curve
        segment closest to some arbitrary, user-input point
        Return point on the curve at that parameter value"""
        self.maxdepth = 64
        self.epsilon = math.ldexp(1.0, -self.maxdepth-1)
        rec_depth = 0
        w_degree = 5
        degree = 3
        # Convert point p and bezcurve defined by control points cps into
        # a 5th-degree bezier curve form
        w = self.convert_to_bezier_form(P, cps)
        # Find all possible roots of that 5th degree equation
        n_candidates = self.find_roots(w, rec_depth)
        t_candidates = self.tvals

        # Check distance to beginning of curve, where t = 0
        dist = (P - cps[0]).get_length_sqrd()
        tval = 0.0

        # Compare distances of point p to all candidate points found as roots
        for t in t_candidates:
            p = self.get_at_t(cps, t)
            new_dist = (P - p).get_length_sqrd()
            if new_dist < dist:
                dist = new_dist
                tval = t

        # Finally, look at distance to end point, where t = 1.0
        new_dist = (P - cps[3]).get_length_sqrd()
        if new_dist < dist:
            dist = new_dist
            tval = 1.0

        #print tval, dist, self.tvals

        # Return point on curve at parameter value tval
        return self.get_at_t(cps, tval)

    def convert_to_bezier_form(self, P, cps):
        """Given a point and control points for a bezcurve, generate 5th degree
        Bezier-format equation whose solution finds the point on the curve
        nearest the user-defined point"""
        # Precomputed "z" values for cubics
        z = [[1.0, 0.6, 0.3, 0.1],
             [0.4, 0.6, 0.6, 0.4],
             [0.1, 0.3, 0.6, 1.0]]
        # Determine the "c" values, these are vectors created by subtracting
        # point P from each of the control points
        c = []
        for cp in cps:
            c.append(cp - P)
        # Determine the "d" values, these are vectors created by subtracting
        # each control point from the next (and multiplying by 3?)
        d = []
        for i in range(len(cps)-1):
            d.append((cps[i+1] - cps[i]) * 3.0)
        # Create table of c/d values, table of the dot products of the
        # values from c and d
        cdtable = []
        for row in range(len(cps)-1):
            temp = []
            for col in range(len(cps)):
                temp.append(d[row].dot(c[col]))
            cdtable.append(temp)
        # A little unsure about this part, the C-code was unclear!
        # Apply the "z" values to the dot products, on the skew diagonal
        # Also set up the x-values, making these "points"                   - What does this mean?
        w = []
        n = len(cps) - 1
        m = len(cps) - 2
        # Bezier is uniform parameterised
        for i in range(6):
            w.append(vec2d(i/5.0, 0.0))
        for k in range(n+m+1):
            lb = max(0, k - m)
            ub = min(k, n)
            for i in range(lb, ub+1):
                j = k - i
                w[i+j].y += cdtable[j][i] * z[j][i]
        return w
    def find_roots(self, cps, depth):
        """Given a 5th degree equation in Bernstein-Bezier form, find
        all the roots in the interval [0,1]. Return number of roots found"""
        if depth == 0:
            # First level of recursion, set up variables used by the next steps
            self.tvals = []
        cc = self.crossing_count(cps)
        if cc is 0:
            # No solutions here
            return 0
        elif cc is 1:
            # Unique solution
            # Stop recursion when enough recursions have occured (deep enough)
            # If deep enough, return 1 solution at midpoint of current curve
            if depth >= self.maxdepth:
                # cps here is relative, i.e. it refers to the control points
                # of the bisected bezier curve that this branch of recursion
                # is dealing with
                self.tvals.append((cps[0].x + cps[-1].x) / 2.0)
                return 1
            elif self.polygon_flat_enough(cps):
                self.tvals.append(self.compute_x_intercept(cps))
                return 1
        # Otherwise, solve recursively after subdividing control polygon
        left, right = self.subdivide_bezier(cps, 0.5)
        left_count = self.find_roots(left, depth+1)
        right_count = self.find_roots(right, depth+1)
        # All solutions are still being stored in self.tvals, so no need
        # to gather them together

        # Send back total number of solutions
        return left_count + right_count
    def crossing_count(self, cps):
        """Count the number of times a bezier control polygon crosses
        the 0-axis, this number is >= the number of roots"""
        crossings = 0
        # Starting state for sign
        sign = math.copysign(1, cps[0].y)
        old_sign = math.copysign(1, cps[0].y)
        for cp in cps:
            sign = math.copysign(1, cp.y)
            if sign != old_sign:
                crossings += 1
            old_sign = sign
        return crossings
    def polygon_flat_enough(self, cps):
        """Check if the control polygon of a bezier curve is flat
        enough for recursive subdivision to bottom out"""
        # Derive implicit equation for line connecting first and last
        # control points
        a = cps[0].y - cps[-1].y
        b = cps[-1].x - cps[0].x
        c = cps[0].x * cps[-1].y - cps[-1].x * cps[0].y

        max_above = 0.0
        max_below = 0.0

        for cp in cps:
            value = a * cp.x + b * cp.y + c
            if value > max_above:
                max_above = value
            elif value < max_below:
                max_below = value

        # Implicit equation for zero line
        a1 = 0.0
        b1 = 1.0
        c1 = 0.0
        # Implicit equation for "above" line
        a2 = a
        b2 = b
        c2 = c - max_above
        det = a1 * b2 - a2 * b1
        dInv = 1.0 / det
        intercept_1 = (b1 * c2 - b2 * c1) * dInv
        # Implicit equation for "below" line
        a2 = a
        b2 = b
        c2 = c - max_below
        det = a1 * b2 - a2 * b1
        dInv = 1.0 / det
        intercept_2 = (b1 * c2 - b2 * c1) * dInv
        # Compute intercepts of bounding box
        left_intercept = min(intercept_1, intercept_2)
        right_intercept = max(intercept_1, intercept_2)

        error = right_intercept - left_intercept
        if error < self.epsilon:
            return 1
        else:
            return 0

    def compute_x_intercept(self, cps):
        """Compute intersection of line from first control point
        to last control point with the 0-axis"""
        x_lk = 1.0
        y_lk = 0.0
        x_nm = cps[-1].x - cps[0].x
        y_nm = cps[-1].y - cps[0].y
        x_mk = cps[0].x
        y_mk = cps[0].y

        det = x_nm * y_lk - y_nm * x_lk
        dInv = 1.0/det

        return x_lk * (x_nm * y_mk - y_nm * x_mk) * dInv

    def build_vtemp(self, cps, t):
        """"""
        Vtemp = []
        vt2 = []
        for x in range(len(cps)):
            vt = []
            vt22 = []
            for y in range(len(cps)):
                vt.append(vec2d(0,0))
                vt22.append(0)
            vt2.append(vt22)
            Vtemp.append(vt)
                
        # Copy control points
        for n, cp in enumerate(cps):
            Vtemp[0][n].x = cp.x
            vt2[0][n] = 2
            Vtemp[0][n].y = cp.y
        # Triangle computation
        # Uses forward/back substitution on the triangular matrix
        for i in range(1, len(cps)):
            for j in range(len(cps) - i):
                Vtemp[i][j].x = (1.0 - t) * Vtemp[i-1][j].x + t * Vtemp[i-1][j+1].x
                Vtemp[i][j].y = (1.0 - t) * Vtemp[i-1][j].y + t * Vtemp[i-1][j+1].y
                vt2[i][j] = 1
        return Vtemp

    def subdivide_bezier(self, cps, t):
        """Subdivide bezier curve into two smaller curves
        Split occurs at parameter value t"""
        Vtemp = self.build_vtemp(cps, t)
        left = []
        right = []
        for j in range(len(cps)):
            left.append(Vtemp[j][0])
            right.append(Vtemp[len(cps)-1 - j][j])

        return (left, right)

    def get_at_t(self, cps, t):
        """Evaluate bezier curve at particular parameter value"""
        Vtemp = self.build_vtemp(cps, t)

        return Vtemp[len(cps)-1][0]

