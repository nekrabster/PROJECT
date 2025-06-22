from setuptools import setup, Extension
from Cython.Build import cythonize
import os
import sys

def get_ui_modules(path="ui"):
    modules = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".py") and not file.startswith("_"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ".").replace(os.sep, ".")
                modules.append(rel_path[:-3])  # remove .py
    return modules

extensions = [
    Extension(
        module,
        [module.replace(".", os.sep) + ".py"],
        extra_compile_args=["/O2"] if sys.platform == "win32" else ["-O3"],
        extra_link_args=[],
        define_macros=[("NDEBUG", "1")],
        language="c"
    )
    for module in get_ui_modules()
]

if not extensions:
    print("No modules found to compile.")
    sys.exit(1)

setup(
    name="my_app",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": 3,
            "boundscheck": False,
            "wraparound": False,
            "initializedcheck": False,
            "cdivision": True,
            "nonecheck": False,
            "overflowcheck": False,
            "embedsignature": False,
            "profile": False,
            "linetrace": False,
            "always_allow_keywords": False
        },
        annotate=False
    ),
    zip_safe=False,
)