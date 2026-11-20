# bench-28

## fizz
check: python3 -c "from f01 import fizz; assert fizz(9) == 'Fizz' and fizz(4) == '4'"

## vowels
check: python3 -c "from f02 import vowels; assert vowels('Banana') == 3"

## clamp
check: python3 -c "from f03 import clamp; assert clamp(9, 0, 5) == 5 and clamp(-1, 0, 5) == 0"

## is_even
check: python3 -c "from f04 import is_even; assert is_even(4) and not is_even(3)"
