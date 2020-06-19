# ----------------------------------------------------------------------------
# Copyright (c) 2016-2020, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import collections.abc
import textwrap

from qiime2.sdk import usage
from qiime2.sdk.util import (
    is_metadata_type,
    is_visualization_type,
)

from q2cli.util import to_cli_name


def is_iterable(val):
    return isinstance(val, collections.abc.Iterable)


class CLIUsage(usage.Usage):
    def __init__(self):
        super().__init__()
        self._recorder = []
        self._init_data_refs = dict()

    def _init_data_(self, ref, factory):
        self._init_data_refs[ref] = factory
        return ref

    def _init_metadata_(self, ref, factory):
        self._init_data_refs[ref] = factory
        return ref

    def _init_data_collection_(self, ref, collection_type, *records):
        return sorted([r.ref for r in records])

    def _merge_metadata_(self, ref, records):
        return sorted([r.ref for r in records])

    def _get_metadata_column_(self, column_name, record):
        return (record.ref, column_name)

    def _comment_(self, text: str):
        self._recorder.append('# %s' % (text,))

    def _action_(self, action, input_opts, output_opts):
        t = self._template_action(action, input_opts, output_opts)
        self._recorder.append(t)
        return output_opts

    def _assert_has_line_matching_(self, ref, label, path, expression):
        pass

    def render(self):
        return '\n'.join(self._recorder)

    def get_example_data(self):
        return {r: f() for r, f in self._init_data_refs.items()}

    def _destructure_signature(self, action_sig):
        inputs = {k: v for k, v in action_sig.inputs.items()}
        params, mds = {}, {}
        outputs = {k: v for k, v in action_sig.outputs.items()}

        for param_name, spec in action_sig.inputs.items():
            inputs[param_name] = spec

        for param_name, spec in action_sig.parameters.items():
            if is_metadata_type(spec.qiime_type):
                mds[param_name] = spec
            else:
                params[param_name] = spec

        return {'inputs': inputs, 'params': params,
                'mds': mds, 'outputs': outputs}

    def _destructure_opts(self, signature, input_opts, output_opts):
        inputs, params, mds, outputs = {}, {}, {}, {}

        for opt_name, val in input_opts.items():
            if opt_name in signature['inputs'].keys():
                inputs[opt_name] = (val, signature['inputs'][opt_name])
            elif opt_name in signature['params'].keys():
                params[opt_name] = (val, signature['params'][opt_name])
            elif opt_name in signature['mds'].keys():
                mds[opt_name] = (val, signature['mds'][opt_name])

        for opt_name, val in output_opts.items():
            outputs[opt_name] = (val, signature['outputs'][opt_name])

        return inputs, params, mds, outputs

    def _template_action(self, action, input_opts, output_opts):
        action_f, action_sig = action.get_action()
        signature = self._destructure_signature(action_sig)
        inputs, params, mds, outputs = self._destructure_opts(
            signature, input_opts, output_opts)

        templates = [
            *self._template_inputs(inputs),
            *self._template_parameters(params),
            *self._template_metadata(mds),
            *self._template_outputs(outputs),
        ]

        base_cmd = to_cli_name(f"qiime {action_f.plugin_id} {action_f.id}")

        action_t = self._format_templates(base_cmd, templates)
        return action_t

    def _format_templates(self, command, templates):
        wrapper = textwrap.TextWrapper(initial_indent=" " * 4)
        templates = [command] + [wrapper.fill(t) for t in templates]
        # TODO: double-check that string escaping is working
        return " \\\n".join(templates)

    def _template_inputs(self, input_opts):
        inputs = []
        for opt_name, (ref, _) in input_opts.items():
            refs = ref if isinstance(ref, list) else [ref]
            for ref in refs:
                opt_name = to_cli_name(opt_name)
                inputs.append(f"--i-{opt_name} {ref}.qza")
        return inputs

    def _template_parameters(self, param_opts):
        params = []
        for opt_name, (val, _) in param_opts.items():
            vals = val if is_iterable(val) else [val]
            for val in sorted(vals):
                opt_name = to_cli_name(opt_name)
                params.append(f"--p-{opt_name} {val}")
        return params

    def _template_metadata(self, md_opts):
        mds = []
        for opt_name, (ref, spec) in md_opts.items():
            refs = ref if isinstance(ref, list) else [ref]
            for ref in refs:
                opt_name = to_cli_name(opt_name)
                col = None
                if isinstance(ref, tuple):
                    ref, col = ref
                mds.append(f"--m-{opt_name}-file {ref}.tsv")
                if col is not None:
                    mds.append(f"--m-{opt_name}-column '{col}'")
        return mds

    def _template_outputs(self, output_opts):
        outputs = []
        for opt_name, (ref, spec) in output_opts.items():
            opt_name = to_cli_name(opt_name)
            ext = "qzv" if is_visualization_type(spec.qiime_type) else "qza"
            outputs.append(f"--o-{opt_name} {ref}.{ext}")
        return outputs


def examples(action):
    all_examples = []
    for example in action.examples:
        use = CLIUsage()
        action.examples[example](use)
        rendered_example = use.render()
        header = f"# {example}".replace('_', ' ')
        all_examples.append(header)
        all_examples.append(f"{rendered_example}\n")
    return "\n\n".join(all_examples)
