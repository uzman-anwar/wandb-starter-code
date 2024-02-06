import math
import json
import os

#==============================================================================
# Functions to handle parser.
#==============================================================================

color2num = dict(
    gray=30,
    red=31,
    green=32,
    yellow=33,
    blue=34,
    magenta=35,
    cyan=36,
    white=37,
    crimson=38
)

def colorize(string, color, bold=False, highlight=False):
    attr = []
    num = color2num[color]
    if highlight: num += 10
    attr.append(str(num))
    if bold: attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), string)

def concat_nondefault_arguments(parser, ignore_keys=[], path_keys=[],
                                default_config=None, actual_config=None):
    """
    Given an instance of argparse.ArgumentParser, return a concatenation
    of the names and values of only those arguments that do not have the
    default value (i.e. alternative values were specified via command line).

    So if you run

        python file.py -abc 123 -def 456

    this function will return abc_123_def_456. (In case the value passed for
    'abc' or 'def' is the same as the default value, they will be ignored)

    If a shorter version of the argument name is specified, it will be
    preferred over the longer version.

    Arguments are sorted alphabetically.

    If you want this function to ignore some arguments, you can pass them
    as a list to the ignore_keys argument.

    If some arguments expect paths, you can pass in those as a list to the
    path_keys argument. The values of these will be split at '/' and only the
    last substring will be used.

    If the default config dictionary is specified then the default values in it
    are preferred ovr the default values in parser.

    If the actual_config dictionary is specified then the values in it are preferred
    over the values passed through command line.
    """
    sl_map = get_sl_map(parser)

    def get_default(key):
        if default_config is not None and key in default_config:
            return default_config[key]
        return parser.get_default(key)

    # Determine save dir based on non-default arguments if no
    # save_dir is provided.
    concat = ''
    for key, value in sorted(vars(parser.parse_args()).items()):
        if actual_config is not None:
            value = actual_config[key]

        # Skip these arguments.
        if key in ignore_keys:
            continue

        if type(value) == list:
            b = False
            if get_default(key) is None or len(value) != len(get_default(key)):
                b = True
            else:
                for v, p in zip(value, get_default(key)):
                    if v != p:
                        b = True
                        break
            if b:
                concat += '%s_' % sl_map[key]
                for v in value:
                    if type(v) not in [bool, int] and hasattr(v, "__float__"):
                        if v == 0:
                            valstr = 0
                        else:
                            valstr = round(v, 4-int(math.floor(math.log10(abs(v))))-1)
                    else: valstr = v
                    concat += '%s_' % str(valstr)

        # Add key, value to concat.
        elif value != get_default(key):
            # For paths.
            if value is not None and key in path_keys:
                value = value.split('/')[-1]

            if type(value) not in [bool, int] and hasattr(value, "__float__"):
                if value == 0:
                    valstr = 0
                else:
                    valstr = round(value, 4-int(math.floor(math.log10(abs(value))))-1)
            else: valstr = value
            concat += '%s_%s_' % (sl_map[key], valstr)

    if len(concat) > 0:
        # Remove extra underscore at the end.
        concat = concat[:-1]

    return concat

def get_sl_map(parser):
    """Return a dictionary containing short-long name mapping in parser."""
    sl_map = {}

    # Add arguments with long names defined.
    for key in parser._option_string_actions.keys():
        if key[1] == '-':
            options = parser._option_string_actions[key].option_strings
            if len(options) == 1:   # No short argument.
                sl_map[key[2:]] = key[2:]
            else:
                if options[0][1] == '-':
                    sl_map[key[2:]] = options[1][1:]
                else:
                    sl_map[key[2:]] = options[0][1:]

    # We've now processed all arguments with long names. Now need to process
    # those with only short names specified.
    known_keys = list(sl_map.keys()) + list(sl_map.values())
    for key in parser._option_string_actions.keys():
        if key[1:] not in known_keys and key[2:] not in known_keys:
            sl_map[key[1:]] = key[1:]

    return sl_map

def reverse_dict(x):
    """
    Exchanges keys and values in x i.e. x[k] = v ---> x[v] = k.
    Added Because reversed(x) does not work in python 3.7.
    """
    y = {}
    for k,v in x.items():
        y[v] = k
    return y

def merge_configs(config, parser, parser_dict, sys_argv):
    """
    Merge a dictionary (config) and arguments in parser. Order of priority:
    argument supplied through command line > specified in config > default
    values in parser.
    """
    config_keys = list(config.keys())
    parser_keys = list(parser_dict.keys())

    sl_map = get_sl_map(parser)
    rev_sl_map = reverse_dict(sl_map)
    def other_name(key):
        if key in sl_map:
            return sl_map[key]
        elif key in rev_sl_map:
            return rev_sl_map[key]
        else:
            return key

    merged_config = {}
    for key in config_keys + parser_keys:
        if key in parser_keys:
            # Was argument supplied through command line?
            if key_was_specified(key, other_name(key), sys_argv):
                merged_config[key] = parser_dict[key]
            else:
                # If key is in config, then use value from there.
                if key in config:
                    merged_config[key] = config[key]
                else:
                    merged_config[key] = parser_dict[key]
        elif key in config:
            # If key was only specified in config, use value from there.
            merged_config[key] = config[key]

    return merged_config

