import os
import sys
import threading


class OnOffMethods:
    def __init__(self, on=False, *argv, **kwargs):
        self.attr_dict = {}
        self.initialized = False
        if on:
            self.is_on = True
            self._do_init(argv, kwargs)
        else:
            self.init_argv = argv
            self.init_kwargs = kwargs
            self.off()
            self.is_on = False

    def _do_init(self, argv, kwargs):
        self._init(*argv, **kwargs)
        self.initialized = True

    def _init(self, *argv, **kwargs):
        """Off method."""
        pass

    def pass_(self, *args, **kwargs):
        """Off method."""
        pass

    def save_attr(self):
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            self.attr_dict[attr_name] = attr

    def on(self):
        if self.is_on:
            return
        for attr_name in self.attr_dict:
            if attr_name.startswith('__') and attr_name.endswith('__'):
                continue
            setattr(self, attr_name, self.attr_dict[attr_name])
        if not self.initialized:
            self._do_init(self.init_argv, self.init_kwargs)
            return
        self.is_on = True

    def off(self):
        self.save_attr()
        for attr_name in dir(self):
            if attr_name.startswith('__') and attr_name.endswith('__'):
                continue
            if attr_name in ('on', 'attr_dict', 'init_argv', 'init_kwargs', '_init', '_do_init'):
                continue
            attr = getattr(self, attr_name)
            if callable(attr):
                setattr(self, attr_name, self.pass_)
            else:
                setattr(self, attr_name, None)
        self.is_on = False


class PrintControl(OnOffMethods):
    _BLUE = '\033[94m'
    _GREEN = '\033[92m'
    _RED = '\033[91m'
    _WITHE = '\033[0m'
    _DEFAULT_COLOR = _WITHE
    COLOR_DICT = {
        'blue': _BLUE,
        'green': _GREEN,
        'red': _RED,
        'withe': _WITHE
    }
    BLUE = 'blue'
    GREEN = 'green'
    RED = 'red'
    WITHE = 'withe'

    @classmethod
    def print_color(cls, string, color=None, *args, **kwargs):
        if color in cls.COLOR_DICT:
            string = cls.COLOR_DICT[color] + string + cls._DEFAULT_COLOR
        print(string, *args, **kwargs)

    def __init__(self, on=True, flush=False, color=_DEFAULT_COLOR, formatter_function=None):
        self.flush = None
        self.show = self.pass_
        self._len_last_print = None
        self.to_print_ = None
        self.add = self.pass_
        self.m = None
        self.color = None
        self.formatter_function = None
        if sys.version_info[0] > 2:
            super().__init__(on, flush=flush, color=color, formatter_function=formatter_function)
        else:
            OnOffMethods.__init__(self, on, flush=flush, color=color, formatter_function=formatter_function)

    def _init(self, *args, **kwargs):
        self.flush = kwargs['flush']
        self.color = kwargs['color']
        self.formatter_function = kwargs['formatter_function']
        self.show = self._print
        self._len_last_print = 0
        self.to_print_ = ''
        self.add = self._concatenate
        self.m = threading.Lock()

    def _print(self, string=None, new_line=True, clean_line=False, color=None, transformation=None):
        if not isinstance(string, str):
            string = str(string)
        if transformation:
            string = transformation(string)
        elif self.formatter_function:
            string = self.formatter_function(string)
        self.m.acquire()
        try:
            if clean_line:
                print('\r', end='')
                print(' ' * self._len_last_print, end='')
                print('\r', end='')
            if not string and not self.to_print_:
                return
            if not string:
                string = self.to_print_
                self.to_print_ = ''
            if color in self.COLOR_DICT:
                string = self.COLOR_DICT[color] + string + self._DEFAULT_COLOR
            elif self.color != self._DEFAULT_COLOR:
                string = self.COLOR_DICT[self.color] + string + self._DEFAULT_COLOR
            self._len_last_print = len(string)
            if new_line:
                print(string)
            else:
                print(string, end='')
            if self.flush:
                sys.stdout.flush()
        finally:
            self.m.release()

    def _concatenate(self, string, color=None):
        if color in self.COLOR_DICT:
            string = self.COLOR_DICT[color] + string + self._DEFAULT_COLOR
        self.to_print_ += string


def file_abs_path(file):
    return os.path.abspath(file)


def dir_abs_path_of_file(file, ends_with='/'):
    return os.path.dirname(file_abs_path(file)) + ends_with
