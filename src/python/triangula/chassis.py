from math import cos, sin, degrees, radians, pi

from euclid import Vector2, Point2
from numpy import array as np_array
from numpy.linalg import solve as np_solve

__author__ = 'tom'


def test():
    chassis = HoloChassis(wheels=[
        HoloChassis.OmniWheel(position=Point2(1, 0), angle=0, radius=60),
        HoloChassis.OmniWheel(position=Point2(-1, 0), angle=0, radius=60)]
    )
    print chassis.get_wheel_speeds(translation=Vector2(0, 0), rotation=0.5)
    print chassis.get_wheel_speeds(translation=Vector2(0, 0), rotation=0.5, origin=Point2(1, 0))


def rotate_point(point, angle, origin=None):
    """
    Rotate a Point2 around another Point2

    :param euclid.Point2 point:
        The point to rotate
    :param float angle:
        Angle in radians, anti-clockwise rotation
    :param euclid.Point2 origin:
        Origin of the rotation, defaults to (0,0) if not specified
    :return:
        A new :class:`euclid.Point2` containing the rotated input point
    """
    if origin is None:
        origin = Point2(0, 0)
    s = sin(angle)
    c = cos(angle)
    return Point2(c * (point.x - origin.x) - s * (point.y - origin.y) + origin.x,
                  s * (point.x - origin.x) + c * (point.y - origin.y) + origin.y)


def rotate_vector(vector, angle, origin=None):
    """
    Rotate a :class:`euclid.Vector2` around a :class:`euclid.Point2`

    :param euclid.Vector2 vector:
        The vector to rotate
    :param float angle:
        Angle in radians, anti-clockwise rotation
    :param euclid.Point2 origin:
        Origin of the rotation, defaults to (0,0) if not specified
    :return:
        A new :class:`euclid.Point2` containing the rotated input point
    """
    if origin is None:
        origin = Point2(0, 0)
    s = sin(angle)
    c = cos(angle)
    return Vector2(c * (vector.x - origin.x) - s * (vector.y - origin.y) + origin.x,
                   s * (vector.x - origin.x) + c * (vector.y - origin.y) + origin.y)


def smallest_difference(a, b, max_value=2 * pi):
    """
    Given two floats, a and b, and a maximum possible value for both a and b, calculate the smallest delta from a to b.
    For example, if a=1.0, b=2.5 and max_value=2.6, this should return -1.1, as subtracting 1.1 from a would result in
    -0.1, which will then be transformed to 2.5 after taking its modulus with 2.6. If max_value was 10, it would return
    +1.5, as this is the lower magnitude delta needed to go from 1.0 to 2.5. This function is used when calculating the
    shortest delta between two pose orientations, for this reason the max_value defaults to 2*pi for use when working
    in radians.

    If either a or b are less than zero or greater than the maximum value they will be treated as a % max_value or b %
    max_value respectively for the purposes of this calculation.

    :param float a:
        First value (see above)
    :param b:
        Second value (see above)
    :param max_value:
        Modulus, defaults to 2*pi if not specified
    :return:
        A value d such that (a + d) % max_value == b, and abs(d) is minimal (as there would be an infinite number of
        possible d that satisfy this relationship).
    """
    mod_a = a % max_value
    mod_b = b % max_value
    if abs(mod_a - mod_b) <= max_value / 2:
        return mod_b - mod_a
    elif mod_a >= mod_b:
        return max_value - (mod_a + mod_b)
    else:
        return mod_b + mod_a - max_value


