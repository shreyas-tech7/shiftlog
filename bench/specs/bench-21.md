# bench-21

## slug
check: python3 -c "from f01 import slug; assert slug('Hello Big World') == 'hello-big-world'"

## mul
check: python3 -c "from f02 import mul; assert mul(4, 3) == 12"

## fizz
check: python3 -c "from f03 import fizz; assert fizz(9) == 'Fizz' and fizz(4) == '4'"

## is_even
check: python3 -c "from f04 import is_even; assert is_even(4) and not is_even(3)"

## clamp
check: python3 -c "from f05 import clamp; assert clamp(9, 0, 5) == 5 and clamp(-1, 0, 5) == 0"
