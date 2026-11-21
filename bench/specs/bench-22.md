# bench-22

## vowels
check: python3 -c "from f01 import vowels; assert vowels('Banana') == 3"

## fizz
check: python3 -c "from f02 import fizz; assert fizz(9) == 'Fizz' and fizz(4) == '4'"

## reverse
check: python3 -c "from f03 import reverse; assert reverse('abc') == 'cba'"
