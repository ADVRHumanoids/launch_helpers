"""Launch helpers shared by lio_mapping's and kyon_navigation's launch files (not a launch file):
one process per tmux window, `ros2 run` command lines, params files, temp files.

Each package installs this file into its share/<package>/launch (a git submodule, not a ROS
package: one package.xml in two repos would be a duplicate package):

    sys.path.insert(0, os.path.join(get_package_share_directory("<package>"), "launch"))
    from launch_helpers import launch_windows, ros2_run, temp_file  # noqa: E402
"""

import os
import shlex
import subprocess
import sys
import tempfile

import yaml
from launch.actions import DeclareLaunchArgument, ExecuteProcess, LogInfo


def is_true(value: str) -> bool:
    return value.lower() in ("true", "1", "yes", "on")


def declare(name: str, default: str, description: str) -> DeclareLaunchArgument:
    return DeclareLaunchArgument(name, default_value=default, description=description)


def temp_file(content: str, suffix: str) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, prefix="launch_", delete=False)
    f.write(content)
    f.close()
    return f.name


def ros_params_of(path: str, node_name: str, namespace: str = "") -> dict:
    """The ros__parameters of `node_name` in a params file ({} if none)."""
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    for key in (
        f"{namespace}/{node_name}",
        f"/**/{node_name}",
        f"/{node_name}",
        node_name,
        "/**",
    ):
        if key in data:
            return data[key].get("ros__parameters", {})
    return {}


def merged(base: dict, over: dict) -> dict:
    """Recursive merge: values of `over` replace those of `base`, maps are merged."""
    out = dict(base)
    for k, v in over.items():
        out[k] = (
            merged(out[k], v)
            if isinstance(v, dict) and isinstance(out.get(k), dict)
            else v
        )
    return out


def params_file(node_name: str, params: dict, namespace: str = "") -> str:
    """Params file of `params` for the node ("a.b.c" keys become nested maps)."""
    nested: dict = {}
    for dotted, value in params.items():
        *parents, leaf = dotted.split(".")
        node = nested
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return temp_file(
        yaml.safe_dump({f"{namespace}/{node_name}": {"ros__parameters": nested}}),
        ".yaml",
    )


def ros2_run(
    package,
    executable,
    name=None,
    params=(),
    args=(),
    remaps=(),
    param_files=(),
    namespace=None,
):
    """`ros2 run` command line."""
    cmd = ["ros2", "run", package, executable, *args, "--ros-args"]
    if name:
        cmd += ["-r", f"__node:={name}"]
    if namespace:
        cmd += ["-r", f"__ns:={namespace}"]
    for f in param_files:
        cmd += ["--params-file", f]
    for k, v in dict(params).items():
        cmd += ["-p", f"{k}:={v}"]
    for a, b in remaps:
        cmd += ["-r", f"{a}:={b}"]
    return shlex.join(cmd)


def centre_view_on_map(view, map_dir):
    """Points an RViz Orbit view at the middle of a saved map or session (its keyframes)."""
    poses = os.path.join(map_dir, "poses.csv")
    if not os.path.isfile(poses):
        poses = os.path.join(map_dir, "odom_poses.csv")  # a session
    try:
        with open(poses) as f:
            xyz = [
                [float(v) for v in line.split(",")[2:5]]
                for line in f
                if line.strip() and not line.startswith("#")
            ]
    except (OSError, ValueError):
        return
    if not xyz:
        return
    lo = [min(p[k] for p in xyz) for k in range(3)]
    hi = [max(p[k] for p in xyz) for k in range(3)]
    view["Focal Point"] = {k: (lo[i] + hi[i]) / 2.0 for i, k in enumerate("XYZ")}
    view["Distance"] = max(50.0, 1.2 * max(hi[0] - lo[0], hi[1] - lo[1]))


def _tmux_session(name: str, append: bool) -> bool:
    """Whether session `name` exists; raises if it does and windows may not be appended."""
    exists = (
        subprocess.run(
            ["tmux", "has-session", "-t", f"={name}"], capture_output=True
        ).returncode
        == 0
    )
    if exists and not append:
        raise RuntimeError(
            f"tmux session '{name}' already exists: close it (tmux kill-session -t {name}) "
            f"or pass tmux_session:=<other name>"
        )
    return exists


def launch_windows(
    name: str,
    windows: list,
    tmux: bool,
    attach: bool,
    append: bool = False,
    focus: str = None,
):
    """Runs (window name, shell command) pairs in tmux session `name`, one window each, or without
    tmux as processes of ros2 launch. With append, an existing session gets the windows. The
    session shows window `focus`, else (new session) the first.
    """
    if not tmux:
        return [
            ExecuteProcess(cmd=["bash", "-c", cmd], name=title, output="screen")
            for title, cmd in windows
        ]
    exists = _tmux_session(name, append)
    # The tmux server's environment may predate `source install/setup.bash`: re-export it.
    env_file = temp_file(
        "".join(
            f"export {k}={shlex.quote(v)}\n"
            for k, v in os.environ.items()
            if k.isidentifier()
        ),
        ".env",
    )

    # Interactive shell running the command, with it as the only history entry: Up + Enter
    # restarts it. No history file is read or written.
    def window_cmd(title, cmd):
        rc = temp_file(
            "[ -f ~/.bashrc ] && source ~/.bashrc\n"
            f"source {shlex.quote(env_file)}\n"
            "unset HISTFILE\n"
            "history -c\n"
            f"history -s {shlex.quote(cmd)}\n"
            f"echo {shlex.quote('$ ' + cmd)}\n"
            f"{cmd}\n"
            f'echo; echo "[{title} exited with code $?; Up + Enter restarts it]"\n',
            ".rc",
        )
        return f"bash --rcfile {shlex.quote(rc)} -i"

    (first_title, first_cmd), *rest = windows
    if exists:
        rest = windows
    else:
        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                name,
                "-n",
                first_title,
                "-x",
                "220",
                "-y",
                "60",
            ]
            + [window_cmd(first_title, first_cmd)],
            check=True,
        )
    for title, cmd in rest:
        subprocess.run(
            [
                "tmux",
                "new-window",
                "-d",
                "-t",
                f"={name}:",
                "-n",
                title,
                window_cmd(title, cmd),
            ],
            check=True,
        )
    if focus or not exists:
        subprocess.run(
            ["tmux", "select-window", "-t", f"={name}:{focus or first_title}"],
            check=True,
        )

    started = ", ".join(t for t, _ in windows)
    if os.environ.get("TMUX"):
        if attach:
            subprocess.run(["tmux", "switch-client", "-t", f"={name}"], check=True)
            return [
                LogInfo(
                    msg=f"Started {started} in tmux session '{name}' (switched to it)"
                )
            ]
    elif attach and sys.stdin.isatty() and sys.stdout.isatty():
        # ros2 launch cannot hand its terminal to a child: become the tmux client.
        print(f"Started {started} in tmux session '{name}', attaching...", flush=True)
        os.execvp("tmux", ["tmux", "attach-session", "-t", f"={name}"])
    return [
        LogInfo(
            msg=f"Started {started} in tmux session '{name}' (attach: tmux attach -t {name})"
        )
    ]
