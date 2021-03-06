
import os
import json
import platform

import avalon
import pyblish.api


class SubmitDeadlineRender(pyblish.api.InstancePlugin):
    """Publish via rendering rop node on Deadline

    Submitting jobs per instance to deadline.

    """

    order = pyblish.api.ExtractorOrder + 0.492
    hosts = ["houdini"]
    label = "Deadline Render"

    families = [
        "reveries.pointcache",
        "reveries.camera",
        "reveries.standin",
        "reveries.rsproxy",
        "reveries.vdbcache",
        "reveries.fx.layer_prim",
        "reveries.fx.usd",
        "reveries.final.usd"
    ]

    targets = ["deadline"]

    def process(self, instance):
        import reveries

        context = instance.context

        if not all(result["success"] for result in context.data["results"]):
            self.log.warning("Atomicity not held, aborting.")
            return

        # Context data

        username = context.data["user"]
        comment = context.data.get("comment", "")
        project = context.data["projectDoc"]
        asset = instance.data["assetDoc"]["name"]

        fpath = context.data["currentMaking"]
        houdini_version = context.data["houdiniVersion"]

        project_id = str(project["_id"])[-4:].upper()
        project_code = project["data"].get("codename") or project_id
        fname = os.path.basename(fpath)

        batch_name = "({projcode}): [{asset}] {filename}".format(
            projcode=project_code,
            asset=asset,
            filename=fname
        )

        # Instance data

        subset = instance.data["subset"]
        version = instance.data["versionNext"]

        deadline_pool = instance.data["deadlinePool"]
        deadline_prio = instance.data["deadlinePriority"]
        deadline_group = instance.data.get("deadlineGroup")

        frame_per_task = instance.data.get("deadlineFramesPerTask", 1)

        try:
            frame_start = int(instance.data["startFrame"])
            frame_end = int(instance.data["endFrame"])
            frame_step = int(instance.data["step"])

        except KeyError:
            frames = None
        else:
            frames = "{start}-{end}x{step}".format(
                start=frame_start,
                end=frame_end,
                step=frame_step,
            )
            if instance.data["singleOutput"]:
                frame_per_task = len(range(frame_start, frame_end + 1))

        job_name = "{subset} v{version:0>3}".format(
            subset=subset,
            version=version,
        )

        if instance.data.get("deadlineSuspendJob", False):
            init_state = "Suspended"
        else:
            init_state = "Active"

        try:
            ropnode = instance[0]
        except Exception as e:
            # In USD publish, few instance don't need ropnode.
            print("Get ropnode failed: {}".format(e))
            ropnode = None

        # Get output path
        output = self._get_output(ropnode, context)

        _plugin_name = instance.data.get("deadline_plugin", "Houdini")

        # Get HoudiniBatch arguments
        _arguments = ""
        if _plugin_name in ["HoudiniBatch"]:
            reveries_path = reveries.__file__
            script_file = os.path.join(os.path.dirname(reveries_path),
                                       "scripts",
                                       "deadline_extract_houdini.py")
            _arguments = "{} {}".format(
                script_file, instance.data.get("deadline_arguments", "")
            )

        # Assemble payload
        payload = {
            "JobInfo": {
                "Plugin": _plugin_name,  # HoudiniBatch/Houdini
                "BatchName": batch_name,  # Top-level group name
                "Name": job_name,
                "UserName": username,
                "MachineName": platform.node(),
                "Comment": comment,
                "Pool": deadline_pool,
                "Priority": deadline_prio,
                "Group": deadline_group,

                "Frames": frames,
                "ChunkSize": frame_per_task,
                "InitialStatus": init_state,

                "ExtraInfo0": project["name"],
                # "Whitelist": platform.node().lower()
            },
            "PluginInfo": {

                "SceneFile": fpath,
                "Build": "64bit",
                "Version": houdini_version,

                # Renderer Node
                "OutputDriver": ropnode.path() if ropnode else None,
                # Output Filename
                "Output": output,

                "Arguments": _arguments,  # E:\..\deadline_extract_houdini.py
                "ScriptOnly": instance.data.get("deadline_script_only", False),

                "IgnoreInputs": False,
                "GPUsPerTask": 0,
                "SelectGPUDevices": "",
            },
            # Mandatory for Deadline, may be empty
            "AuxFiles": [],
            "IdOnly": True
        }

        # Add dependency for pointcache usd
        if instance.data.get("deadline_dependency", False):
            payload = self._add_dependency(
                instance, payload)

        # Environment
        environment = self.assemble_environment(instance)

        parsed_environment = {
            "EnvironmentKeyValue%d" % index: u"{key}={value}".format(
                key=key,
                value=environment[key]
            ) for index, key in enumerate(environment)
        }
        payload["JobInfo"].update(parsed_environment)

        self.log.info("Submitting.. %s" % instance)
        self.log.info(json.dumps(
            payload, indent=4, sort_keys=True)
        )

        # Submit
        submitter = context.data["deadlineSubmitter"]
        index = submitter.add_job(payload)
        instance.data["deadline_index"] = index

    def _get_output(self, ropnode, context):
        from reveries.houdini import lib

        output = ""
        if ropnode:
            # Override output to use original $HIP
            output = lib.get_output_parameter(ropnode).rawValue()
            on_HIP = output.startswith("$HIP")
            origin_HIP = os.path.dirname(context.data["originMaking"])
            output = output.replace("$HIP", origin_HIP, 1) if on_HIP else output
            # (NOTE) ^^^ For a fixed staging dir
            #   We need this because the scene file we submit to Deadline is a
            #   backup under `$HIP/_published` dir which copied via extractor
            #   plugin `AvalonSaveScene`.
            #
            #   Note that the Deadline (10.0.27.2) Houdini plugin does not support
            #   output filename override if the ROP node type is `alembic`. So to
            #   make this work, I have modified the Deadline Houdini plugin script
            #   `{DeadlineRepo}/plugins/Houdini/hrender_dl.py` at line 375:
            #   ```diff
            #   - elif ropType == "rop_alembic":
            #   + elif ropType in ("rop_alembic", "alembic"):
            #   ```

        return output

    def _add_dependency(self, instance, payload):
        _child_indexs = []

        for _instance in instance.data.get("deadline_dependency", []):
            if "deadline_index" in list(_instance.data.keys()):
                _child_indexs.append(_instance.data.get("deadline_index", ""))
        if _child_indexs:
            dependency_list = {
                "JobDependencies": ",".join(_child_indexs)
            }
            payload["JobInfo"].update(dependency_list)
        return payload

    def assemble_environment(self, instance):
        """Compose submission required environment variables for instance

        Return:
            environment (dict): A set of remote variables, return `None` if
                instance is not assigning to remote site or publish is
                disabled.

        """
        submitter = instance.context.data["deadlineSubmitter"]
        environment = submitter.environment()

        optional_vars = [
            "AVALON_CACHE_ROOT",
            "JOB",
        ]

        optional_vars += self._check_redshift_vars()

        for var in optional_vars:
            value = os.getenv(var)
            if value:
                environment[var] = value

        dumped = ";".join(instance.data["dumpedExtractors"])
        environment["PYBLISH_EXTRACTOR_DUMPS"] = dumped

        environment["PYBLISH_DUMP_FILE"] = instance.data["dumpPath"]

        return environment

    def _check_redshift_vars(self):
        project = avalon.io.find_one({
            "name": avalon.api.Session["AVALON_PROJECT"],
            "type": "project"
        })
        renderer = project.get('renderer', None)
        if renderer == "redshift":
            return [
                "PATH",
                "HOUDINI_PATH",
                "solidangle_LICENSE",
                "redshift_LICENSE",
                "PXR_PLUGINPATH_NAME"
            ]

        return []