def key_was_specified(key1, key2, sys_argv):
    for arg in sys_argv:
        if arg[0] == '-' and (key1 == arg.strip('-') or key2 == arg.strip('-')):
            return True
    return False

def get_name(parser, default_config, actual_config, mod_name):
    """Returns a name for the experiment based on parameters passed."""
    prefix = lambda x, y: x + '_'*(len(y)>0) + y

    name = actual_config["name"]
    if name is None:
        name = concat_nondefault_arguments(
                parser,
                # TODO: Add keys you want to not be included in the name here
                ignore_keys=["config_file", "project", "group"],
                # TODO: Add keys you want to be treated as paths here
                # This avoids including the entire path in the name
                # instead only the last part of the path is included
                path_keys=["expert_path"],
                default_config=default_config,
                actual_config=actual_config
        )
        if len(mod_name) > 0:
            name = prefix(mod_name.split('.')[-1], name)

        # TODO: if you want some key to be the one that occurs
        # first in the name, add it here
        # For example, putting env_id in RL Experiments here
        # generally works for me. 
        # And makes browsing experiments on wandb easier.
        name = prefix(actual_config["project"], name)

    # Append seed and system id regardless of whether the name was passed in
    # or not
    #if "wandb_sweep" in actual_config and not actual_config["wandb_sweep"]:
    #    sid = get_sid()
    #else:
    #    sid = "-1"
    name = name + "_s_" + str(actual_config["seed"]) #+ "_sid_" + sid

    return name

color2num = dict(
    gray=30,
    red=31,
    green=32,
    yellow=33,
    blue=34,
    magenta=35,
    cyan=36,
    white=37,
    crimson=38
)

def colorize(string, color, bold=False, highlight=False):
    attr = []
    num = color2num[color]
    if highlight: num += 10
    attr.append(str(num))
    if bold: attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), string)

def concat_nondefault_arguments(parser, ignore_keys=[], path_keys=[],
                                default_config=None, actual_config=None):
    """
    Given an instance of argparse.ArgumentParser, return a concatenation
    of the names and values of only those arguments that do not have the
    default value (i.e. alternative values were specified via command line).

    So if you run

        python file.py -abc 123 -def 456

    this function will return abc_123_def_456. (In case the value passed for
    'abc' or 'def' is the same as the default value, they will be ignored)

    If a shorter version of the argument name is specified, it will be
    preferred over the longer version.

    Arguments are sorted alphabetically.

    If you want this function to ignore some arguments, you can pass them
    as a list to the ignore_keys argument.

    If some arguments expect paths, you can pass in those as a list to the
    path_keys argument. The values of these will be split at '/' and only the
    last substring will be used.

    If the default config dictionary is specified then the default values in it
    are preferred ovr the default values in parser.

    If the actual_config dictionary is specified then the values in it are preferred
    over the values passed through command line.
    """
    sl_map = get_sl_map(parser)

    def get_default(key):
        if default_config is not None and key in default_config:
            return default_config[key]
        return parser.get_default(key)

    # Determine save dir based on non-default arguments if no
    # save_dir is provided.
    concat = ''
    for key, value in sorted(vars(parser.parse_args()).items()):
        if actual_config is not None:
            value = actual_config[key]

        # Skip these arguments.
        if key in ignore_keys:
            continue

        if type(value) == list:
            b = False
            if get_default(key) is None or len(value) != len(get_default(key)):
                b = True
            else:
                for v, p in zip(value, get_default(key)):
                    if v != p:
                        b = True
                        break
            if b:
                concat += '%s_' % sl_map[key]
                for v in value:
                    if type(v) not in [bool, int] and hasattr(v, "__float__"):
                        if v == 0:
                            valstr = 0
                        else:
                            valstr = round(v, 4-int(math.floor(math.log10(abs(v))))-1)
                    else: valstr = v
                    concat += '%s_' % str(valstr)

        # Add key, value to concat.
        elif value != get_default(key):
            # For paths.
            if value is not None and key in path_keys:
                value = value.split('/')[-1]

            if type(value) not in [bool, int] and hasattr(value, "__float__"):
                if value == 0:
                    valstr = 0
                else:
                    valstr = round(value, 4-int(math.floor(math.log10(abs(value))))-1)
            else: valstr = value
            concat += '%s_%s_' % (sl_map[key], valstr)

    if len(concat) > 0:
        # Remove extra underscore at the end.
        concat = concat[:-1]

    return concat

