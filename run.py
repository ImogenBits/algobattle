#!/usr/bin/env python3
import sys
import os
import logging
import configparser
from optparse import OptionParser
import datetime as dt
import importlib

from match import Match

# Timestamp format: YYYY-MM-DD_HH:MM:SS
_now = dt.datetime.now()
current_timestamp = '{:04d}-{:02d}-{:02d}_{:02d}:{:02d}:{:02d}'.format(_now.year, _now.month, _now.day, _now.hour, _now.minute, _now.second)

if len(sys.argv) < 2:
    sys.exit('Expecting (relative) path to the parent directory of the problem file as argument. Use ./run.py --help for more information on usage and options.')

##Option parser to process arguments from the console.
usage = 'usage: ./%prog FILE [options]\nExpecting (relative) path to the parent directory of the problem file as first argument.'
parser = OptionParser(usage=usage)
parser.add_option('--verbose', dest = 'verbose_logging', action = 'store_true', help = 'Log all debug messages.')
parser.add_option('--output_folder', dest = 'folder_name', default = 'logs/', help = 'Specify the folder into which all logging files are written to. Default: logs/')
parser.add_option('--config_file', dest = 'config_file', default = 'config.ini', help = 'Path to a .ini configuration file to be used for the run. Default: config.ini')
parser.add_option('--solver1', dest = 'solver1_path', default = sys.argv[1].strip('/') + '/solver/', help = 'Specify the folder name containing the solver of the first contestant. Default: arg1/solver/')
parser.add_option('--solver2', dest = 'solver2_path', default = sys.argv[1].strip('/') + '/solver/', help = 'Specify the folder name containing the solver of the second contestant. Default: arg1/solver/')
parser.add_option('--generator1', dest = 'generator1_path', default = sys.argv[1].strip('/') + '/generator/', help = 'Specify the folder name containing the generator of the first contestant. Default: arg1/generator/')
parser.add_option('--generator2', dest = 'generator2_path', default = sys.argv[1].strip('/') + '/generator/', help = 'Specify the folder name containing the generator of the second contestant. Default: arg1/generator/')
parser.add_option('--group_nr_one', dest = 'group_nr_one', type=int, default = '0', help = 'Specify the group number of the first contestant. Default: 0')
parser.add_option('--group_nr_two', dest = 'group_nr_two', type=int, default = '1', help = 'Specify the group number of the second contestant. Default: 1')
parser.add_option('--iterations', dest = 'battle_iterations', type=int, default = '5', help = 'Number of fights that are to be made in the battle (points are split between each fight). Default: 5')
parser.add_option('--points', dest = 'points', type=int, default = '100', help = 'Number of points for which are fought. Default: 100')
parser.add_option('--do_not_count_points', dest = 'do_not_count_points', action = 'store_true', help = 'If set, points are not calculated for the run.')
parser.add_option('-c', '--do_not_log_to_console', dest = 'do_not_log_to_console', action = 'store_true', help = 'Disable forking the logging output to stderr.')

(options, args) = parser.parse_args()

# Validate that all paths given by options exist
if not os.path.exists(sys.argv[1]):
    sys.exit('Input path "{}" does not exist in the file system! Use ./run.py --help for more information on usage and options.'.format(sys.argv[1]))
if not os.path.exists(options.solver1_path):
    sys.exit('The given path for option --solver1 "{}" does not exist in the file system! Use ./run.py --help for more information on usage and options.'.format(options.solver1_path))
if not os.path.exists(options.solver2_path):
    sys.exit('The given path for option --solver2 "{}" does not exist in the file system! Use ./run.py --help for more information on usage and options.'.format(options.solver2_path))
if not os.path.exists(options.generator1_path):
    sys.exit('The given path for option --generator1 "{}" does not exist in the file system! Use ./run.py --help for more information on usage and options.'.format(options.generator1_path))
if not os.path.exists(options.generator2_path):
    sys.exit('The given path for option --generator2 "{}" does not exist in the file system! Use ./run.py --help for more information on usage and options.'.format(options.generator2_path))

# Logging level below which no logs are supposed to be written out.
common_logging_level = logging.INFO

# Enable logging of all levels if the option is set
if options.verbose_logging:
    common_logging_level = logging.DEBUG

