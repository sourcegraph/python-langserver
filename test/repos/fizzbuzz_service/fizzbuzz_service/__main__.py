from .loopers import number_looper

if __name__ == '__main__':
    looper = number_looper.NumberLooper(1, 16)
    for number_string in looper.get_number_strings():
        print(number_string)