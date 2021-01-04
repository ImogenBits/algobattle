#!/usr/bin/env python3

import sys
import subprocess
import signal
import timeit
import logging

logger = logging.getLogger('algobattle.framework')

class Match:
    def __init__(self, problem, config, generator1_path, generator2_path, solver1_path, solver2_path, group_nr_one, group_nr_two):
        self.timeout_build     = int(config['run_parameters']['timeout_build'])
        self.timeout_generator = int(config['run_parameters']['timeout_generator'])
        self.timeout_solver    = int(config['run_parameters']['timeout_solver'])
        self.space_generator   = int(config['run_parameters']['space_generator'])
        self.space_solver      = int(config['run_parameters']['space_solver'])
        self.cpus              = int(config['run_parameters']['cpus'])
        self.iteration_cap     = int(config['run_parameters']['iteration_cap'])
        self.problem = problem
        self.config = config

        self.latest_running_docker_image = ""

        def signal_handler(sig, frame):
                print('You pressed Ctrl+C!')
                self._kill_spawned_docker_containers()
                logger.info('Received SIGINT.')
                sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)

        self.build_successful = self._build(generator1_path, generator2_path, solver1_path, solver2_path, group_nr_one, group_nr_two)

    def _build(self, generator1_path, generator2_path, solver1_path, solver2_path, group_nr_one, group_nr_two):
        """Builds docker containers for the given generators and solvers.
        
        Parameters:
        ----------
        generator1_path: str
            Path to the generator of the first team.
        generator1_path: str
            Path to the generator of the second team.
        solver1_path: str
            Path to the solver of the first team.
        solver2_path: str
            Path to the solver of the second team.
        group_nr_one: int
            Group number of the first team.
        group_nr_two: int
            Group number of the second team.
        Returns:
        ----------
        Bool:
            Boolean indicating whether the build process succeeded.
        """
        docker_build_base = [
            "docker",
            "build",
            "--network=host",
            "-t"
        ]
        self.teamA = group_nr_one
        self.teamB = group_nr_two

        build_commands = []
        build_commands.append(docker_build_base + ["solver"+str(group_nr_one), solver1_path])
        build_commands.append(docker_build_base + ["solver"+str(group_nr_two), solver2_path])
        build_commands.append(docker_build_base + ["generator"+str(group_nr_one), generator1_path])
        build_commands.append(docker_build_base + ["generator"+str(group_nr_two), generator2_path])

        success = True
        for command in build_commands:
            logger.debug('Building docker container with the following command: {}'.format(command))
            process = subprocess.Popen(command)
            try:
                process.communicate(timeout=self.timeout_build)
            except subprocess.TimeoutExpired as e:
                process.kill()
                success = False
                logger.error('Build process for {} ran into a timeout!'.format(command[5]))
            if process.returncode != 0:
                process.kill()
                success = False
                logger.error('Build process for {} failed!'.format(command[5]))

        return success


    def run(self, iterations=5):
        """ Match entry point. Executes iterations fights between two teams and
        returns the results with failure messages of the battles.

        Parameters:
        ----------
        iterations: int
            Number of Battles between teamA and teamB.
        Returns:
        ----------
        (list, list, list, list) 
            The first two lists contain the highest n for each iteration for which 
            the team was still able to solve the opposing instance.  
            The last two lists contain the failure messages for each of the iterations.
        """
        results_A = []
        results_B = []

        failure_messages_A = []
        failure_messages_B = []

        for j in range(iterations):
            logger.info('Running battle {}/{}...'.format(j+1,iterations))

            maximum_A, failure_message = self._battle_wrapper(self.teamB, self.teamA)
            failure_messages_A.append(failure_message)
            logger.info('{}'.format(failure_message))

            maximum_B, failure_message = self._battle_wrapper(self.teamA, self.teamB)
            failure_messages_B.append(failure_message)
            logger.info('{}'.format(failure_message))

            results_A.append(maximum_A)
            results_B.append(maximum_B)

        return results_A, results_B, failure_messages_A, failure_messages_B

    def _kill_spawned_docker_containers(self):
        """Terminates all running docker containers."""
        if self.latest_running_docker_image:
            if subprocess.check_output("docker ps -a -q", shell=True):
                subprocess.run('docker ps -a -q --filter ancestor={} | xargs -r docker stop > /dev/null'.format(self.latest_running_docker_image), shell=True)

    def _battle_wrapper(self, generating_team, solving_team):
        """Wrapper to execute one round of the number of wanted battles.

        Incrementally try to search for the highest n for which the solver
        is still able to solve instances.  The base increment value is
        multiplied with the square of the iterations since the last
        unsolvable instance.  Only once the solver fails after the
        multiplier is reset, it counts as failed. Since this would heavily
        favour probabilistic algorithms (That may have only failed by chance
        and are able to solve a certain instance size on a second try), we
        cap the maximum solution size by the first value that an algorithm
        has failed on.

        The wrapper automatically ends the battle and declares the solver
        as the winner once the iteration cap is reached, which is set
        in the config.ini.

        Parameters:
        ----------
        generating_team: int
            Group number of the generating team, expected to be a positive int.
        solving_team: int
            Group number of the solving team, expected to be a positive int.
        Returns:
        ----------
        (int, str)
            Returns the biggest instance size for which the solving team still found a solution.
            Returns a message about the reason why the solver was unable to solve a bigger instance.
        """
        n = self.problem.n_start
        maximum_reached_n = -1
        i = 0
        n_cap = 50000
        most_recent_failure_message = ''
        alive = True

        while alive:
            logger.info('=============== instance size: {} ==============='.format(n))
            alive, message  = self._one_fight(n, generating_team, solving_team)
            logger.info(message)
            if not alive:
                #We are only interested in the very last failure message
                most_recent_failure_message = message
            
            #Try to search for the highest n for which the solver still runs through
            if not alive and i > 1:
                #The step size increase was too aggressive, take it back and reset the increment multiplier
                logger.info('Setting the solution cap to {}...'.format(n))
                n_cap = n
                n -= i * i
                i = 0
                alive = True
            elif n > maximum_reached_n and alive:
                #We solved an instance of bigger size than before
                maximum_reached_n = n

            if n+1 == n_cap:
                alive = False
                break
            
            i += 1
            n += i * i

            if n >= n_cap and n_cap != self.iteration_cap:
                #We have failed at this value of n already, reset the step size!
                n -= i * i - 1
                i = 1
            elif n >= n_cap and n_cap == self.iteration_cap:
                most_recent_failure_message = 'Solver {} exceeded the instance size cap of {}!'.format(solving_team, self.iteration_cap)
                maximum_reached_n = self.iteration_cap
                alive = False
        return (maximum_reached_n, most_recent_failure_message)


    def _one_fight(self, size, generating_team, solving_team):
        """Executes a single fight of a battle between a given generator and
        solver for a given instance size.

        Parameters:
        ----------
        size: int 
            The instance size.
        generating_team: int
            The group number of the generating team, expected to be nonnegative ints.  
        solving_team: int
            The group number of the solving team, expected to be nonnegative ints.
        Returns:
        ----------
        (bool, str) 
            The boolean indicates whether the solver was successful in
            solving the given instance.  The string contains a message
            containing a failure or success message.
        """
        if not str(generating_team).isdigit() or not str(solving_team).isdigit():
            logger.error('Solving and generating team are expected to be nonnegative ints, received "{}" and "{}".'.format(generating_team, solving_team))
            raise Exception('Solving and generating team are expected to be nonnegative ints!')
        elif not generating_team >= 0 or not solving_team >= 0:
            logger.error('Solving and generating team are expected to be nonnegative ints, received "{}" and "{}".'.format(generating_team, solving_team))
            raise Exception('Solving and generating team are expected to be nonnegative ints!')

        generator_run_command = [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            "-i",
            "--memory=" + str(self.space_generator) + "mb",
            "--cpus=" + str(self.cpus),
            "generator" + str(generating_team)
        ]
        solver_run_command = [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            "-i",
            "--memory=" + str(self.space_solver) + "mb",
            "--cpus=" + str(self.cpus),
            "solver" + str(solving_team)
        ]

        logger.info('Running generator of group {}...\n'.format(generating_team))

        p = subprocess.Popen(generator_run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.latest_running_docker_image = "generator" + str(generating_team)
        start_time = timeit.default_timer()
        try:
            raw_instance_with_solution, _ = p.communicate(input=str(size).encode(), timeout=self.timeout_generator)
            raw_instance_with_solution = self.problem.parser.decode(raw_instance_with_solution)
            logger.info('Approximate elapsed runtime: {}/{} seconds.'.format('{:.2f}'.format(timeit.default_timer() - start_time), self.timeout_generator))
        except subprocess.TimeoutExpired:
            elapsed_time = '{:.2f}'.format(timeit.default_timer() - start_time)
            logger.info('Approximate elapsed runtime: {}/{} seconds.'.format(elapsed_time, self.timeout_generator))
            p.kill()
            self._kill_spawned_docker_containers()
            return (True, "Generator {} exceeded the given time limit at instance size {}! ({}s/{}s)".format(solving_team, size, elapsed_time, self.timeout_generator))


        logger.info('Checking generated instance and certificate...')

        raw_instance, raw_solution = self.problem.parser.split_into_instance_and_solution(raw_instance_with_solution)
        instance                   = self.problem.parser.parse_instance(raw_instance, size)
        generator_solution         = self.problem.parser.parse_solution(raw_solution, size)

        if not self.problem.verifier.verify_solution_against_instance(instance, generator_solution, size):
            return (True, 'Generator {} failed at instance size {}!'.format(generating_team, size))

        logger.info('Generated instance and certificate are valid!\n\n')


        logger.info('Running solver of group {}...\n'.format(solving_team))

        p = subprocess.Popen(solver_run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self.latest_running_docker_image = "solver" + str(solving_team)
        start_time = timeit.default_timer()
        try:
            raw_solver_solution, _ = p.communicate(input=self.problem.parser.encode(instance), timeout=self.timeout_solver)
            logger.info('Approximate elapsed runtime: {}/{} seconds.'.format('{:.2f}'.format(timeit.default_timer() - start_time),self.timeout_solver))
        except subprocess.TimeoutExpired:
            elapsed_time = '{:.2f}'.format(timeit.default_timer() - start_time)
            logger.info('Approximate elapsed runtime: {}/{} seconds.'.format(elapsed_time, self.timeout_solver))
            p.kill()
            self._kill_spawned_docker_containers()
            return (False, "Solver {} exceeded the given time limit at instance size {}! ({}s/{}s)".format(solving_team, size, elapsed_time, self.timeout_solver))


        logger.info('Checking validity of the solvers solution...')
        
        solver_solution = self.problem.parser.parse_solution(self.problem.parser.decode(raw_solver_solution), size)
        if not self.problem.verifier.verify_solution_against_instance(instance, solver_solution, size):
            return (False, 'Solver {} yields a wrong answer at instance size {}.'.format(solving_team, size))
        elif not self.problem.verifier.verify_solution_quality(generator_solution, solver_solution):
            return (False, 'The solvers solution does not meet the wanted solution quality!')
        else:
            return (True, 'Solver {} yields a correct answer in the given time limit!\n'.format(solving_team))