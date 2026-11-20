# bench-07

## fizz
check: python3 -c "from f01 import fizz; assert fizz(9) == 'Fizz' and fizz(4) == '4'"

## mul
check: python3 -c "from f02 import mul; assert mul(4, 3) == 12"

## clamp
check: python3 -c "from f03 import clamp; assert clamp(9, 0, 5) == 5 and clamp(-1, 0, 5) == 0"