def get_sl_map(parser):
    """Return a dictionary containing short-long name mapping in parser."""
    sl_map = {}

    # Add arguments with long names defined.
    for key in parser._option_string_actions.keys():
        if key[1] == '-':
            options = parser._option_string_actions[key].option_strings
            if len(options) == 1:   # No short argument.
                sl_map[key[2:]] = key[2:]
            else:
                if options[0][1] == '-':
                    sl_map[key[2:]] = options[1][1:]
                else:
                    sl_map[key[2:]] = options[0][1:]

    # We've now processed all arguments with long names. Now need to process
    # those with only short names specified.
    known_keys = list(sl_map.keys()) + list(sl_map.values())
    for key in parser._option_string_actions.keys():
        if key[1:] not in known_keys and key[2:] not in known_keys:
            sl_map[key[1:]] = key[1:]

    return sl_map

def reverse_dict(x):
    """
    Exchanges keys and values in x i.e. x[k] = v ---> x[v] = k.
    Added Because reversed(x) does not work in python 3.7.
    """
    y = {}
    for k,v in x.items():
        y[v] = k
    return y

def merge_configs(config, parser, parser_dict, sys_argv):
    """
    Merge a dictionary (config) and arguments in parser. Order of priority:
    argument supplied through command line > specified in config > default
    values in parser.
    """
    config_keys = list(config.keys())
    parser_keys = list(parser_dict.keys())

    sl_map = get_sl_map(parser)
    rev_sl_map = reverse_dict(sl_map)
    def other_name(key):
        if key in sl_map:
            return sl_map[key]
        elif key in rev_sl_map:
            return rev_sl_map[key]
        else:
            return key

    merged_config = {}
    for key in config_keys + parser_keys:
        if key in parser_keys:
            # Was argument supplied through command line?
            if key_was_specified(key, other_name(key), sys_argv):
                merged_config[key] = parser_dict[key]
            else:
                # If key is in config, then use value from there.
                if key in config:
                    merged_config[key] = config[key]
                else:
                    merged_config[key] = parser_dict[key]
        elif key in config:
            # If key was only specified in config, use value from there.
            merged_config[key] = config[key]

    return merged_config

def key_was_specified(key1, key2, sys_argv):
    for arg in sys_argv:
        if arg[0] == '-' and (key1 == arg.strip('-') or key2 == arg.strip('-')):
            return True
    return False

def get_name(parser, default_config, actual_config, mod_name):
    """Returns a name for the experiment based on parameters passed."""
    prefix = lambda x, y: x + '_'*(len(y)>0) + y

    name = actual_config["name"]
    if name is None:
        name = concat_nondefault_arguments(
                parser,
                # TODO: Add keys you want to not be included in the name here
                ignore_keys=["config_file", "project", "group"],
                # TODO: Add keys you want to be treated as paths here
                # This avoids including the entire path in the name
                # instead only the last part of the path is included
                path_keys=["expert_path"],
                default_config=default_config,
                actual_config=actual_config
        )
        if len(mod_name) > 0:
            name = prefix(mod_name.split('.')[-1], name)

        # TODO: if you want some key to be the one that occurs
        # first in the name, add it here
        # For example, putting env_id in RL Experiments here
        # generally works for me. 
        # And makes browsing experiments on wandb easier.
        name = prefix(actual_config["project"], name)

    # Append seed and system id regardless of whether the name was passed in
    # or not
    #if "wandb_sweep" in actual_config and not actual_config["wandb_sweep"]:
    #    sid = get_sid()
    #else:
    #    sid = "-1"
    name = name + "_s_" + str(actual_config["seed"]) #+ "_sid_" + sid

    return name

# =============================================================================
# File handlers
# =============================================================================

def save_dict_as_json(dic, save_dir, name=None):
    if name is not None:
        save_dir = os.path.join(save_dir, name+".json")
    with open(save_dir, 'w') as out:
        out.write(json.dumps(dic, separators=(',\n','\t:\t'),
                  sort_keys=True))

def load_dict_from_json(load_from, name=None):
    if name is not None:
        load_from = os.path.join(load_from, name+".json")
    with open(load_from, "rb") as f:
        dic = json.load(f)

    return dic

def save_dict_as_pkl(dic, save_dir, name=None):
    if name is not None:
        save_dir = os.path.join(save_dir, name+".pkl")
    with open(save_dir, 'wb') as out:
        pickle.dump(dic, out, protocol=pickle.HIGHEST_PROTOCOL)

def load_dict_from_pkl(load_from, name=None):
    if name is not None:
        load_from = os.path.join(load_from, name+".pkl")
    with open(load_from, "rb") as out:
        dic = pickle.load(out)

    return dic


