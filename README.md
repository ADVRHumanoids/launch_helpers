# launch_helpers

Python helpers for ROS 2 launch files:

- `launch_windows`: runs each process in its own tmux window, or as plain `ros2 launch`
  processes. A window's command stays in its shell history: Up + Enter restarts it.
- `ros2_run`: `ros2 run` command lines with node name, namespace, params, params files and remaps.
- `params_file`, `ros_params_of`, `merged`: write, read and merge ROS 2 params files.
- `temp_file`: content to a temporary file.
- `declare`, `is_true`: launch arguments.

Not a ROS package: add this repository as a git submodule of each package that uses it, and install
the module next to the package's launch files:

```cmake
install(FILES launch_helpers/launch_helpers.py DESTINATION share/${PROJECT_NAME}/launch)
```

```python
sys.path.insert(0, os.path.join(get_package_share_directory("<package>"), "launch"))
from launch_helpers import launch_windows, ros2_run, temp_file  # noqa: E402
```

A ROS package would need its own `package.xml`; vendored into several repositories of one
workspace, it would be a duplicate package.

## Requirements

ROS 2 `launch` and PyYAML; tmux for `launch_windows(tmux=True)`.