def get_regular_triangular_chassis(wheel_distance, wheel_radius, max_rotations_per_second):
    """
    Build a HoloChassis object with three wheels, each identical in size and maximum speed. Each wheel is positioned
    at the corner of a regular triangle, and with direction perpendicular to the normal vector at that corner.

    :param wheel_distance:
        Distance in millimetres between the contact points of each pair of wheels (i.e. the length of each edge of the
        regular triangle)
    :param wheel_radius:
        Wheel radius in millimetres
    :param max_rotations_per_second:
        Maximum wheel speed in revolutions per second
    :return:
        An appropriately configured HoloChassis
    """
    point = Point2(0, cos(radians(30)) * wheel_distance / 2.0)
    vector = Vector2(-2 * pi * wheel_radius, 0)

    # Pink
    wheel_a = HoloChassis.OmniWheel(
        position=point,
        vector=vector,
        max_speed=max_rotations_per_second)
    # Yellow
    wheel_b = HoloChassis.OmniWheel(
        position=rotate_point(point, -pi * 2 / 3),
        vector=rotate_vector(vector, -pi * 2 / 3),
        max_speed=max_rotations_per_second)
    # Green
    wheel_c = HoloChassis.OmniWheel(
        position=rotate_point(point, -pi * 4 / 3),
        vector=rotate_vector(vector, -pi * 4 / 3),
        max_speed=max_rotations_per_second)

    return HoloChassis(wheels=[wheel_a, wheel_b, wheel_c])


class WheelSpeeds:
    """
    A simple container to hold desired wheel speeds, and to indicate whether any speeds were scaled back due to
    impossibly high values.
    """

    def __init__(self, speeds, scaling):
        """
        Create a new wheel speeds container

        :param speeds:
            A sequence of float values, one per wheel, in revolutions per second
        :param float scaling:
            If a requested translation or rotation was too fast for the chassis to perform, it will return an instance
            of this class with the scaling set to a value greater than 1.0. This indicates that it was unable to
            provide the requested trajectory but has instead provided the highest magnitude one possible. This parameter
            then contains the proportion of the requested trajectory that was possible to provide. For example, if
            the motion requested was a translation of 10mm/s in the X axis and a rotation of 10 radians per second, but
            on calculation this resulted in excessive wheel speeds which weren't possible, it might be scaled back to
            6mm/s on X and 6 radians per second - the motion is proportionately the same just slower, and in this case
            the scaling value would be 0.6.
        """
        self.speeds = speeds
        self.scaling = scaling

    def __str__(self):
        return 'WheelSpeeds[ speeds={}, scaling={} ]'.format(self.speeds, self.scaling)


class Motion:
    """
    A container to hold the translation and rotation vector representing the robot's motion. This is always expressed
    in the robot's coordinate frame, so a translation component of 0,1 always means the robot is heading forwards,
    irrespective of the current orientation of the robot (i.e. if the robot was turned 90 degrees in world space this
    0,1 motion would be a movement along the X axis in world space, but the Y axis in robot space). The rotation
    component of the motion is expressed in radians per second, positive values corresponding to clockwise rotation
    when viewed from the direction relative to the plane such that X is positive to the right and Y positive upwards.
    """

    def __init__(self, translation, rotation):
        """
        Constructor

        :param euclid.Vector2 translation:
            Vector2 representing the translation component in robot coordinate space of the motion.
        :param rotation:
            Rotation in radians per second
        """
        self.translation = translation
        self.rotation = rotation

    def __str__(self):
        return 'Motion[ x={}, y={}, theta={} (deg={}) ]'.format(self.translation.x, self.translation.y, self.rotation,
                                                                degrees(self.rotation))


