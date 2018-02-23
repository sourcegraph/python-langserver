from enum import Enum
from ..checkers.fizz import fizz_checker
from ..checkers.buzz import buzz_checker
from ..checkers.fizzbuzz import fizzbuzz_checker

class OutputDecision(Enum):
    '''Convenient enum representing a particular output for a number'''
    NUMBER = 1
    FIZZ = 2
    BUZZ = 3
    FIZZBUZZ = 4

def decide_output_for_number(number):
    '''Decides the output for a given number'''
    if fizzbuzz_checker.should_fizzbuzz(number):
        return OutputDecision.FIZZBUZZ
    
    if fizz_checker.should_fizz(number):
        return OutputDecision.FIZZ

    if buzz_checker.should_buzz(number):
        return OutputDecision.BUZZ

    return OutputDecision.NUMBER