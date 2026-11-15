from enum import StrEnum


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class RobotStatus(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    BUSY = "BUSY"


class RobotMode(StrEnum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"


class Movement(StrEnum):
    STOP = "STOP"
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