class Pose:
    """
    A container to hold the position as a Point2 along with orientation in radians, where 0 corresponds to the positive
    Y axis (0,1). Orientation is expressed in radians, with positive values indicating a rotation from the positive Y
    axis in the clockwise direction, i.e. a rotation of 0 is North, pi/2 East, pi South and 3pi/2 West.
    """

    def __init__(self, position, orientation):
        """
        Constructor

        :param euclid.Point2 position:
            A Point2 containing the position of the centre of the robot
        :param float orientation:
            Orientation in radians, 0 being the positive Y axis, positive values correspond to clockwise rotations, i.e.
            pi/4 is East. This value will be normalised to be between 0 and 2 * pi
        """
        self.position = position
        self.orientation = orientation % (2 * pi)

    def pose_to_pose_vector(self, to_pose):
        """
        Calculates the Vector2, in robot coordinate space (remember that Pose objects use world coordinates!) that
        represents the translation required to move from this Pose to the specified target Pose.

        :param triangula.chassis.Pose to_pose:
            A target :class:`triangula.chassis.Pose`, the resultant vector in robot space will translate the robot to
            the position contained in this pose. Note that this does not take any account of the orientation component
            of the to_pose, only the starting one.
        :return:
            A :class:`euclid.Vector2` containing the translation part, in robot space, of the motion required to move
            from this Pose to the target.
        """
        return rotate_vector(
            vector=Vector2(to_pose.position.x - self.position.x, to_pose.position.y - self.position.y),
            angle=-self.orientation)

    def calculate_pose_change(self, motion, time):
        """
        Given this as the starting Pose, a Motion and a time in seconds, calculate the resultant Pose at the end of the
        time interval.

        This makes use of the fact that if you travel in a consistent direction while turning at a constant rate you
        will describe an arc. By calculating the centre point of this arc we can simply rotate the starting pose around
        this centre point. This is considerably simpler than integrating over the motion 3-vector. A special case is
        used to avoid division by zero errors when there is no rotation component to the motion.

        :param triangula.chassis.Motion motion:
            The motion of the robot, assumed to be constant for the duration of the time interval. The motion is
            expressed in the robot's coordinate frame, so a translation of (0,1) is always a forward motion,
            irrespective of the current orientation.
        :param float time:
            The time in seconds
        :return:
            A :class:`triangula.chassis.Pose` which represents resultant pose after applying the supplied motion for the
            given time.
        """
        if motion.rotation != 0:
            # Trivially, the final orientation is the starting orientation plus the rotation in radians per second
            # multiplied by the time in seconds.
            final_orientation = self.orientation + motion.rotation * time
            # We've moved motion.rotation/2PI revolutions, and a revolution is 2PI*r, so we've moved motion.rotation*r,
            # so r is abs(translation)/motion.rotation, meaning our centre point is at normalise(translation).cross() *
            # abs(translation) / motion.rotation, i.e. translation.cross() / motion.rotation
            centre_of_rotation_as_vector = rotate_vector(motion.translation,
                                                         -self.orientation).cross() / motion.rotation
            centre_of_rotation = Point2(x=centre_of_rotation_as_vector.x, y=centre_of_rotation_as_vector.y)
            # Now rotate the starting_pose.position around the centre of rotation, by the motion.rotation angle
            final_position = rotate_point(self.position, motion.rotation, centre_of_rotation)
            return Pose(position=final_position, orientation=final_orientation)
        else:
            # No rotation, avoid the divide by zero catch in the above block and simply add the translation component
            return Pose(position=self.position + rotate_vector(motion.translation, -self.orientation),
                        orientation=self.orientation)

    def __str__(self):
        return 'Pose[x={}, y={}, orientation={} (deg={})]'.format(self.position.x, self.position.y, self.orientation,
                                                                  degrees(self.orientation))


