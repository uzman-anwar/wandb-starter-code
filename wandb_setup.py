import os
import time
import argparse
import importlib
import subprocess

import numpy as np
import wandb

import utils

#==============================================================================
# Main function that setups up argparse, wandb etc.
#==============================================================================

def main(raw_args=None):
    start = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--config_file", "-cf", type=str, default=None,
        help="You can pass a yaml config file to override argparse defaults.")
    parser.add_argument("--seed", "-s", type=int, default=None)
    # ========================== Wandb Setup ============================== #
    parser.add_argument("--entity", "-e", type=str, default="usman391",
        help="Wandb entity")
    parser.add_argument("--project", "-p", type=str, default="ABC",
        help="Wandb project")
    parser.add_argument("--group", "-g", type=str, default=None,
        help="Wandb Group")
    parser.add_argument("--name", "-n", type=str, default=None,
        help="Wandb experiment name.")
    # ======================= Add your own args =========================== #
    parser.add_argument("--false_by_default_arg", "-fda", action="store_true",
        help="Use store_true for args that are false by default.")
    parser.add_argument("--true_by_default_arg", "-tda", action="store_false",
        help="Use store_false for args that are true by default.")
    parser.add_argument("--int_arg", "-ia", type=int, default=1,
        help="An integer argument.")
    parser.add_argument("--float_arg", "-fa", type=float, default=1.0,
        help="A float argument.")
    parser.add_argument("--float_arg_with_none_as_default", type=float, default=None,
        help="You can also seed default value to None. \
              You can also skip defining shorthand.")
    parser.add_argument("--timesteps", "-t", type=lambda x: int(float(x)), default=1e6,
        help="You can also pass a lambda function to define custom type. \
              This is useful for converting scientific notation to int.")
    parser.add_argument("--mlp_layers", "-pl", type=int, default=[64,64], nargs='*',
        help="Use nargs for list args.")

 
    args = vars(parser.parse_args(raw_args))

    # Get default config
    default_config, mod_name = {}, ''
    if args["config_file"] is not None:
        if args["config_file"].endswith(".py"):
            mod_name = args["config_file"].replace('/', '.').strip(".py")
            default_config = importlib.import_module(mod_name).config
        elif args["config_file"].endswith(".json"):
            default_config = utils.load_dict_from_json(args["config_file"])
        else:
            raise ValueError("Invalid type of config file")

    # Overwrite config file with parameters supplied through parser
    # Order of priority: supplied through command line > specified in config
    # file > default values in parser
    raw_args = [] if raw_args is None else raw_args
    config = utils.merge_configs(default_config, parser, args, raw_args)
    # Choose seed
    if config["seed"] is None:
        config["seed"] = np.random.randint(0,100)

    # Get name by concatenating arguments with non-default values. Default
    # values are either the one specified in config file or in parser (if both
    # are present then the one in config file is prioritized)
    config["name"] = utils.get_name(parser, default_config, config, mod_name)

    # Initialize W&B project
    on_cambridge_hpc = (subprocess.check_output(["echo $HOME"],
                        shell=True).decode('utf-8').strip().split("/")[-1] == 'ua237')
    base_dir = '/rds-d7/user/ua237/hpc-work/wandb' if on_cambridge_hpc else './wandb'
    base_dir = base_dir + '/' + config['project'] if config['project'] is not None else base_dir
    base_dir = base_dir + '/' + config['group'] if config['group'] is not None else base_dir
    os.makedirs(base_dir, exist_ok=True)
    run = wandb.init(entity=config["entity"], 
                     project=config["project"], 
                     name=config["name"], config=config, dir=base_dir,
                     group=config['group'], reinit=True, monitor_gym=True)
    wandb.config.save_dir = wandb.run.dir
    config = wandb.config

    print(utils.colorize("Configured folder %s for saving" % config.save_dir,
          color="green", bold=True))
    print(utils.colorize("Name: %s" % config.name, color="green", bold=True))

    # Save config
    utils.save_dict_as_json(config.as_dict(), config.save_dir, "config")

    #==============================================================================
    # TODO: ADD CALLS TO TRAIN ETC. HERE
    #==============================================================================

    end = time.time()
    print(utils.colorize("Time taken: %05.2f minutes" % ((end-start)/60),
          color="green", bold=True))

    run.finish()
    return config.save_dir

if __name__ == '__main__':
    main()
