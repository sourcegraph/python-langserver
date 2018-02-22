from ..fizz.fizz_checker import should_fizz
from ..buzz.buzz_checker import should_buzz

def should_fizzbuzz(number):
    '''Whether or not "fizzbuzz" should be printed for this number'''
    return should_fizz(number) and should_buzz(number)