# launch_helpers

Python helpers for ROS 2 launch files, shared by lio_mapping and kyon_navigation: one process per
tmux window (`launch_windows`), `ros2 run` command lines (`ros2_run`), params files
(`params_file`, `ros_params_of`, `merged`), temp files, launch arguments (`declare`, `is_true`) and
`centre_view_on_map` for RViz.

Not a ROS package. Each package carries this repo as a git submodule and installs the module next
to its launch files:

```cmake
install(FILES launch_helpers/launch_helpers.py DESTINATION share/${PROJECT_NAME}/launch)
```

```python
sys.path.insert(0, os.path.join(get_package_share_directory("<package>"), "launch"))
from launch_helpers import launch_windows, ros2_run, temp_file  # noqa: E402
```
