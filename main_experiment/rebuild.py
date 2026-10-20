"""Offline main-study reconstruction runner; no dependency on pilot orchestration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid
from .support import command


class RebuildRuntime:
    def __init__(self, config, image):
        self.cfg = {"agent": {"cpus": 4, "memory": "8g"}}
        self.source = Path(config["inputs"])
        self.root = self.source.parent
        self.image = image

    def rebuild(self, workspace, argv, log, timeout):
        name = "adam-exp-" + uuid.uuid4().hex[:12]
        inputs_volume, work_volume = name + "-inputs", name + "-work"
        loader = name + "-loader"
        cmd = ["docker", "create", "--name", name, "--init", "--cap-drop=ALL",
               "--security-opt=no-new-privileges", "--user", f"{os.getuid()}:{os.getgid()}",
               "--cpus", str(self.cfg["agent"]["cpus"]), "--memory", self.cfg["agent"]["memory"],
               "--pids-limit", "256", "--network", "none", "-e", "HOME=/tmp/agent-home",
               "-e", "OPENCODE_CONFIG_CONTENT=" + json.dumps({"permission": {
                   "*": "allow", "webfetch": "deny", "websearch": "deny", "task": "deny",
                   "external_directory": "allow"}}),
               "--mount", f"type=volume,src={work_volume},dst=/workspace",
               "--mount", f"type=volume,src={inputs_volume},dst=/inputs,readonly", "-w", "/workspace"]
        cmd += [self.image] + argv
        created = False
        try:
            # XPT readers/writers issue many small operations. Keep execution
            # on Docker-local storage rather than macOS shared mount paths.
            for volume in (inputs_volume, work_volume):
                subprocess.run(["docker", "volume", "create", volume], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["docker", "create", "--name", loader, "--network", "none",
                            "--mount", f"type=volume,src={inputs_volume},dst=/inputs",
                            "--mount", f"type=volume,src={work_volume},dst=/workspace",
                            self.image, "chown", "-R", f"{os.getuid()}:{os.getgid()}", "/workspace"], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["docker", "cp", str(self.source) + "/.", loader + ":/inputs"], check=True)
            subprocess.run(["docker", "cp", str(workspace) + "/.", loader + ":/workspace"], check=True)
            subprocess.run(["docker", "start", "-a", loader], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
            created = True
            return command(["docker", "start", "-a", name], self.root, log, timeout)
        finally:
            try:
                if created:
                    subprocess.run(["docker", "stop", "-t", "1", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    # Preserve even partially generated evidence after a timeout.
                    returned = workspace.with_name(workspace.name + "-returned-" + uuid.uuid4().hex[:8])
                    returned.mkdir()
                    subprocess.run(["docker", "cp", name + ":/workspace/.", str(returned)], check=True)
                    # Replace rather than merge: agent deletions must survive.
                    shutil.rmtree(workspace)
                    returned.rename(workspace)
            finally:
                subprocess.run(["docker", "rm", "-f", name, loader], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["docker", "volume", "rm", work_volume, inputs_volume], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)