if not os.path.exists(options.folder_name):
    os.makedirs(options.folder_name)

# Strings to build the logfile name
group_stamp = '_{}v{}'.format(options.group_nr_one,options.group_nr_two)
logging_path = options.folder_name + current_timestamp + group_stamp + '.log'

# Initialize logger
logging.basicConfig(filename=logging_path, level=common_logging_level, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S')
# Parent-logger for the whole program
logger = logging.getLogger('algobattle')

# Pipe logging out to console if not disabled by option
if not options.do_not_log_to_console:
    _consolehandler = logging.StreamHandler(stream=sys.stderr)
    _consolehandler.setLevel(common_logging_level)

    _consolehandler.setFormatter(logging.Formatter('%(message)s'))

    logger.addHandler(_consolehandler)

logger.info('Options for this run: {}'.format(options))
logger.info('Contents of sys.argv: {}'.format(sys.argv))

# Read in config file specifying problem parameters.
config = configparser.ConfigParser()
if not options.config_file:
    logger.info('No config file specified for this run, terminating!')
    sys.exit(1)
elif not os.path.isfile(options.config_file):
    logger.error('Config file "%s" could not be found, terminating!', options.config_file)
    sys.exit(1)
else:
    logger.info('Using additional configuration options from file "%s".', options.config_file)
    config.read(options.config_file)


def main():
    try:
        Problem = importlib.import_module(sys.argv[1].replace('/','.'))
        problem = Problem.Problem()
    except Exception as e:
        logger.critical('Importing the given problem failed with the following exception: "{}"'.format(e))
        sys.exit(1)

    match = Match(problem, config, options.generator1_path, options.generator2_path,
                    options.solver1_path, options.solver2_path,
                    int(options.group_nr_one), int(options.group_nr_two))

    if not match.build_successful:
        sys.exit(1)

    results0, results1, messages0, messages1 = match.run(int(options.battle_iterations))

    logger.info('#'*70)
    if int(options.battle_iterations) > 0:
        logger.info('Summary of the battle results: \n{}\n'.format(
            format_summary_message(results0, results1, messages0, messages1,int(options.group_nr_one), int(options.group_nr_two))))
        if not options.do_not_count_points:
            points = options.points #Number of points that are awarded in total
            points0 = 0 #points awarded to the first team
            points1 = 0 #points awarded to the second team
            #Points are awarded for each match individually, as one run reaching the cap poisons the average number of points
            for i in range(len(results0)):
                if results0[i] + results1[i] > 0:
                    points0 += round(points/len(results0) * results0[i] / (results1[i] + results0[i]))
                    points1 += round(points/len(results0) * results1[i] / (results0[i] + results1[i]))
                else:
                    points0 += round(points/len(results0) / 2)
                    points1 += round(points/len(results0) / 2)
            logger.info('Group {} gained {} points.'.format(options.group_nr_one, str(points0)))
            logger.info('Group {} gained {} points.'.format(options.group_nr_two, str(points1)))

    print('You can find the log files for this run in {}'.format(logging_path))


def format_summary_message(results0, results1, messages0, messages1, teamA, teamB):
    if not len(results0) == len(results1) == len(messages0) == len(messages1) == int(options.battle_iterations):
        return "Number of results and summary messages are not the same!"
    summary = ""
    for i in range(int(options.battle_iterations)):
        summary += '='*25
        summary += '\n\nResults of battle {}:\n'.format(i+1)
        if results0[i] == 0:
            summary += 'Solver {} did not solve a single instance.\n'.format(teamA)
        else:
            summary += 'Solver {} solved all instances up to size {}.\n'.format(teamA, results0[i])

        summary += 'The reason for failing beyond this size is: "{}"\n'.format(messages0[i])

        if results1[i] == 0:
            summary += 'Solver {} did not solve a single instance.\n'.format(teamB)
        else:
            summary += 'Solver {} solved all instances up to size {}.\n'.format(teamB, results1[i])

        summary += 'The reason for failing beyond this size is: "{}"\n\n'.format(messages1[i])

    summary += 'Average solution size of group {}: {}\n'.format(teamA, sum(results0)//int(options.battle_iterations))
    summary += 'Average solution size of group {}: {}\n'.format(teamB, sum(results1)//int(options.battle_iterations))

    return summary

if __name__ == "__main__":
    main()