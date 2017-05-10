import opentracing
import lightstep


class Tracer:

    # just use class vars; no need for multiple independent tracer instances
    lightstep_project = None
    lightstep_token = None

    @staticmethod
    def setup(lightstep_project, lightstep_token):

        Tracer.lightstep_project = lightstep_project
        Tracer.lightstep_token = lightstep_token

        # if these variables aren't set, we'll fall back on the default no-op opentracing implementation
        if lightstep_project and lightstep_token:
            opentracing.tracer = lightstep.Tracer(component_name="python-langserver", access_token=lightstep_token)


    @staticmethod
    def start_span(opname, parent_span=None):
        if (parent_span):
            return opentracing.start_child_span(parent_span, opname)
        else:
            return opentracing.tracer.start_span(operation_name=opname)