class HoloChassis:
    """
    An assembly of wheels at various positions and angles, which can be driven independently to create a holonomic drive
    system. A holonomic system is one where number of degrees of freedom in the system is equal to the number of
    directly controllable degrees of freedom, so for a chassis intended to move in two dimensions the degrees of freedom
    are two axes of translation and one of rotation. For a full holonomic system we therefore need at least three wheels
    defined.
    """

    def __init__(self, wheels):
        """
        Create a new chassis, specifying a set of wheels.
        
        :param wheels:
            A sequence of :class:`triangula.chassis.HoloChassis.OmniWheel` objects defining the wheels for this chassis.
        """
        self.wheels = wheels
        self._matrix_coefficients = np_array([[wheel.co_x, wheel.co_y, wheel.co_theta] for wheel in self.wheels])

    def calculate_motion(self, speeds):
        """
        Invert the motion to speed calculation to obtain the actual linear and angular velocity of the chassis given
        a vector of wheel speeds. See http://docs.scipy.org/doc/numpy-1.10.1/reference/generated/numpy.linalg.solve.html

        :param speeds:
            An array of wheel speeds, expressed as floats with units of radians per second, positive being towards
            the wheel vector.
        :return:
            A :class:`triangula.chassis.Motion` object containing the calculated translation and rotation in the robot's
            coordinate space.
        """
        motion_array = np_solve(self._matrix_coefficients, np_array(speeds))
        return Motion(Vector2(x=float(motion_array[0]),
                              y=float(motion_array[1])),
                      rotation=float(motion_array[2]))

    def get_max_translation_speed(self):
        """
        Calculate the maximum translation speed, assuming all directions are equivalent and that there is no rotation
        component to the motion.

        :return:
            Maximum speed in millimetres per second as a float
        """
        unrealistic_speed = 10000.0
        scaling = self.get_wheel_speeds(translation=Vector2(0, unrealistic_speed), rotation=0).scaling
        return unrealistic_speed * scaling

    def get_max_rotation_speed(self):
        """
        Calculate the maximum rotation speed around the origin in radians per second, assuming no translation motion
        at the same time.

        :return:
            Maximum radians per second as a float
        """
        unrealistic_speed = 2 * pi * 100
        scaling = self.get_wheel_speeds(translation=Vector2(0, 0), rotation=unrealistic_speed).scaling
        return unrealistic_speed * scaling

    def get_wheel_speeds_from_motion(self, motion):
        return self.get_wheel_speeds(translation=Vector2(motion.x, motion.y), rotation=motion.rotation)

    def get_wheel_speeds(self, translation, rotation, origin=Point2(x=0, y=0)):
        """
        Calculate speeds to drive each wheel in the chassis at to attain the specified rotation / translation 3-vector.

        :param euclid.Vector2 translation:
            Desired translation vector specified in millimetres per second.
        :param float rotation:
            Desired anguar velocity, specified in radians per second where positive values correspond to clockwise
            rotation of the chassis when viewed from above.
        :param euclid.Point2 origin:
            Optional, can define the centre of rotation to be something other than 0,0. Units are in millimetres.
            Defaults to rotating around x=0, y=0.
        :return:
            A :class:`triangula.chassis.WheelSpeeds` containing both the target wheel speeds and the scaling, if any,
            which was required to bring those speeds into the allowed range for all wheels. This prevents unexpected
            motion in cases where only a single wheel is being asked to turn too fast, in such cases all wheel speeds
            will be scaled back such that the highest is within the bounds allowed for that particular wheel. This
            can accommodate wheels with different top speeds.
        """

        def velocity_at(point):
            """
            Compute the velocity as a Vector2 at the specified point given the enclosing translation and rotation values

            Method: Normalise the vector from the origin to the point, then take the cross of itself to produce a unit
            vector with direction that of a rotation around the origin. Scale this by the distance from the origin and
            by the rotation in radians per second, then simply add the translation vector.

            :param euclid.Point2 point:
                Point at which to calculate velocity
            :return:
                A :class:`euclid.Vector2` representing the velocity at the specified point in mm/s
            """
            d = point - origin
            return d.cross() * rotation + translation

        wheel_speeds = list(wheel.speed(velocity_at(wheel.position)) for wheel in self.wheels)
        scale = 1.0
        for speed, wheel in zip(wheel_speeds, self.wheels):
            if wheel.max_speed is not None and abs(speed) > wheel.max_speed:
                wheel_scale = wheel.max_speed / abs(speed)
                scale = min(scale, wheel_scale)
        return WheelSpeeds(speeds=list(speed * scale for speed in wheel_speeds), scaling=scale)

    class OmniWheel:
        """
        Defines a single omni-wheel within a chassis assembly. Omni-wheels are wheels formed from rollers, where the
        motion of the roller is perpendicular to the motion of the primary wheel. This is distinct from a mechanum wheel
        where the rollers are at an angle (normally around 40-30 degrees) to the primary wheel. Omni-wheels must be
        positioned on the chassis with non-parallel unit vectors, mechanum wheels can in some cases be positioned with
        all unit vectors parallel.

        A wheel has a location relative to the chassis centre and a vector describing the direction of motion of the
        wheel when driven with a positive angular velocity. The location is specified in millimetres, and the magnitude
        of the wheel vector should be equal to the number of millimetres travelled in a single revolution. This allows
        for different sized wheels to be handled within the same chassis.
        """

        def __init__(self, position, max_speed=0, angle=None, radius=None, vector=None):
            """
            Create a new omni-wheel object, specifying the position and either a direction vector directly or the angle
            in degrees clockwise from the position Y axis along with the radius of the wheel.

            :param euclid.Point2 position:
                The wheel's contact point with the surface, specified relative to the centre of the
                chassis. Units are millimetres.
            :param float max_speed:
                The maximum number of revolutions per second allowed for this wheel. When calculating the wheel speeds
                required for a given trajectory this value is used to scale back all motion if any wheel would have to
                move at an impossible speed. If not specified this defaults to None, indicating that no speed limit
                should be placed on this wheel.
            :param angle:
                The angle, specified in radians from the positive Y axis where positive values are clockwise from this
                axis when viewed from above, of the direction of travel of the wheel when driven with a positive speed.
                If this value is specified then radius must also be specified and dx,dy left as None.
            :param radius:
                The radius in millimetres of the wheel, measuring from the centre to the contact point with the surface,
                this may be hard to determine for some wheels based on their geometry, particularly for wheels with
                cylindrical rollers, as the radius will vary. For these cases it may be worth directly measuring the
                circumference of the entire assembly and calculating radius rather than measuring directly. This is used
                to determine the magnitude of the direction vector. If this is not None then the angle must also be
                specified, and dx,dy left as None.
            :param euclid.Vector2 vector:
                2 dimensional vector defining the translation of the wheel's contact point after a full
                revolution of the wheel.
            """
            self.position = position
            self.max_speed = max_speed
            if angle is None and radius is None and vector is not None:
                #  Specify wheel based on direct vector """
                self.vector = vector
            elif angle is not None and radius is not None and vector is None:
                # Specify based on angle from positive Y axis and radius """
                circumference = 2 * pi * radius
                self.vector = Vector2(sin(angle) * circumference, cos(angle) * circumference)
            else:
                raise ValueError('Must specify exactly one of angle and radius or translation vector')
            self.vector_magnitude_squared = self.vector.magnitude_squared()
            self.co_x = self.vector.x / self.vector_magnitude_squared
            self.co_y = self.vector.y / self.vector_magnitude_squared
            self.co_theta = (self.vector.x * self.position.y -
                             self.vector.y * self.position.x) / self.vector_magnitude_squared

        def speed(self, velocity):
            """
            Given a velocity at a wheel contact point, calculate the speed in revolutions per second at which the wheel
            should be driven.

            Method: we want to find the projection of the velocity onto the vector representing the drive of this wheel.
            We store the vector representing a single revolution of travel as self.vector, so the projection onto this
            would be velocity.dot(self.vector / abs(self.vector)). However, we want revolutions per second, so we must
            then divide again by abs(self.vector), leading to
            velocity.dot(self.vector / abs(self.vector))/abs(self.vector). Because the definition of the dot product is
            the sum of x1*x2, y1*y2, ... any scalar applied to each x, y ... of a single vector can be moved outside
            the dot product, so we can simplify as velocity.dot(self.vector) / abs(self.vector)^2. As the magnitude of
            the vector is taken by sqrt(x^2+y^2) we can simply express this as (x^2+y^2), held in the convenient
            function magnitude_squared(). So our final simplified form is
            velocity.dot(self.vector) / self.vector.magnitude_squared(). For efficiency, and because self.vector doesn't
            change, we can pre-compute this.

            :param euclid.Vector2 velocity:
                The velocity at the wheel's contact point with the surface, expressed in mm/s
            :return:
                Target wheel speed in rotations per second to hit the desired vector at the contact point.
            """
            return velocity.dot(self.vector) / self.vector_magnitude_squared
