from .number_decision import OutputDecision, decide_output_for_number

def output_string_for_number(number):
    '''Returns the correct string for the number'''
    decision = decide_output_for_number(number)

    if decision == OutputDecision.FIZZBUZZ:
        return "FIZZBUZZ"

    if decision == OutputDecision.FIZZ:
        return "FIZZ"

    if decision == OutputDecision.BUZZ:
        return "BUZZ"
    
    return str(number)
