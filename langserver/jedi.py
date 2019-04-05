
import jedi
import jedi._compatibility

import opentracing


class RemoteJedi:
    def __init__(self, fs, workspace, root_path):
        self.fs = fs
        self.workspace = workspace
        self.root_path = root_path

    def new_script(self, *args, **kwargs):
        """Return an initialized Jedi API Script object."""
        if "parent_span" in kwargs:
            parent_span = kwargs.get("parent_span")
            del kwargs["parent_span"]
        else:
            parent_span = opentracing.tracer.start_span("new_script_parent")

        with opentracing.start_child_span(parent_span,
                                          "new_script") as new_script_span:
            path = kwargs.get("path")
            new_script_span.set_tag("path", path)
            return self._new_script_impl(new_script_span, *args, **kwargs)

    def _new_script_impl(self, parent_span, *args, **kwargs):
        path = kwargs.get("path")

        if 'trace' in kwargs:
            del kwargs['trace']

        if self.workspace is not None:
            path = self.workspace.project_to_cache_path(path)
            project = self.workspace.find_project_for_path(path)

            environment = None
            for env in jedi.find_virtualenvs([project.VENV_PATH], safe=False):
                if env._base_path == project.VENV_PATH:
                    environment = env
                    break

            kwargs.update(
                environment=environment,
                path=path
            )

        return jedi.api.Script(*args, **kwargs)
