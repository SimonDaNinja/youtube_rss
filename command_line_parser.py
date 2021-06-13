#! /usr/bin/env python3

class CommandLineParseError(Exception):
    pass

class FlagVal:
    def __init__(self, key, value=None):
        self.key = key
        self.value = value
        self.treated = False

    def __eq__(self, other):
        if type(other) is FlagVal:
            return self.key == other.key and self.value == other.value
        elif type(other) is FlagDef:
            return self.key == other.key and other.allowedValue(self.value)
        elif type(other) is str:
            return self.key == other
        else:
            return False

    def __ne__(self, other):
        if type(other) is FlagVal or type(other) is FlagDef or type(other) is str:
            return not self.__eq__(other)
        else:
            return False

class FlagDef:
    def __init__(self, key, allowedValue=None):
        self.key = key
        if type(allowedValue) is list:
            self.allowedValue = lambda x: x in allowedValue
        elif allowedValue == None:
            self.allowedValue = lambda x: x is None
        else:
            self.allowedValue = allowedValue

    def __eq__(self, other):
        if type(other) is FlagVal:
            return self.key == other.key and self.allowedValue(other.value)
        elif type(other) is FlagDef:
            return self.key == other.key and self.allowedValue == other.allowedValue
        elif type(other) is str:
            return self.key == other
        else:
            return False

    def __ne__(self, other):
        if type(other) is FlagVal or type(other) is FlagDef or type(other) is str:
            return not self.__eq__(other)
        else:
            return False

def readFlags(argv):
    flags = []
    skip = False
    for i, arg in enumerate(argv[1:]):
        if skip:
            skip = False
            continue
        if arg.startswith('--'):
            if '=' in arg:
                if arg[2] == '=':
                    raise CommandLineParseError
                key = arg.split('=',1)[0]
                val = arg.split('=',1)[1]
                if val == '':
                    raise CommandLineParseError
                flag = FlagVal(key, val)
            else:
                if len(arg) < 3:
                    raise CommandLineParseError
                flag = FlagVal(arg[2:])
        elif arg.startswith('-'):
            if len(arg) < 2:
                raise CommandLineParseError
            for j in range(len(arg)-1):
                flag = FlagVal(arg[1+i])
                if flag.key in flags:
                    raise CommandLineParseError
                flags.append(flag)
            if not (i+1 >= len(argv) or argv[i+1].startswith('--') or \
                    argv[i+1].startswith('-')):
                flag = FlagVal(arg[-1], argv[i+1])
                skip = True
        if flag.key in flags:
            raise CommandLineParseError
        flags.append(flag)
    return flags

allowedFlags = [
        FlagDef(
            key = 'use-thumbnails',
            allowedValue = None
        )
    ]

if __name__ == '__main__':
    import sys
    print(sys.argv)
    flags = readFlags(sys.argv)
    for flag in flags:
        if flag in allowedFlags:
            print(f'{flag.key} is an allowed flag')
