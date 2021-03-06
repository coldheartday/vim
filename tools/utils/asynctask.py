#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#======================================================================
#
# asynctask.py - 
#
# Created by skywind on 2020/02/25
# Last Modified: 2020/02/25 21:55:54
#
#======================================================================
from __future__ import print_function, unicode_literals
import sys
import os
import pprint


#----------------------------------------------------------------------
# 2/3 compatible
#----------------------------------------------------------------------
if sys.version_info[0] >= 3:
    unicode = str
    long = int


UNIX = (sys.platform[:3] != 'win') and True or False


#----------------------------------------------------------------------
# call program and returns output (combination of stdout and stderr)
#----------------------------------------------------------------------
def execute(args, shell = False, capture = False):
    import sys, os  # noqa: F811
    parameters = []
    cmd = None
    if not isinstance(args, list):
        import shlex
        cmd = args
        if sys.platform[:3] == 'win':
            ucs = False
            if sys.version_info[0] < 3:
                if not isinstance(cmd, str):
                    cmd = cmd.encode('utf-8')
                    ucs = True
            args = shlex.split(cmd.replace('\\', '\x00'))
            args = [ n.replace('\x00', '\\') for n in args ]
            if ucs:
                args = [ n.decode('utf-8') for n in args ]
        else:
            args = shlex.split(cmd)
    for n in args:
        if sys.platform[:3] != 'win':
            replace = { ' ':'\\ ', '\\':'\\\\', '\"':'\\\"', '\t':'\\t',
                '\n':'\\n', '\r':'\\r' }
            text = ''.join([ replace.get(ch, ch) for ch in n ])
            parameters.append(text)
        else:
            if (' ' in n) or ('\t' in n) or ('"' in n): 
                parameters.append('"%s"'%(n.replace('"', ' ')))
            else:
                parameters.append(n)
    if cmd is None:
        cmd = ' '.join(parameters)
    if sys.platform[:3] == 'win' and len(cmd) > 255:
        shell = False
    if shell and (not capture):
        os.system(cmd)
        return b''
    elif (not shell) and (not capture):
        import subprocess
        if 'call' in subprocess.__dict__:
            subprocess.call(args)
            return b''
    import subprocess
    if 'Popen' in subprocess.__dict__:
        p = subprocess.Popen(args, shell = shell,
                stdin = subprocess.PIPE, stdout = subprocess.PIPE, 
                stderr = subprocess.STDOUT)
        stdin, stdouterr = (p.stdin, p.stdout)
    else:
        p = None
        stdin, stdouterr = os.popen4(cmd)
    stdin.close()
    text = stdouterr.read()
    stdouterr.close()
    if p: p.wait()
    if not capture:
        sys.stdout.write(text)
        sys.stdout.flush()
        return b''
    return text


#----------------------------------------------------------------------
# read_ini
#----------------------------------------------------------------------
def load_ini_file (ininame, codec = None):
    if not ininame:
        return False
    elif not os.path.exists(ininame):
        return False
    try:
        content = open(ininame, 'rb').read()
    except IOError:
        content = b''
    if content[:3] == b'\xef\xbb\xbf':
        text = content[3:].decode('utf-8')
    elif codec is not None:
        text = content.decode(codec, 'ignore')
    else:
        codec = sys.getdefaultencoding()
        text = None
        for name in [codec, 'gbk', 'utf-8']:
            try:
                text = content.decode(name)
                break
            except:
                pass
        if text is None:
            text = content.decode('utf-8', 'ignore')
    if sys.version_info[0] < 3:
        import StringIO
        import ConfigParser
        sio = StringIO.StringIO(text)
        cp = ConfigParser.ConfigParser()
        cp.readfp(sio)
    else:
        import configparser
        cp = configparser.ConfigParser(interpolation = None,
                strict = False)
        cp.read_string(text)
    config = {}
    for sect in cp.sections():
        section = sect.strip()
        config[section] = {}
        for key, val in cp.items(sect):
            config[section][key.strip()] = val.strip()
    return config


