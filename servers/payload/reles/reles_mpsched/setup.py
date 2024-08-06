import os
from distutils.core import Extension, setup

setup(
    name="reles_mpsched",
    ext_modules=[
        Extension(
            "reles_mpsched",
            ["mpsched.c"],
            include_dirs=[
                "/usr/src/linux-headers-{}/include/uapi".format(os.uname().release),
                "/usr/src/linux-headers-{}/include/".format(os.uname().release),
            ],
            define_macros=[("NUM_SUBFLOWS", "2"), ("SOL_TCP", "6")],
        )
    ],
)
