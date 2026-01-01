"""
CONfiguration DOer
caragols.condo

I provide a nested mapping object, useful for configuration, etc.
Multi-part keys (typically separated by the dot "." element) are parsed into nested keys.

Typical use starts with constructing a condo using the Condex( ) construction function, e.g. ...

conf = Condex( )
conf['some.nested.key'] = 'something'
conf['some.other.key'] = 'else'

#------------------------------------
#-- These two lines are equivalent. |
#------------------------------------
print(conf['some.other.key'])
print(conf['some']['other']['key'])
"""
from pathlib import Path
import sys
import os
import os.path
import collections.abc as pycollections
import json
import fnmatch
import logging
import yaml

assert (sys.version_info.major == 3)  # Check python3

LOGGER = logging.getLogger(__name__)

class ftuple(tuple):
    """
    ftuple is a special case of a tuple that returns its own iterator when called.
    This is used as a hack to allow my own (NTD) .keys (as a property) idiom to be
    shoe-horned in where standard python might expect .keys to be a callable method
    Specifically, dict.update(x) will first check to see if x has an attribute named "keys"
    It then assumes that keys is a callable.  In my own style, .keys returns a set or a tuple
    (depending on the class) and neither sets nor tuples are normally callable.
    ftuple should allow both styles to work.
    """

    def __call__(self):
        return iter(self)


class CxKeyView:
    def __init__(self, cxnode):
        self.nest = cxnode

    @property
    def all(self):
        collected = []
        for k, v in self.nest.children.items():
            hKey = CxKey(k)
            if isinstance(v, CxNode):
                subNode = v
                collected.extend([(hKey / sKey) for sKey in subNode.keys])
            else:
                collected.append(hKey)
        return frozenset(collected)

    def matching(self, pattern):
        spattern = str(pattern)
        return list(sorted(filter(lambda k: fnmatch.fnmatch(str(k), spattern), self.all)))

    def __contains__(self, k):
        k = CxKey(k)
        if k.head in self.nest.children.keys():
            if k.tail.isNotEmpty:
                return (k.tail in self.nest.children[k.head])
            else:
                return True
        else:
            return False

    def __iter__(self):
        return iter(sorted(self.all))

    def __call__(self):
        return iter(self)


class CxKey(tuple):
    def __new__(cls, k=None):
        if k is None:
            return tuple.__new__(cls, [None])

        if isinstance(k, cls):
            return k

        if isinstance(k, str):
            tokens = list(map(lambda token: token.strip(), k.split('.')))
            return cls(tokens)

        if isinstance(k, pycollections.Sequence):
            return tuple.__new__(cls, k)

        if isinstance(k, CxNode):
            if k.isChild:
                return CxKey(k.parent) / k.name
            else:
                return CxKey(None)

        raise TypeError

    @property
    def isEmpty(self):
        if len(self) == 0:
            return True
        elif len(self) == 1:
            return ((self[0] is None) or (self[0] == ''))
        return False

    @property
    def isNotEmpty(self):
        if len(self) > 0:
            if self[0]:
                return True
        return False

    @property
    def head(self):
        return self[0]

    @property
    def tail(self):
        return CxKey(self[1:])

    def __str__(self):
        return '' if self.isEmpty else '.'.join(map(str, self))

    def __format__(self, *args):
        return str(self)

    def __repr__(self):
        return str(self)

    def __truediv__(self, other):
        other = CxKey(other)
        if self[0] is None:
            return CxKey(other)
        else:
            return CxKey(tuple(self) + tuple(other))