#----------------------------------------------------------------------
# OBJECT：enchanced object
#----------------------------------------------------------------------
class OBJECT (object):
    def __init__ (self, **argv):
        for x in argv: self.__dict__[x] = argv[x]
    def __getitem__ (self, x):
        return self.__dict__[x]
    def __setitem__ (self, x, y):
        self.__dict__[x] = y
    def __delitem__ (self, x):
        del self.__dict__[x]
    def __contains__ (self, x):
        return self.__dict__.__contains__(x)
    def __len__ (self):
        return self.__dict__.__len__()
    def __repr__ (self):
        line = [ '%s=%s'%(k, repr(v)) for k, v in self.__dict__.items() ]
        return 'OBJECT(' + ', '.join(line) + ')'
    def __str__ (self):
        return self.__repr__()
    def __iter__ (self):
        return self.__dict__.__iter__()


#----------------------------------------------------------------------
# configure
#----------------------------------------------------------------------
class configure (object):

    def __init__ (self, path = None):
        self.win32 = sys.platform[:3] == 'win' and True or False
        self._cache = {}
        if not path:
            path = os.getcwd()
        else:
            path = os.path.abspath(path)
        if not os.path.exists(path):
            raise IOError('invalid path: %s'%path)
        if os.path.isdir(path):
            self.home = path
        else:
            self.home = os.path.dirname(path)
        self.path = path
        self.mark = '.git,.svn,.project,.hg,.root'
        if 'VIM_TASK_ROOTMARK' in os.environ:
            mark = os.environ['VIM_TASK_ROOTMARK'].strip()
            if mark:
                self.mark = mark
        mark = [ n.strip() for n in self.mark.split(',') ]
        self.root = self.find_root(self.home, mark, True)
        self.tasks = {}
        self.feature = {}
        self.environ = {}
        self._load_config()
        self.compose_config()

    def read_ini (self, ininame, codec = None):
        ininame = os.path.abspath(ininame)
        key = ininame
        if self.win32:
            key = ininame.replace("\\", '/').lower()
        if key in self._cache:
            return self._cache[key]
        config = load_ini_file(ininame)
        self._cache[key] = config
        inihome = os.path.dirname(ininame)
        for sect in config:
            section = config[sect]
            for key in list(section.keys()):
                val = section[key]
                val = val.replace('$(VIM_INIHOME)', inihome)
                val = val.replace('$(VIM_ININAME)', ininame)
                section[key] = val
        return config

    def find_root (self, path, markers = None, fallback = False):
        if markers is None:
            markers = ('.git', '.svn', '.hg', '.project', '.root')
        if path is None:
            path = os.getcwd()
        path = os.path.abspath(path)
        base = path
        while True:
            parent = os.path.normpath(os.path.join(base, '..'))
            for marker in markers:
                test = os.path.join(base, marker)
                if os.path.exists(test):
                    return base
            if os.path.normcase(parent) == os.path.normcase(base):
                break
            base = parent
        if fallback:
            return path
        return None

    def check_environ (self, key):
        if key in os.environ:
            if os.environ[key].strip():
                return True
        return False

    def extract_list (self, text):
        items = []
        for item in text.split(','):
            item = item.strip('\r\n\t ')
            if not item:
                continue
            items.append(item)
        return items

    def _load_config (self):
        self.system = self.win32 and 'win32' or 'linux'
        self.profile = 'debug'
        self.cfg_name = '.tasks'
        self.rtp_name = 'tasks.ini'
        self.extra_config = []
        if self.check_environ('VIM_TASK_SYSTEM'):
            self.system = os.environ['VIM_TASK_SYSTEM']
        if self.check_environ('VIM_TASK_PROFILE'):
            self.profile = os.environ['VIM_TASK_PROFILE']
        if self.check_environ('VIM_TASK_CFG_NAME'):
            self._cfg_name = os.environ['VIM_TASK_CFG_NAME']
        if self.check_environ('VIM_TASK_RTP_NAME'):
            self._rtp_name = os.environ['VIM_TASK_RTP_NAME']
        if self.check_environ('VIM_TASK_EXTRA_CONFIG'):
            extras = os.environ['VIM_TASK_EXTRA_CONFIG']
            for path in self.extract_list(extras):
                if os.path.exists(path):
                    self.extra_config.append(os.path.abspath(path))
        return 0

    def trinity_split (self, text):
        p1 = text.find(':')
        p2 = text.find('/')
        if p1 < 0 and p2 < 0:
            return [text, '', '']
        parts = text.replace('/', ':').split(':')
        if p1 >= 0 and p2 >= 0:
            if p1 < p2:
                return [parts[0], parts[1], parts[2]]
            else:
                return [parts[0], parts[2], parts[1]]
        elif p1 >= 0 and p2 < 0:
            return [parts[0], parts[1], '']
        elif p1 < 0 and p2 >= 0:
            return [parts[0], '', parts[1]]
        return [text, '', '']

    def config_merge (self, target, source, ininame, mode):
        special = []
        for key in source:
            if ':' in key:
                special.append(key)
            elif '/' in key:
                special.append(key)
            elif key != '*':
                target[key] = source[key]
                if ininame:
                    target[key]['__name__'] = ininame
                if mode:
                    target[key]['__mode__'] = mode
        for key in special:
            parts = self.trinity_split(key)
            parts = [ n.strip('\r\n\t ') for n in parts ]
            name = parts[0]
            if parts[1]:
                if self.profile != parts[1]:
                    continue
            if parts[2]:
                feature = self.feature.get(parts[2], False)
                if not feature:
                    continue
            target[name] = source[key]
            if ininame:
                target[name]['__name__'] = ininame
            if mode:
                target[name]['__mode__'] = mode
        return 0

    # search for global configs
    def collect_rtp_config (self):
        names = []
        t = os.path.join(os.path.expanduser('~/.vim'), self.rtp_name)
        if os.path.exists(t):
            names.append(os.path.abspath(t))
        for path in self.extra_config:
            if os.path.exists(path):
                names.append(os.path.abspath(path))
        for name in names:
            obj = self.read_ini(name)
            self.config_merge(self.tasks, obj, name, 'global')        
        return 0

    # search parent
    def search_parent (self, path):
        output = []
        path = os.path.abspath(path)
        while True:
            parent = os.path.normpath(os.path.join(path, '..'))
            output.append(path)
            if os.path.normcase(path) == os.path.normcase(parent):
                break
            path = parent
        return output

    # search for local configs
    def collect_local_config (self):
        names = self.search_parent(self.home)
        for name in names:
            t = os.path.abspath(os.path.join(name, self.cfg_name))
            if not os.path.exists(t):
                continue
            obj = self.read_ini(t)
            self.config_merge(self.tasks, obj, t, 'local')
        return 0

    # merge global and local config
    def compose_config (self):
        self.tasks = {}
        self.collect_rtp_config()
        self.collect_local_config()
        return 0
        

#----------------------------------------------------------------------
# manager
#----------------------------------------------------------------------
class TaskManager (object):

    def __init__ (self, path):
        self.config = configure(path)

    def task_run (self, name):
        return 0


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        c = configure('d:/acm/github/vim/autoload')
        # cfg = c.read_ini(os.path.expanduser('~/.vim/tasks.ini'))
        # pprint.pprint(cfg)
        print(c.root)
        print(c.trinity_split('command:vim/win32'))
        print(c.trinity_split('command/win32:vim'))
        print(c.trinity_split('command/win32'))
        print(c.trinity_split('command:vim'))
        print(c.trinity_split('command'))
        pprint.pprint(c.tasks)
        # print(c.search_parent('d:/acm/github/vim/autoload/quickui'))
        return 0
    def test2():
        tm = TaskManager('d:/acm/github/vim/autoload/quickui/generic.vim')
        print(tm.config.root)
        pprint.pprint(tm.config.tasks)
    test2()

