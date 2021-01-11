from abc import ABC, abstractmethod

class Parser(ABC):
    @abstractmethod
    def split_into_instance_and_solution(self, raw_input):
        """ Splits an input into instance and solution lines, discards anything else.
        
        The validity is only checked by grouping together lines with the same
        first element as an identifier. No checks are made that test whether
        they are otherwise well formatted or semantically correct.

        Parameters:
        ----------
        raw_input: list
            The raw input as list of tuples.

        Returns:
        ----------
        list, list
            Returns all instance lines and all solution lines, each as a list of tuples.
            The lines may still be syntactially and semantically incorrect.
        """
        raise NotImplementedError

    @abstractmethod
    def parse_instance(self, raw_instance, instance_size):
        """ Removes all syntactially and semantically wrong lines from the raw instance.

        Parameters:
        ----------
        raw_input: list
            The raw instance as list of tuples.
        instance_size: int
            The size of the instance.

        Returns:
        ----------
        list
            Returns all valid instance lines as a list of tuples.
        """
        raise NotImplementedError

    @abstractmethod
    def parse_solution(self, raw_solution, instance_size):
        """ Removes all syntactially and semantically wrong lines from the raw solution.

        Parameters:
        ----------
        raw_input: list
            The raw solution as list of tuples.
        instance_size: int
            The size of the instance.

        Returns:
        ----------
        list
            Returns all valid solution lines as a list of tuples.
        """
        raise NotImplementedError

    @abstractmethod
    def encode(self, input):
        """ Encode an input and return it.

        Parameters:
        ----------
        raw_input: list
            The input that is to be encoded as a list of tuples.

        Returns:
        ----------
        byte object
            Returns the input as a byte object.
        """
        return "\n".join(str(" ".join(str(element) for element in line)) for line in input).encode()

    @abstractmethod
    def decode(self, raw_input):
        """ Decode an input and return it.

        Parameters:
        ----------
        raw_input: byte object
            The raw input as byte code.

        Returns:
        ----------
        list
            Returns the input as a list of tuples.
        """
        return [tuple(line.split()) for line in raw_input.decode().splitlines() if line.split()]