class CxNode(object):
    def __init__(self, parent=None, name=None, value=None):
        self.children = {}
        self.parent = parent
        self.name = name
        self.value = value

    def show(self) -> str:
        output = ''
        for k in sorted(self.allKeys):
            v = self[k]
            output += "{key:40s}: {value}\n".format(key=str(k), value=v)
        return output

    def translate(self, k, xlator, **kwargs):
        """
        Given a key, k, performs conditional translation.
        If the (possibly normalized) value of k is one of the values of the xlator mapping, then answer the value of self[k] translated through xlator
        Otherwise, answer the unaltered value of self[k]
        """
        if 'default' in kwargs:
            x = self.get(k, kwargs['default'])
        else:
            x = self[k]

        if 'normalize' in kwargs:
            normalize = kwargs['normalize']
            x = normalize(x)

        if x in xlator:
            x = xlator[x]

        return x

    @property
    def flattened(self):
        """
        Answers a tuple of the form ((keyname, keyval), ...) for each key in self.
        """
        return tuple([(str(k), self[k]) for k in self.allKeys])

    def __iter__(self):
        return iter(self.flattened)

    def __eq__(self, other):
        if isinstance(other, CxNode):
            return (self.flattened == other.flattened)

        if isinstance(other, pycollections.Mapping):
            # -- Flatten the other mapping.
            flatter = tuple([(k, other[k]) for k in sorted(other.keys())])
            return (self.flattened == flatter)

        raise TypeError

    def _dex(self):
        return dict(self.flattened)

    def get(self, *args):
        """
        gets the value of a given key.
        .get(f, key) - answers the value of f(self[key])
        .get(f, key, default) - answers the value of f(self[key] or default)
        .get(key) - answers the value associated with key
        .get(key, default) - answers the value of self[key] or default
        """
        if len(args) == 1:
            # -- .get(key)
            return self[args[0]]

        if len(args) == 2:
            # -- .get(key, default)
            if isinstance(args[0], str):
                k, default = args
                try:
                    return self[k]
                except KeyError:
                    return default

            # -- .get(form, key)
            if callable(args[0]):
                xform, k = args
                return xform(self[k])

        if len(args) == 3:
            # -- .get(form, key, default)
            xform, k, default = args
            return xform(self.get(k, default))

        raise ValueError

    def __contains__(self, k):
        return (k in self.keys)

    def __getitem__(self, k):
        k = CxKey(k)
        if k.isEmpty:
            return self
        else:
            if k.head in self.children:
                if isinstance(self.children[k.head], CxNode):
                    return self.children[k.head][k.tail]
                else:
                    v = self.children[k.head]
                    if callable(v):
                        return v(self.root, k)
                    else:
                        return v
                    return self.children[k.head]
            else:
                raise KeyError(k)

    def __setitem__(self, k, v):
        k = CxKey(k)
        if len(k) == 1:
            self.children[k.head] = v
        else:
            if (k.head not in self.children):
                self.children[k.head] = CxNode(self, k.head)
            self.children[k.head][k.tail] = v

    def load(self, fname, form=None):
        if os.path.exists(fname):
            LOGGER.debug("CxNode/load: reading configuration from %s", fname)

            if form is None:
                # -- Try to guess the form from the file's suffix.
                # -- Here, we get the suffix into a canonical form of 'YAML', 'JSON', etc.
                lemma, suffix = os.path.splitext(fname)
                suffix = suffix.strip().upper()
                if suffix.startswith('.'):
                    suffix = suffix[1:]
                form = suffix
            else:
                form = form.strip().upper()

            JSONs = ['JSON', 'JSN']
            YAMLs = ['YAML', 'YML']

            file_content = Path(fname).read_text()
            blob = None

            LOGGER.debug('Config content: \n %s', file_content)

            if form in JSONs:
                blob = json.loads(file_content)

            elif form in YAMLs:
                if 'yaml' in sys.modules:
                    with Path(fname).open() as f:
                        blob = yaml.safe_load(f)
                else:
                    LOGGER.error("CxNode/read: I cannot read yaml files")

            else:
                raise ValueError(
                    "CxNode/load: I don't know how to handle files of form '{}'".format(form))

            if blob is not None:
                self.update(blob)
        else:
            LOGGER.error('CxNode/read: I cannot find the specified file: %s', fname)

        return self

    def update(self, d):
        if d is not None:
            if isinstance(d, CxNode):
                for k in d.keys:
                    self[k] = d[k]
                return self

            if isinstance(d, pycollections.Mapping):
                for k in d.keys():
                    if isinstance(d[k], pycollections.Mapping):
                        if k not in self:
                            self[k] = CxNode(self, k)
                        self[k].update(d[k])
                    else:
                        self[k] = d[k]
                return self

        raise TypeError

    @property
    def allKeys(self):
        return tuple(sorted(self.keys.all))

    @property
    def keys(self):
        return CxKeyView(self)

    @property
    def root(self):
        """
        Answers a reference to the root node of this configuration tree.
        """
        if self.parent is None:
            return self
        else:
            return self.parent.root

    @property
    def isRoot(self):
        return True if self.parent is None else False

    @property
    def isChild(self):
        return True if self.parent is not None else False

    def sed(self, tokens):
        """
        Interpet the given list of tokens as an edit stream (aka "sed").
        ^file (LOAD) reads the given file name into the configuration
        key: (SET) sets a nested key to some value
        key+ (SADD) adds a value to the key (set semantics)
        key++ (BADD) adds a value to the key (bag semantics)
        key- (SREM) removes a value from the key (set semantics)
        key-- (BREM) removes all instances of the value from the key (bag semantics)
        key! (ON) sets the key to True
        key~ (OFF) sets the key to False
        """
        state = 'SCANNING'
        key = None
        nakeds = []

        for token in tokens:
            LOGGER.debug(
                "CxNode/sed --> token: %s | state: %s | key: %s", token, state, key)
            if token.endswith((':', '!', '~', '+', '-', '^')):
                state = 'SCANNING'
            if state == 'SCANNING':
                LOGGER.debug('SCANNING %s...', token)
                op = None
                if token[-1] == '^':
                    path = token[:-1]
                    self.load(path)

                if token[-1] == ':':
                    key = token[:-1]
                    op = 'SET'

                elif token[-1] == '!':
                    key = token[:-1]
                    self[key] = True

                elif token[-1] == '~':
                    key = token[:-1]
                    self[key] = False

                elif token[-1] == '+':
                    if token[-2:] == '++':
                        key = token[:-2]
                        op = 'BADD'
                    else:
                        key = token[:-1]
                        op = 'SADD'

                elif token[-1] == '-':
                    if token[-2:] == '--':
                        key = token[:-2]
                        op = 'BREM'
                    else:
                        key = token[:-1]
                        op = 'SREM'
                else:
                    # ---------------------------------------------------------
                    # -- the token doesn't appear to have any sed semantics,  |
                    # -- so add it to the "naked" list.                       |
                    # ---------------------------------------------------------
                    nakeds.append(token)

            elif state == 'SET':
                self[key] = token
                op = 'SCANNING'

            elif state == 'SADD':
                if key not in self:
                    self[key] = set()
                else:
                    curval = self[key]
                    if not isinstance(curval, set):
                        if isinstance(curval, (list, tuple)):
                            self[key] = set(curval)
                        else:
                            self[key] = {curval}
                self[key].add(token)

            elif state == 'BADD':
                self[key] = [] if not (key in self) else self[key]
                curval = self[key]

                # ----------------------------------------------------------
                # -- if the current value is a mutable set,                |
                # -- convert the set to aac list to handle the bag semantics |
                # ----------------------------------------------------------
                if isinstance(curval, pycollections.MutableSet):
                    self[key] = list(curval)
                    curval = self[key]

                if isinstance(curval, pycollections.MutableSequence):
                    self[key].append(token)
                else:
                    self[key] = [curval, token]

            elif state == 'SREM':
                if key in self:
                    curval = self[key]
                    if isinstance(curval, pycollections.MutableSet):
                        self[key].discard(token)
                    if isinstance(curval, pycollections.MutableSequence):
                        if token in self[key]:
                            self[key].remove(token)
                op = 'SCANNING'

            elif state == 'BREM':
                if key in self:
                    curval = self[key]
                    if isinstance(curval, pycollections.MutableSet):
                        self[key].discard(token)
                    elif isinstance(curval, pycollections.MutableSequence):
                        while token in self[key]:
                            self[key].remove(token)
            state = op

        return nakeds

    def toJDN(self):
        d = {}
        for k in self.allKeys:
            if k.tail.isEmpty:
                d[str(k)] = self[k]
            else:
                d[str(k.head)] = self[k.head].toJDN()
        return d


def Condex(*args, **kwargs):
    c = CxNode()
    for arg in args:
        c.update(dict(arg))
    c.update(kwargs)
    return c
