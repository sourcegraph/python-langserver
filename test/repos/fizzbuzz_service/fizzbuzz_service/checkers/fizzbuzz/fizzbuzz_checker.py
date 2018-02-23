from ..fizz import fizz_checker
from ..buzz.buzz_checker import should_buzz

def should_fizzbuzz(number):
    '''Whether or not "fizzbuzz" should be printed for this number'''
    return fizz_checker.should_fizz(number) and should_buzz(number)