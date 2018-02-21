from checkers.fizz import fizz_checker
from checkers.buzz import buzz_checker
from checkers.fizzbuzz import fizzbuzz_checker


def decide_string_for_number(number):
    '''Returns the correct string for the number'''
    if fizzbuzz_checker.should_fizzbuzz(number):
        return "FIZZBUZZ"
    
    if fizz_checker.should_fizz(number):
        return "FIZZ"

    if buzz_checker.should_buzz(number):
        return "BUZZ"

    return str(number)
