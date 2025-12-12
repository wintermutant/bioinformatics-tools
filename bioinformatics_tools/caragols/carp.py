"""
I implement reporting tools for the Common App Reporting Prototocol (CARP)
"""
import csv
import io
import json
import operator
import traceback
import yaml


class ReplyStatus(tuple):
    DEFAULT_CATEGORY_GLOSS = {
        '1': 'ℹ️ FYI',
        '2': '✅ Success',
        '3': '❔ Inconclusive',
        '4': '❌ Failure',
        '5': '💥 Fault'
    }

    DEFAULT_CODE_GLOSS = {
        100: "FYI",
        200: "ok",
        207: "multi-status",
        300: "inconclusive",
        400: "error in request",
        401: "not authorized",
        403: "forbidden",
        404: "not found",
        412: "precondition failed",
        416: "range not satisfiable",
        500: "exception",
    }

    def __new__(cls, *args):
        if len(args) == 1:
            arg = args[0]

            if isinstance(arg, cls):
                return arg

            if isinstance(arg, int):
                code = int(arg)
                category = str(code)[0]
                phrase = cls.DEFAULT_CODE_GLOSS[code] if (
                    code in cls.DEFAULT_CODE_GLOSS) else cls.DEFAULT_CATEGORY_GLOSS[category]
                return cls(code, phrase)

            if isinstance(arg, str):
                if arg.isdigit():
                    return cls(int(arg))

            if isinstance(arg, (tuple, list)):
                if len(arg) == 2:
                    return cls(arg[0], arg[1])

        if len(args) == 2:
            code = int(args[0])
            phrase = str(args[1])
            return tuple.__new__(cls, (code, phrase))

    code = property(operator.itemgetter(0))
    gloss = property(operator.itemgetter(1))

    def __repr__(self):
        return "{}: {}".format(self.code, self.gloss)

    @property
    def title(self):
        return self.DEFAULT_CATEGORY_GLOSS[self.category]

    @property
    def category(self):
        return str(self.code)[0]

    @property
    def indicates_success(self):
        return (self.category in ('1', '2', '3'))

    @property
    def indicates_failure(self):
        return (self.category in ('4', '5'))


ReplyStatus.FYI = ReplyStatus(100)
ReplyStatus.Ok = ReplyStatus(200)
ReplyStatus.Multiple = ReplyStatus(207)
ReplyStatus.Inconclusive = ReplyStatus(300)
ReplyStatus.Failed = ReplyStatus(400)
ReplyStatus.Unauthorized = ReplyStatus(401)
ReplyStatus.Forbidden = ReplyStatus(403)
ReplyStatus.NotFound = ReplyStatus(404)
ReplyStatus.RangeError = ReplyStatus(416)
ReplyStatus.Exception = ReplyStatus(500)
ReplyStatus.Fault = ReplyStatus.Exception


# -----------------
# -- App commands |
# -----------------
class Report:
    def __init__(self, status, data, body=None):
        self.status = ReplyStatus(status)
        self.data = data
        self.body = body if body is not None else ""

    def __str__(self):
        # NOTE: this is for making json logging config a bit easier. If this gets in the way, it can be removed
        return json.dumps(self.boxed())

    @staticmethod
    def flatten(data_dict):
        """
        Flattens a dictionary into a list of (key, value) tuples.
        """
        if isinstance(data_dict, dict):
            return [(str(k), v) for k, v in data_dict.items()]
        return []

    def toDEX(self, opts=None):
        '''Data EXchange'''
        return self.boxed(opts=opts)

    def toPROSE(self, **kwargs):
        '''Human-readable, mainly for stdout/stderr'''
        return self.toMD(include_data_section=False)

    def toMD(self, **kwargs):
        title = getattr(self, 'title', self.status.title)

        title_stanza = "# {}".format(title)
        status_stanza = "## Status\n{}: {}".format(
            self.status.code, self.status.gloss)
        response_stanza = "## Response 💬\n{}".format(str(self.body))

        stanzas = [title_stanza, status_stanza, response_stanza]

        if kwargs.get('include_data_section', True):
            data_stanza = "## Data\n{}".format(
                yaml.dump(self.data, default_flow_style=False, width=80, indent=3))
            stanzas.append(data_stanza)

        return '\n'.join(stanzas)

    def toROWs(self):
        return self.flatten(self.toDEX())

    def toYAML(self, **kwargs):
        opts = {'default_flow_style': False}
        opts.update(kwargs)
        return yaml.dump(self.toDEX(opts=opts))

    def toJSON(self, **kwargs):
        opts = {'sort_keys': True, 'indent': 3}
        opts.update(kwargs)
        return json.dumps(self.toDEX(opts=opts))

    def toCSV(self):
        rows = self.toROWs()

        dst = io.StringIO()
        writer = csv.writer(dst, quoting=csv.QUOTE_NONNUMERIC)
        for row in rows:
            writer.writerow(row)

        return dst.getvalue()

    def formatted(self, form):
        formatters = {
            'prose':    self.toPROSE,
            'csv':      self.toCSV,
            'CSV':      self.toCSV,
            'yaml':     self.toYAML,
            'YAML':     self.toYAML,
            'json':     self.toJSON,
            'JSON':     self.toJSON,
            'md':       self.toMD,
            'markdown': self.toMD,
        }
        formatter = formatters.get(form, self.toPROSE)
        return formatter()

    def boxed(self, opts=None):
        """
        I answer a dictionary of myself with some minimal canonicalization.
        """
        box = {
            'status': {
                'code': self.status.code,
                'gloss': self.status.gloss
            },
            'body': str(self.body),
            'data': self.data
        }
        if opts:
            box.update(opts)
        return box

    @classmethod
    def Success(cls, **kwargs):
        status = ReplyStatus.Ok
        return cls(status, kwargs.get('data', None), kwargs.get('body', None))

    @classmethod
    def Failure(cls, **kwargs):
        # body = response if (response is not None) else cls.DEFAULT_FAILURE_RESPONSE
        status = ReplyStatus.Failed
        return cls(status, kwargs.get('data', None), kwargs.get('body', None))

    @classmethod
    def Exception(cls, exxor=None, **kwargs):
        body = exxor if (exxor is not None) else traceback.format_exc(10)
        status = ReplyStatus.Exception
        return cls(status, body, kwargs.get('data', None))

    @classmethod
    def Inconclusive(cls, **kwargs):
        status = ReplyStatus.Inconclusive
        return cls(status, kwargs.get('data', None), kwargs.get('body', None))
