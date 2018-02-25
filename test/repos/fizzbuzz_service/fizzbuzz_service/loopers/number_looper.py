import fizzbuzz_service.string_deciders.number_decider

class NumberLooper(object):
    '''Very important class that is capable of gathering all the number strings in [start, end)'''
    def __init__(self, start, end):
        self.start = start
        self.end = end

        if (start> end):
            raise ValueError("start {} > end {}".format(start, end))
    
    def get_number_strings(self):
        '''Returns the number strings in [self.start, self.end)'''
        number_strings = []
        for number in range(self.start, self.end):
            number_string = fizzbuzz_service.string_deciders.number_decider.output_string_for_number(number)
            number_strings.append(number_string)
        return number_strings
