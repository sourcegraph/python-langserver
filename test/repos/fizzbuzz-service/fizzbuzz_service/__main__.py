import loopers.number_looper

if __name__ == '__main__':
    looper = loopers.number_looper.NumberLooper(1, 16)
    for number_string in looper.get_number_strings():
        print(number_string)